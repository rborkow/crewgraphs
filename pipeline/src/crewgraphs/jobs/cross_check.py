"""Compare parsed IRS anchor concepts against ProPublica's non-canonical data."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from ..db import DatabaseGateway
from ..quarantine import quarantine
from ..runlog import IngestRun


SOURCE = "propublica"
ANCHORS = {
    "total_revenue": "totrevenue",
    "total_expenses": "totfuncexpns",
    "total_assets_eoy": "totassetsend",
    "total_liabilities_eoy": "totliabend",
    "contributions_grants": "totcntrbgfts",
    "program_service_revenue": "totprgmrevnue",
}


def cross_check(db: DatabaseGateway) -> str:
    """Run the six-anchor ProPublica check and return its ingest-run id.

    ProPublica is a discovery/cross-check oracle only: a missing ProPublica row
    or a null field is recorded as coverage information, never as canonical data
    or a mismatch.
    """
    with IngestRun(db, job_name="cross_check", source=SOURCE) as run:
        for stat in ("comparisons", "matches", "pp_nulls", "no_pp_rows", "mismatches"):
            run.add_stat(stat, 0)
        extracts = db.execute(
            """
            SELECT id, source_record_id, ein, irs_object_id, concepts, tax_period_end
            FROM staging.filing_extract
            """
        )
        propublica_rows = db.execute(
            """
            SELECT ein, raw_payload
            FROM staging.propublica_org
            """
        )
        filings_by_ein = _propublica_filings(propublica_rows)

        for extract in extracts:
            _cross_check_extract(db, run, extract, filings_by_ein.get(str(extract["ein"]), {}))

        comparisons = int(run.stats.get("comparisons", 0))
        mismatches = int(run.stats.get("mismatches", 0))
        if comparisons and mismatches / comparisons > 0.05:
            raise RuntimeError(
                f"cross-check mismatch rate {mismatches}/{comparisons} exceeds 5%"
            )
    return run.id or ""


def _propublica_filings(rows: list[dict[str, Any]]) -> dict[str, dict[str, Mapping[str, Any]]]:
    """Index the current PP payloads by EIN and the spike's YYYYMM tax period."""
    indexed: dict[str, dict[str, Mapping[str, Any]]] = {}
    for row in rows:
        payload = _as_mapping(row.get("raw_payload"))
        if payload is None:
            continue
        periods: dict[str, Mapping[str, Any]] = {}
        for filing in payload.get("filings_with_data", []):
            if isinstance(filing, Mapping) and filing.get("tax_prd") is not None:
                periods[str(filing["tax_prd"])] = filing
        indexed[str(row["ein"])] = periods
    return indexed


def _cross_check_extract(
    db: DatabaseGateway,
    run: IngestRun,
    extract: dict[str, Any],
    pp_filings: Mapping[str, Mapping[str, Any]],
) -> None:
    document = _as_mapping(extract.get("concepts"))
    if document is None:
        quarantine(
            db,
            run.id or "",
            "cross_check",
            str(extract.get("irs_object_id") or extract.get("id")),
            "cross_check_bad_extract",
            details={"filing_extract_id": str(extract.get("id")), "problem": "concepts is not a JSON object"},
        )
        run.add_stat("quarantines")
        return
    # Filing extraction stages the complete parsed-document envelope.  Supporting
    # a direct concept map keeps this boundary usable by simple staging clients.
    concepts = _as_mapping(document.get("concepts")) or document
    # tax_period_end is a header column (migration 010); the jsonb fallback keeps
    # older staged rows comparable.
    period_end = extract.get("tax_period_end") or document.get("tax_period_end")
    tax_period = tax_prd_from_end(str(period_end or ""))
    if not tax_period:
        quarantine(
            db,
            run.id or "",
            "cross_check",
            str(extract.get("irs_object_id") or extract.get("id")),
            "cross_check_missing_tax_period",
            details={"filing_extract_id": str(extract.get("id"))},
        )
        run.add_stat("quarantines")
        return
    pp_filing = pp_filings.get(tax_period)

    for concept, pp_field in ANCHORS.items():
        ours = _concept_value(concepts.get(concept), extract.get("id"), concept)
        run.add_stat("comparisons")
        if pp_filing is None:
            run.add_stat("no_pp_rows")
            continue
        theirs = pp_filing.get(pp_field)
        if theirs is None:
            run.add_stat("pp_nulls")
            continue
        if ours == theirs:
            run.add_stat("matches")
            continue

        run.add_stat("mismatches")
        task = {
            "ein": str(extract["ein"]),
            "tax_period": tax_period,
            "concept": concept,
            "ours": ours,
            "theirs": theirs,
            "filing_reference": {
                "filing_extract_id": str(extract["id"]),
                "irs_object_id": str(extract["irs_object_id"]),
                "source_record_id": str(extract["source_record_id"]),
            },
        }
        db.execute(
            """
            INSERT INTO core.review_task
                (entity_type, entity_id, task_type, details)
            VALUES ('filing_extract', %s, 'cross_check_mismatch', %s::jsonb)
            """,
            (extract["id"], json.dumps(task)),
        )
        run.warn(
            "cross-check mismatch "
            f"EIN {extract['ein']} tax_period={tax_period} {concept}: "
            f"ours={ours} theirs={theirs}"
        )


def tax_prd_from_end(end: str) -> str:
    """Match ``spike/crosscheck.py``: ``2023-12-31`` becomes ``202312``."""
    return end[:7].replace("-", "") if end else ""


def _concept_value(value: object, filing_id: object, concept: str) -> int | None:
    result = _as_mapping(value)
    if result is None:
        raise ValueError(f"filing_extract {filing_id} is missing concept {concept}")
    status = result.get("status")
    if status == "resolved":
        raw_value = result.get("value")
        if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
            raise ValueError(f"filing_extract {filing_id} has invalid {concept} value")
        return int(raw_value)
    if status == "absent":
        # The spike treats omitted optional IRS e-file lines as dollar-zero.
        return 0
    if status == "not_on_form":
        return None
    raise ValueError(f"filing_extract {filing_id} has invalid {concept} status {status!r}")


def _as_mapping(value: object) -> Mapping[str, Any] | None:
    if isinstance(value, Mapping):
        return value
    if isinstance(value, str):
        decoded = json.loads(value)
        return decoded if isinstance(decoded, Mapping) else None
    return None


__all__ = ["ANCHORS", "cross_check", "tax_prd_from_end"]
