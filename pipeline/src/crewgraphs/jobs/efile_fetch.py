"""Fetch per-object e-file XML from GivingTuesday's public data lake."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from ..db import DatabaseGateway
from ..quarantine import quarantine
from ..raw_store import RawStore, register_source_record
from ..runlog import IngestRun


# The GivingTuesday lake mirrors IRS 990 XML and is the primary per-object path.
GT_LAKE_XML_URL = (
    "https://gt990datalake-rawdata.s3.amazonaws.com/EfileData/XmlFiles/{object_id}_public.xml"
)


def efile_fetch(
    db: DatabaseGateway,
    store: RawStore,
    http: Any,
    *,
    object_ids: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Fetch staged XMLs sequentially, quarantining expected lake 404s."""
    requested_ids = list(object_ids) if object_ids is not None else None
    with IngestRun(
        db,
        job_name="efile_fetch",
        source="givingtuesday",
        params={"object_ids": requested_ids},
    ) as run:
        for candidate in _fetch_candidates(db, requested_ids):
            object_id = str(candidate["irs_object_id"])
            tax_year = int(candidate["tax_year"])
            url = GT_LAKE_XML_URL.format(object_id=object_id)
            # Deliberately sequential: caller/Actions provides any rate limiting.
            response = http.get(url, timeout=120)
            if response.status_code == 404:
                quarantine(
                    db,
                    run.id or "",
                    "givingtuesday",
                    object_id,
                    "gt_lake_missing",
                    url,
                    {"tax_year": tax_year},
                )
                run.add_stat("gt_lake_missing")
                run.warn(
                    f"GT lake has not yet mirrored object {object_id}; IRS indexes can lead by months"
                )
                continue
            response.raise_for_status()
            raw = store.put_raw(
                f"raw/irs/efile-xml/{tax_year}/{object_id}_public.xml",
                response.content,
                "application/xml",
            )
            register_source_record(
                db,
                source="givingtuesday",
                external_key=object_id,
                raw_object=raw,
                metadata={"tax_year": tax_year, "url": url},
            )
            run.add_stat("objects_fetched")
    return run.stats


def _fetch_candidates(
    db: DatabaseGateway, object_ids: list[str] | None
) -> list[dict[str, Any]]:
    filter_sql = ""
    params: tuple[object, ...] = ()
    if object_ids is not None:
        filter_sql = "AND e.irs_object_id = ANY(%s)"
        params = (object_ids,)
    return db.execute(
        f"""
        SELECT DISTINCT e.irs_object_id, e.tax_year
        FROM staging.efile_index_row AS e
        WHERE NOT EXISTS (
            SELECT 1
            FROM core.source_record AS sr
            WHERE sr.source = 'givingtuesday'
              AND sr.external_key = e.irs_object_id
        )
        {filter_sql}
        ORDER BY e.tax_year, e.irs_object_id
        """,
        params,
    )


__all__ = ["GT_LAKE_XML_URL", "efile_fetch"]
