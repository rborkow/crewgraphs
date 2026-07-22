from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from crewgraphs.jobs.cross_check import cross_check


ROOT = Path(__file__).resolve().parents[2]
PP_990 = json.loads((ROOT / "spike/output/237397498/propublica.json").read_text())
PARSED_990 = json.loads(
    (ROOT / "spike/output/237397498/202103139349302615.parsed.json").read_text()
)
PP_EZ = json.loads((ROOT / "spike/output/030388282/propublica.json").read_text())
PARSED_EZ = json.loads(
    (ROOT / "spike/output/030388282/202133159349200948.parsed.json").read_text()
)


class FakeDb:
    def __init__(self, extracts: list[dict[str, Any]], pp_rows: list[dict[str, Any]]) -> None:
        self.extracts = extracts
        self.pp_rows = pp_rows
        self.review_tasks: list[dict[str, Any]] = []
        self.final_stats: dict[str, Any] = {}
        self.final_status = ""

    def execute(self, query: str, params: object = None) -> list[dict[str, Any]]:
        values = tuple(params or ())
        if "INSERT INTO ops.ingest_run" in query:
            return [{"id": "run-1"}]
        if "FROM staging.filing_extract" in query:
            return self.extracts
        if "FROM staging.propublica_org" in query:
            return self.pp_rows
        if "INSERT INTO core.review_task" in query:
            self.review_tasks.append(
                {"entity_id": values[0], "payload": json.loads(values[1])}
            )
        if "SET status = %s" in query:
            self.final_status = str(values[0])
            self.final_stats = json.loads(values[2])
        return []


def _extract(document: dict[str, Any], *, id: str = "extract-1") -> dict[str, Any]:
    return {
        "id": id,
        "source_record_id": f"source-{id}",
        "ein": document["ein"],
        "irs_object_id": document["object_id"],
        "concepts": document,
    }


def _pp(document: dict[str, Any]) -> dict[str, Any]:
    return {"ein": f"{document['organization']['ein']:09d}", "raw_payload": document}


def test_cross_check_counts_real_fixture_anchor_values_as_matches() -> None:
    db = FakeDb([_extract(PARSED_990)], [_pp(PP_990)])

    assert cross_check(db) == "run-1"

    assert db.review_tasks == []
    assert db.final_status == "succeeded"
    assert db.final_stats == {
        "comparisons": 6,
        "matches": 6,
        "pp_nulls": 0,
        "no_pp_rows": 0,
        "mismatches": 0,
    }


def test_cross_check_treats_ez_propublica_nulls_as_coverage_not_mismatches() -> None:
    db = FakeDb([_extract(PARSED_EZ)], [_pp(PP_EZ)])

    cross_check(db)

    assert db.review_tasks == []
    assert db.final_stats == {
        "comparisons": 6,
        "matches": 4,
        "pp_nulls": 2,
        "no_pp_rows": 0,
        "mismatches": 0,
    }


def test_cross_check_treats_a_missing_propublica_year_as_lag_not_mismatch() -> None:
    missing_year = copy.deepcopy(PARSED_990)
    missing_year["tax_period_end"] = "2029-12-31"
    db = FakeDb([_extract(missing_year)], [_pp(PP_990)])

    cross_check(db)

    assert db.review_tasks == []
    assert db.final_stats == {
        "comparisons": 6,
        "matches": 0,
        "pp_nulls": 0,
        "no_pp_rows": 6,
        "mismatches": 0,
    }


def test_cross_check_creates_one_review_task_for_one_off_anchor_value() -> None:
    matching = [_extract(copy.deepcopy(PARSED_990), id=f"extract-{n}") for n in range(20)]
    off = copy.deepcopy(PARSED_990)
    off["concepts"]["total_revenue"]["value"] += 1
    db = FakeDb(matching + [_extract(off, id="extract-off")], [_pp(PP_990)])

    cross_check(db)

    assert len(db.review_tasks) == 1
    assert db.review_tasks[0]["entity_id"] == "extract-off"
    assert db.review_tasks[0]["payload"] == {
        "ein": "237397498",
        "tax_period": "202012",
        "concept": "total_revenue",
        "ours": 301702,
        "theirs": 301701,
        "filing_reference": {
            "filing_extract_id": "extract-off",
            "irs_object_id": "202103139349302615",
            "source_record_id": "source-extract-off",
        },
    }
    assert db.final_stats["comparisons"] == 126
    assert db.final_stats["mismatches"] == 1
    assert db.final_status == "succeeded"


def test_cross_check_fails_after_recording_systemic_mismatches_and_tasks() -> None:
    off = copy.deepcopy(PARSED_990)
    off["concepts"]["total_revenue"]["value"] += 1
    db = FakeDb([_extract(off)], [_pp(PP_990)])

    with pytest.raises(RuntimeError, match="exceeds 5%"):
        cross_check(db)

    assert len(db.review_tasks) == 1
    assert db.final_status == "failed"
    assert db.final_stats["comparisons"] == 6
    assert db.final_stats["mismatches"] == 1
