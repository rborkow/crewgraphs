"""Parse fetched e-file XML through the versioned CrewGraphs extractor."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import asdict
from typing import Any

from ..concept_map import load_concept_map
from ..db import DatabaseGateway
from ..efile_extract import extract_filing
from ..quarantine import quarantine
from ..raw_store import RawStore
from ..runlog import IngestRun


def efile_parse(
    db: DatabaseGateway,
    store: RawStore,
    *,
    object_ids: Iterable[str] | None = None,
    reparse: bool = False,
) -> dict[str, Any]:
    """Extract staged XMLs and quarantine bad XML without stopping the run.

    ``reparse`` re-extracts already-parsed filings and overwrites their staging
    rows in place. Staging is disposable by design; the immutable record lives
    in core, where derive versions facts by normalization_version and inserts
    superseding person_role rows rather than rewriting old ones.
    """
    requested_ids = list(object_ids) if object_ids is not None else None
    concept_map = load_concept_map()
    with IngestRun(
        db,
        job_name="efile_parse",
        source="givingtuesday",
        params={
            "object_ids": requested_ids,
            "concept_map_version": concept_map.version,
            "reparse": reparse,
        },
    ) as run:
        for candidate in _parse_candidates(db, requested_ids, reparse=reparse):
            object_id = str(candidate["irs_object_id"])
            tax_year = int(candidate["tax_year"])
            source_record_id = str(candidate["source_record_id"])
            key = f"raw/irs/efile-xml/{tax_year}/{object_id}_public.xml"
            try:
                extracted = extract_filing(store.get_raw(key), concept_map)
                if not extracted.ein:
                    raise ValueError("IRS e-file XML has no filer EIN")
            except Exception as exc:
                quarantine(
                    db,
                    run.id or "",
                    "givingtuesday",
                    object_id,
                    "parse_failure",
                    str(candidate.get("raw_uri") or f"r2://{store.bucket}/{key}"),
                    {"error": str(exc), "tax_year": tax_year},
                )
                run.add_stat("parse_failures")
                continue
            conflict_action = (
                """
                ON CONFLICT (irs_object_id) DO UPDATE SET
                    ingest_run_id = EXCLUDED.ingest_run_id,
                    source_record_id = EXCLUDED.source_record_id,
                    ein = EXCLUDED.ein,
                    form_type = EXCLUDED.form_type,
                    return_version = EXCLUDED.return_version,
                    tax_period_begin = EXCLUDED.tax_period_begin,
                    tax_period_end = EXCLUDED.tax_period_end,
                    amended_return = EXCLUDED.amended_return,
                    concepts = EXCLUDED.concepts,
                    people = EXCLUDED.people,
                    warnings = EXCLUDED.warnings
                """
                if reparse
                else "ON CONFLICT DO NOTHING"
            )
            db.execute(
                f"""
                INSERT INTO staging.filing_extract
                    (ingest_run_id, source_record_id, ein, irs_object_id,
                     form_type, return_version, tax_period_begin, tax_period_end,
                     amended_return, concepts, people, warnings)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb)
                {conflict_action}
                """,
                (
                    run.id,
                    source_record_id,
                    extracted.ein,
                    object_id,
                    extracted.form_type,
                    extracted.return_version,
                    extracted.tax_period_begin,
                    extracted.tax_period_end,
                    extracted.amended,
                    json.dumps({name: asdict(result) for name, result in extracted.concepts.items()}),
                    json.dumps([asdict(row) for row in extracted.officer_rows]),
                    json.dumps([]),
                ),
            )
            run.add_stat("objects_parsed")
    return run.stats


def _parse_candidates(
    db: DatabaseGateway, object_ids: list[str] | None, *, reparse: bool = False
) -> list[dict[str, Any]]:
    filter_sql = ""
    params: tuple[object, ...] = ()
    if object_ids is not None:
        filter_sql = "AND e.irs_object_id = ANY(%s)"
        params = (object_ids,)
    unparsed_sql = (
        ""
        if reparse
        else """
        AND NOT EXISTS (
            SELECT 1 FROM staging.filing_extract AS f
            WHERE f.source_record_id = sr.id
        )
        """
    )
    return db.execute(
        f"""
        SELECT DISTINCT e.irs_object_id, e.tax_year, sr.id AS source_record_id, sr.raw_uri
        FROM staging.efile_index_row AS e
        JOIN core.source_record AS sr
          ON sr.source = 'givingtuesday'
         AND sr.external_key = e.irs_object_id
        WHERE true
        {unparsed_sql}
        {filter_sql}
        ORDER BY e.tax_year, e.irs_object_id
        """,
        params,
    )


__all__ = ["efile_parse"]
