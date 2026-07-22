from __future__ import annotations

import copy
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from crewgraphs.jobs.derive import derive


ROOT = Path(__file__).resolve().parents[2]
GOLDEN = ROOT / "pipeline" / "tests" / "fixtures" / "golden"


DEFINITIONS = [
    {"metric_key": "operating_margin", "version": 1, "eligibility_rule": {"requires_positive": ["total_revenue"]}},
    {"metric_key": "revenue_cagr", "version": 1, "eligibility_rule": {"min_observations": 3}},
    {"metric_key": "contribution_dependency", "version": 1, "eligibility_rule": {"requires_positive": ["total_revenue"]}},
    {"metric_key": "program_service_share", "version": 1, "eligibility_rule": {"requires_positive": ["total_revenue"]}},
    {"metric_key": "compensation_intensity", "version": 1, "eligibility_rule": {"requires_positive": ["total_expenses"]}},
    {"metric_key": "membership_dues_share", "version": 1, "eligibility_rule": {"requires_positive": ["total_revenue"], "requires_resolved": ["membership_dues"]}},
]


class FakeDeriveDb:
    """Small in-memory gateway: derives behavior from SQL parameters, never a DB."""

    def __init__(self, extracts: list[dict[str, Any]], *, definitions: list[dict[str, Any]] | None = None) -> None:
        self.extracts = extracts
        self.definitions = definitions or copy.deepcopy(DEFINITIONS)
        self.identifiers = {str(row["ein"]): f"org-{row['ein']}" for row in extracts}
        self.filings: list[dict[str, Any]] = []
        self.facts: list[dict[str, Any]] = []
        self.people: list[dict[str, Any]] = []
        self.metrics: list[dict[str, Any]] = []
        self.review_tasks: list[dict[str, Any]] = []
        self.final_stats: dict[str, Any] = {}
        self._counter = 0

    def _id(self, kind: str) -> str:
        self._counter += 1
        return f"{kind}-{self._counter}"

    def execute(self, query: str, params: object = None) -> list[dict[str, Any]]:
        values = tuple(params or ())
        if "INSERT INTO ops.ingest_run" in query:
            return [{"id": "run-derive"}]
        if "FROM core.external_identifier" in query:
            return [{"ein": ein, "organization_id": org} for ein, org in self.identifiers.items()]
        if "FROM staging.filing_extract" in query:
            return self.extracts
        if "FROM core.filing AS f" in query:
            version = values[0]
            rows: list[dict[str, Any]] = []
            for fact in self.facts:
                filing = next(item for item in self.filings if item["id"] == fact["filing_id"])
                if filing["is_authoritative"] and fact["normalization_version"] == version:
                    rows.append({
                        "filing_id": filing["id"], "organization_id": filing["organization_id"],
                        "irs_object_id": filing["irs_object_id"], "tax_year": filing["tax_year"],
                        "fiscal_year_end": filing["tax_period_end"], "fact_id": fact["id"],
                        "concept": fact["concept"], "amount": fact["amount"], "quality_state": "verified",
                    })
            return rows
        if "FROM core.filing" in query and "tax_period_end = %s" in query:
            ein, end, form = values
            return [dict(row) for row in self.filings if (row["ein"], row["tax_period_end"], row["form_type"]) == (ein, end, form)]
        if query.strip().startswith("INSERT INTO core.filing"):
            (org, source, ein, form, begin, end, year, return_version, object_id, amended, authoritative) = values
            if any(row["ein"] == ein and row["irs_object_id"] == object_id for row in self.filings):
                return []
            row = {"id": self._id("filing"), "organization_id": org, "source_record_id": source, "ein": ein, "form_type": form,
                   "tax_period_begin": begin, "tax_period_end": end, "tax_year": year, "return_version": return_version,
                   "irs_object_id": object_id, "amended_return": amended, "is_authoritative": authoritative}
            self.filings.append(row)
            return [{"id": row["id"]}]
        if query.strip().startswith("SELECT id FROM core.filing"):
            ein, object_id = values
            return [{"id": row["id"]} for row in self.filings if row["ein"] == ein and row["irs_object_id"] == object_id]
        if query.strip().startswith("INSERT INTO core.financial_fact"):
            filing_id, concept, version, amount, path = values
            if any((row["filing_id"], row["concept"], row["normalization_version"]) == (filing_id, concept, version) for row in self.facts):
                return []
            row = {"id": self._id("fact"), "filing_id": filing_id, "concept": concept, "normalization_version": version, "amount": Decimal(str(amount)), "source_path": path}
            self.facts.append(row)
            return [{"id": row["id"]}]
        if "information_schema.table_constraints" in query:
            return []
        if "FROM core.person_role" in query:
            filing_id, name, title = values
            return [{"id": row["id"]} for row in self.people if (row["filing_id"], row["person_name"], row["title"]) == (filing_id, name, title)]
        if query.strip().startswith("INSERT INTO core.person_role"):
            filing_id, name, title = values[:3]
            row = {"id": self._id("person"), "filing_id": filing_id, "person_name": name, "title": title}
            self.people.append(row)
            return [{"id": row["id"]}]
        if "FROM core.metric_definition" in query:
            return self.definitions
        if query.strip().startswith("INSERT INTO core.metric_value"):
            key, version, org, tax_year, fye, value, ids = values
            if any((row["metric_key"], row["metric_version"], row["organization_id"], row["fiscal_year_end"]) == (key, version, org, fye) for row in self.metrics):
                return []
            row = {"id": self._id("metric"), "metric_key": key, "metric_version": version, "organization_id": org,
                   "tax_year": tax_year, "fiscal_year_end": fye, "value": Decimal(str(value)), "input_fact_ids": ids}
            self.metrics.append(row)
            return [{"id": row["id"]}]
        if query.strip().startswith("INSERT INTO core.review_task"):
            self.review_tasks.append({"entity_id": values[0], "details": json.loads(values[1])})
            return []
        if "SET status = %s" in query:
            self.final_stats = json.loads(values[2])
        return []


def _extract(
    *, ein: str = "123456789", object_id: str = "2024001", begin: str = "2023-01-01", end: str = "2023-12-31",
    amended: bool = False, concepts: dict[str, Any] | None = None, form_type: str = "IRS990", people: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {"id": f"extract-{object_id}", "source_record_id": f"source-{object_id}", "ein": ein, "irs_object_id": object_id,
            "form_type": form_type, "return_version": "v1", "tax_period_begin": begin, "tax_period_end": end,
            "amended_return": amended, "concepts": concepts or {}, "people": people or []}


def _concepts(*, dues_status: str = "resolved", revenue: int = 100) -> dict[str, Any]:
    values = {"total_revenue": revenue, "total_expenses": 80, "contributions_grants": 20, "program_service_expense": 60,
              "salaries_benefits_total": 40, "membership_dues": 10}
    return {name: {"status": "resolved", "value": amount, "xpath": f"{name}Amt"} for name, amount in values.items()} | {
        "membership_dues": {"status": dues_status, "value": 10 if dues_status == "resolved" else None, "xpath": None}
    }


def test_filing_precedence_prefers_amendments_then_highest_object_id() -> None:
    db = FakeDeriveDb([
        _extract(object_id="100", amended=False), _extract(object_id="200", amended=True), _extract(object_id="300", amended=True),
    ])

    derive(db)

    assert [(row["irs_object_id"], row["is_authoritative"]) for row in db.filings] == [("100", False), ("200", False), ("300", True)]


def test_late_amendment_opens_review_without_mutating_existing_filing() -> None:
    db = FakeDeriveDb([_extract(object_id="100", amended=False)])
    derive(db)
    db.extracts.append(_extract(object_id="200", amended=True))

    derive(db)

    old = next(row for row in db.filings if row["irs_object_id"] == "100")
    new = next(row for row in db.filings if row["irs_object_id"] == "200")
    assert old["is_authoritative"] is True
    assert new["is_authoritative"] is True
    assert db.review_tasks == [{"entity_id": new["id"], "details": {"existing_filing_id": old["id"], "existing_irs_object_id": "100", "new_irs_object_id": "200"}}]
    assert db.final_stats["amendment_reviews"] == 1


def test_tax_year_uses_period_begin_for_concord_and_period_end_for_calendar_vesper() -> None:
    concord = json.loads((GOLDEN / "202133159349200948.parsed.json").read_text())
    vesper = json.loads((GOLDEN / "202103139349302615.parsed.json").read_text())
    db = FakeDeriveDb([
        _extract(ein=concord["ein"], object_id=concord["object_id"], begin=concord["tax_period_begin"], end=concord["tax_period_end"], form_type=concord["form_type"], concepts=concord["concepts"]),
        _extract(ein=vesper["ein"], object_id=vesper["object_id"], begin=None, end=vesper["tax_period_end"], form_type=vesper["form_type"], concepts=vesper["concepts"]),
    ])

    derive(db)

    tax_years = {row["ein"]: row["tax_year"] for row in db.filings}
    assert tax_years[concord["ein"]] == 2020
    assert tax_years[vesper["ein"]] == 2020


def test_absent_fact_is_verified_zero_and_not_on_form_is_not_inserted() -> None:
    concepts = {"membership_dues": {"status": "absent", "value": None, "xpath": None}, "employee_count": {"status": "not_on_form", "value": None, "xpath": None}}
    db = FakeDeriveDb([_extract(concepts=concepts)])

    derive(db)

    dues = next(row for row in db.facts if row["concept"] == "membership_dues")
    assert dues["amount"] == Decimal("0")
    assert dues["source_path"]
    assert not any(row["concept"] == "employee_count" for row in db.facts)


def test_metric_definitions_produce_all_six_expected_values_and_fact_inputs() -> None:
    db = FakeDeriveDb([
        _extract(object_id="a", begin="2020-01-01", end="2020-12-31", concepts=_concepts(revenue=50)),
        _extract(object_id="b", begin="2021-01-01", end="2021-12-31", concepts=_concepts(revenue=75)),
        _extract(object_id="c", begin="2022-01-01", end="2022-12-31", concepts=_concepts(revenue=100)),
    ])

    derive(db)

    latest = {row["metric_key"]: row for row in db.metrics if row["fiscal_year_end"] == "2022-12-31"}
    assert latest["operating_margin"]["value"] == Decimal("0.2")
    assert latest["contribution_dependency"]["value"] == Decimal("0.2")
    assert latest["program_service_share"]["value"] == Decimal("0.6")
    assert latest["compensation_intensity"]["value"] == Decimal("0.5")
    assert latest["membership_dues_share"]["value"] == Decimal("0.1")
    assert latest["revenue_cagr"]["value"] == Decimal(str(2 ** 0.5 - 1))
    assert len(latest["revenue_cagr"]["input_fact_ids"]) == 2


def test_cagr_with_two_observations_is_suppressed() -> None:
    db = FakeDeriveDb([_extract(object_id="a", concepts=_concepts(revenue=50)), _extract(object_id="b", end="2024-12-31", begin="2024-01-01", concepts=_concepts(revenue=100))])

    derive(db)

    assert not any(row["metric_key"] == "revenue_cagr" for row in db.metrics)
    assert db.final_stats["suppressed_metrics"] >= 1


def test_absent_dues_is_not_resolved_and_second_run_is_insert_idempotent() -> None:
    db = FakeDeriveDb([_extract(concepts=_concepts(dues_status="absent"), people=[{"name": "Volunteer", "title": "Treasurer", "comp": 0}])])

    derive(db)
    first_counts = (len(db.filings), len(db.facts), len(db.people), len(db.metrics))
    derive(db)

    assert not any(row["metric_key"] == "membership_dues_share" for row in db.metrics)
    assert db.final_stats["suppressed_metrics"] >= 1
    assert (len(db.filings), len(db.facts), len(db.people), len(db.metrics)) == first_counts
    assert {key: db.final_stats[key] for key in ("filings_inserted", "facts_inserted", "person_roles_inserted", "metrics_inserted")} == {"filings_inserted": 0, "facts_inserted": 0, "person_roles_inserted": 0, "metrics_inserted": 0}
