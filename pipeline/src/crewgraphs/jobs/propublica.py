"""Bootstrap ProPublica organization records as non-canonical cross-check data."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Iterable

from ..db import DatabaseGateway
from ..quarantine import quarantine
from ..raw_store import RawStore, register_source_record
from ..runlog import IngestRun
from . import normalized_ein, verified_irs_eins

if TYPE_CHECKING:
    import httpx


SOURCE = "propublica"
API_TEMPLATE = "https://projects.propublica.org/nonprofits/api/v2/organizations/{ein}.json"


def propublica_bootstrap(
    db: DatabaseGateway,
    store: RawStore,
    http: "httpx.Client",
    *,
    eins: Iterable[str] | None = None,
    retrieved_date: str,
) -> str:
    """Fetch each watched organization and stage its immutable API response.

    The ProPublica endpoint accepts the numeric EIN, so the API path deliberately
    uses ``int(ein)``.  Staging retains the nine-digit IRS representation, which
    is important for joins to the rest of the pipeline.
    """
    watchlist = _watchlist(db, eins)
    with IngestRun(
        db,
        job_name="propublica_bootstrap",
        source=SOURCE,
        params={"retrieved_date": retrieved_date, "eins": sorted(watchlist)},
    ) as run:
        for stat in ("eins_fetched", "not_found", "payload_bytes"):
            run.add_stat(stat, 0)
        for ein in sorted(watchlist):
            api_ein = str(int(ein))
            url = API_TEMPLATE.format(ein=api_ein)
            response = http.get(url)
            if response.status_code == 404:
                quarantine(
                    db,
                    run.id or "",
                    SOURCE,
                    ein,
                    "propublica_not_found",
                    details={"url": url, "retrieved_date": retrieved_date},
                )
                run.add_stat("not_found")
                continue
            response.raise_for_status()

            # Retain exactly the bytes returned by the API.  ``raw_payload`` is
            # decoded only for PostgreSQL JSONB staging; it is not transformed.
            content = response.content
            payload = json.loads(content)
            raw_key = f"raw/propublica/org/{ein}/{retrieved_date}.json"
            raw_object = store.put_raw(raw_key, content, "application/json")
            source_record_id = register_source_record(
                db,
                source=SOURCE,
                external_key=ein,
                raw_object=raw_object,
                metadata={"retrieved_date": retrieved_date, "url": url},
            )
            _upsert_org(
                db,
                run_id=run.id or "",
                source_record_id=source_record_id,
                ein=ein,
                payload=payload,
                retrieved_date=retrieved_date,
            )
            run.add_stat("eins_fetched")
            run.add_stat("payload_bytes", len(content))
    return run.id or ""


def _watchlist(db: DatabaseGateway, eins: Iterable[str] | None) -> set[str]:
    candidates = verified_irs_eins(db) if eins is None else eins
    return {ein for value in candidates if (ein := normalized_ein(value))}


def _upsert_org(
    db: DatabaseGateway,
    *,
    run_id: str,
    source_record_id: str,
    ein: str,
    payload: object,
    retrieved_date: str,
) -> None:
    """Replace the current staging snapshot for an EIN, or create it.

    ``staging.propublica_org`` intentionally has no unique constraint on EIN, so
    PostgreSQL cannot express this as ``ON CONFLICT``.  Updating the current row
    first is the schema-compatible upsert boundary.  ``created_at`` records this
    retrieval because this staging table has no separate ``retrieved_at`` column.
    """
    encoded_payload = json.dumps(payload)
    updated = db.execute(
        """
        UPDATE staging.propublica_org
        SET ingest_run_id = %s,
            source_record_id = %s,
            raw_payload = %s::jsonb,
            created_at = %s::date
        WHERE id = (
            SELECT id
            FROM staging.propublica_org
            WHERE ein = %s
            ORDER BY created_at DESC, id DESC
            LIMIT 1
        )
        RETURNING id
        """,
        (run_id, source_record_id, encoded_payload, retrieved_date, ein),
    )
    if updated:
        return
    db.execute(
        """
        INSERT INTO staging.propublica_org
            (ingest_run_id, source_record_id, ein, raw_payload, created_at)
        VALUES (%s, %s, %s, %s::jsonb, %s::date)
        """,
        (run_id, source_record_id, ein, encoded_payload, retrieved_date),
    )


__all__ = ["propublica_bootstrap"]
