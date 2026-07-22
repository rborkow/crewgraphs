"""Acquire and stage IRS Exempt Organizations Business Master File state files."""

from __future__ import annotations

import csv
import io
import json
from datetime import date
from email.utils import parsedate_to_datetime
from typing import TYPE_CHECKING

from ..db import DatabaseGateway
from ..quarantine import quarantine
from ..raw_store import QuarantineableError, RawStore, register_source_record
from ..runlog import IngestRun
from . import is_discovery_name, normalized_ein, verified_irs_eins

if TYPE_CHECKING:
    import httpx


SOURCE = "irs_bmf"
URL_TEMPLATE = "https://www.irs.gov/pub/irs-soi/eo_{state}.csv"


def bmf_sync(
    db: DatabaseGateway,
    store: RawStore,
    http: "httpx.Client",
    *,
    states: list[str],
    watchlist_eins: set[str] | None = None,
    release_date: date | str | None = None,
) -> str:
    """Fetch BMF state files and return the completed ingest-run id.

    ``release_date`` is primarily useful for deterministic backfills/tests.  If
    omitted, each state's HTTP ``Last-Modified`` header is converted to a date;
    an absent or invalid header falls back to ``date.today()``.  A failed state
    (including an immutable-R2 checksum conflict) is quarantined and warned,
    while the remaining states continue and the run succeeds with warnings.

    Staging is delete-then-insert scoped to ``ingest_run_id``, release date, and
    ``raw_row->>'STATE'`` because ``staging.bmf_row`` intentionally has no
    dedicated state column.
    """
    watchlist = (
        {ein for value in watchlist_eins if (ein := normalized_ein(value))}
        if watchlist_eins is not None
        else verified_irs_eins(db)
    )
    with IngestRun(
        db,
        job_name="bmf_sync",
        source=SOURCE,
        params={"states": states, "release_date": str(release_date or "")},
    ) as run:
        for stat in (
            "states_fetched",
            "rows_seen",
            "rows_kept",
            "observations_inserted",
            "quarantines",
        ):
            run.add_stat(stat, 0)
        for requested_state in states:
            state = requested_state.lower()
            url = URL_TEMPLATE.format(state=state)
            raw_key: str | None = None
            try:
                response = http.get(url)
                response.raise_for_status()
                content = response.content
                state_release_date = _release_date(release_date, response.headers.get("Last-Modified"))
                raw_key = f"raw/irs/bmf/{state_release_date.isoformat()}/eo_{state}.csv"
                raw_object = store.put_raw(raw_key, content, "text/csv")
                source_record_id = register_source_record(
                    db,
                    source=SOURCE,
                    external_key=url,
                    raw_object=raw_object,
                    metadata={"state": state.upper(), "release_date": state_release_date.isoformat()},
                )
                run.add_stat("states_fetched")
                _stage_state(
                    db,
                    run=run,
                    source_record_id=source_record_id,
                    state=state.upper(),
                    release_date=state_release_date,
                    content=content,
                    watchlist=watchlist,
                )
            except Exception as exc:
                # Input/source failures are isolated to one state.  Programming
                # and database errors should still terminate a run, but are not
                # expected to be among these normal acquisition exceptions.
                if not _recoverable_acquisition_error(exc):
                    raise
                quarantine(
                    db,
                    run.id or "",
                    SOURCE,
                    url,
                    str(exc),
                    _r2_uri(store, raw_key),
                    {"state": state.upper()},
                )
                run.add_stat("quarantines")
                run.warn(f"{state.upper()}: {exc}")
    return run.id or ""


def _stage_state(
    db: DatabaseGateway,
    *,
    run: IngestRun,
    source_record_id: str,
    state: str,
    release_date: date,
    content: bytes,
    watchlist: set[str],
) -> None:
    db.execute(
        """
        DELETE FROM staging.bmf_row
        WHERE ingest_run_id = %s
          AND bmf_release_date = %s
          AND raw_row ->> 'STATE' = %s
        """,
        (run.id, release_date, state),
    )
    rows = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    for raw_row in rows:
        run.add_stat("rows_seen")
        ein = normalized_ein(raw_row.get("EIN"))
        name = raw_row.get("NAME", "")
        if ein not in watchlist and not is_discovery_name(name):
            continue
        # The core table enforces nine digits.  Keep malformed discovery rows
        # out of both staging and observations rather than turning a full state
        # download into a failed transaction.
        if ein is None:
            run.warn("skipped BMF discovery row with invalid EIN")
            continue
        run.add_stat("rows_kept")
        db.execute(
            """
            INSERT INTO staging.bmf_row
                (ingest_run_id, source_record_id, bmf_release_date, ein, raw_row)
            VALUES (%s, %s, %s, %s, %s::jsonb)
            """,
            (run.id, source_record_id, release_date, ein, json.dumps(raw_row)),
        )
        inserted = db.execute(
            """
            INSERT INTO core.ein_observation
                (source_record_id, ein, bmf_release_date, legal_name, city, state, raw_payload)
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (ein, bmf_release_date) DO NOTHING
            RETURNING id
            """,
            (
                source_record_id,
                ein,
                release_date,
                name or None,
                raw_row.get("CITY") or None,
                raw_row.get("STATE") or None,
                json.dumps(raw_row),
            ),
        )
        if inserted:
            run.add_stat("observations_inserted")


def _release_date(value: date | str | None, last_modified: str | None) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        return date.fromisoformat(value)
    if last_modified:
        try:
            return parsedate_to_datetime(last_modified).date()
        except (TypeError, ValueError, IndexError):
            pass
    return date.today()


def _recoverable_acquisition_error(exc: Exception) -> bool:
    # Avoid importing httpx at module import time, which preserves the harness's
    # optional-dependency behavior for small unit-test environments.
    try:
        import httpx
    except ImportError:
        return isinstance(exc, (QuarantineableError, OSError, UnicodeError, csv.Error))
    return isinstance(exc, (httpx.HTTPError, QuarantineableError, OSError, UnicodeError, csv.Error))


def _r2_uri(store: RawStore, key: str | None) -> str | None:
    return f"r2://{store.bucket}/{key}" if key else None
