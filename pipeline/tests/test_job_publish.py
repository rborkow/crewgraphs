from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from crewgraphs.jobs.publish import (
    PublishInvariantError,
    _coverage_state,
    publish,
)


GENERATED = "2026-07-22T12:00:00Z"
RETRIEVED = "2026-07-20T12:00:00Z"
ORG_JUNE = "10000000-0000-4000-8000-000000000001"
ORG_AMENDED = "10000000-0000-4000-8000-000000000002"
ORG_POSTCARD = "10000000-0000-4000-8000-000000000003"


class PublishFake:
    def __init__(self, source: dict[str, list[dict[str, Any]]] | None = None) -> None:
        self.source = deepcopy(source or source_rows())
        self.calls: list[tuple[str, object]] = []
        self.writes: list[tuple[str, tuple[Any, ...]]] = []
        self.snapshot_ids = ["old-1", "old-2", "old-3"]
        self.read_snapshot_ids = {"old-1", "old-2", "old-3"}

    def execute(self, query: str, params: object = None) -> list[dict[str, Any]]:
        compact = " ".join(query.split())
        self.calls.append((compact, params))
        if compact.startswith("INSERT INTO ops.ingest_run"):
            return [{"id": "run-publish"}]
        if compact.startswith("UPDATE ops.ingest_run"):
            self.writes.append(("ingest_run_update", tuple(params or ())))
            return []
        if "FROM core.organization AS o" in compact:
            return deepcopy(self.source["organizations"])
        if "FROM read.org_slug_history" in compact:
            return deepcopy(self.source["slug_history"])
        if "FROM core.filing AS f JOIN core.source_record" in compact:
            return deepcopy(self.source["filings"])
        if "JOIN core.financial_fact AS ff" in compact and "concept_definition" in compact:
            return deepcopy(self.source["facts"])
        if "FROM core.epostcard_observation" in compact:
            return deepcopy(self.source["epostcards"])
        if "FROM core.organization_alias" in compact:
            return deepcopy(self.source["aliases"])
        if "FROM core.metric_value" in compact:
            return deepcopy(self.source["metrics"])
        if "FROM core.person_role" in compact:
            return deepcopy(self.source["people"])
        if "FROM core.organization_relationship" in compact:
            return deepcopy(self.source["relationships"])
        if "FROM core.metric_definition" in compact:
            return deepcopy(self.source["metric_definitions"])
        if compact.startswith("INSERT INTO ops.publish_snapshot"):
            snapshot_id = "new-4"
            self.snapshot_ids.append(snapshot_id)
            return [{"id": snapshot_id}]
        if compact.startswith("WITH target AS MATERIALIZED"):
            self.writes.append(("atomic_flip", tuple(params or ())))
            return [{"id": "new-4"}]
        if compact.startswith("WITH stale AS MATERIALIZED"):
            stale = self.snapshot_ids[:-3]
            self.snapshot_ids = self.snapshot_ids[-3:]
            self.read_snapshot_ids.difference_update(stale)
            self.read_snapshot_ids.add("new-4")
            return [{"deleted_count": len(stale)}]
        if compact.startswith("INSERT INTO read."):
            table = compact.split()[2]
            values = tuple(params or ())
            self.writes.append((table, values))
            if values and table != "read.org_slug_history":
                self.read_snapshot_ids.add(str(values[0]))
            return []
        raise AssertionError(f"unexpected SQL: {compact}")

    def table_writes(self, table: str) -> list[tuple[Any, ...]]:
        return [params for name, params in self.writes if name == table]


def source_rows() -> dict[str, list[dict[str, Any]]]:
    organizations = [
        _organization(ORG_JUNE, "june-rowing", "June Rowing", "111111111"),
        _organization(
            ORG_AMENDED, "amended-rowing", "Amended Rowing", "222222222"
        ),
        _organization(
            ORG_POSTCARD,
            "postcard-rowing",
            "Postcard Rowing",
            "333333333",
            org_type="adaptive_program",
        ),
    ]
    june_2022 = _filing(ORG_JUNE, "filing-june-2022", 2022, "2022-07-01", "2023-06-30")
    june_2024 = _filing(ORG_JUNE, "filing-june-2024", 2024, "2024-07-01", "2025-06-30")
    amended = _filing(
        ORG_AMENDED,
        "filing-amended-2024",
        2024,
        "2024-01-01",
        "2024-12-31",
        amended=True,
    )
    facts: list[dict[str, Any]] = []
    facts.extend(_facts(june_2022, revenue=1000, expenses=800, assets=5000, liabilities=1000))
    facts.extend(_facts(june_2024, revenue=1400, expenses=1000, assets=6000, liabilities=1200))
    facts.extend(_facts(amended, revenue=900, expenses=700, assets=3000, liabilities=500))
    return {
        "organizations": organizations,
        "slug_history": [],
        "filings": [june_2022, june_2024, amended],
        "facts": facts,
        "epostcards": [
            _post(2022, "post-2022"),
            _post(2023, "post-2023"),
            _post(2024, "post-2024"),
        ],
        "aliases": [
            {"organization_id": ORG_JUNE, "alias": "June Crew"},
            {"organization_id": ORG_POSTCARD, "alias": "Postcard Adaptive"},
        ],
        "metrics": [
            {
                "metric_value_id": "metric-value-1",
                "metric_key": "operating_margin",
                "metric_version": 1,
                "organization_id": ORG_JUNE,
                "tax_year": 2024,
                "fiscal_year_end": "2025-06-30",
                "value": 0.2857,
                "quality_state": "derived",
                "unit": "percent",
                "source_path": "/Return/ReturnData/IRS990/CYTotalRevenueAmt",
                "normalization_version": 1,
                "filing_id": "filing-june-2024",
                "form_type": "990",
                "tax_period_begin": "2024-07-01",
                "tax_period_end": "2025-06-30",
                "amended_return": False,
                "retrieved_at": RETRIEVED,
            }
        ],
        "people": [
            _person("Alice Cox", 100, "Coach"),
            _person("Vera Volunteer", 0, "Director"),
        ],
        "relationships": [
            {
                "organization_id": ORG_JUNE,
                "relationship_type": "supports",
                "notes": "Provides equipment.",
                "other_org_slug": "amended-rowing",
                "other_display_name": "Amended Rowing",
            }
        ],
        "metric_definitions": [
            {
                "metric_key": "operating_margin",
                "version": 1,
                "label": "Operating margin",
                "description": "Revenue less expenses divided by revenue.",
                "unit": "percent",
                "eligibility_rule": {"requires_positive": ["total_revenue"]},
                "limitation": None,
            }
        ],
    }


def _organization(
    org_id: str, slug: str | None, name: str, ein: str, *, org_type: str = "community_club"
) -> dict[str, Any]:
    return {
        "organization_id": org_id,
        "slug": slug,
        "display_name": name,
        "legal_name": f"{name} Association",
        "org_type": org_type,
        "city": "Crewtown",
        "state": "MA",
        "website": "https://example.test",
        "eins": [ein],
    }


def _filing(
    org_id: str,
    filing_id: str,
    tax_year: int,
    begin: str,
    end: str,
    *,
    amended: bool = False,
    form_type: str = "990",
) -> dict[str, Any]:
    return {
        "filing_id": filing_id,
        "organization_id": org_id,
        "source_record_id": f"source-{filing_id}",
        "form_type": form_type,
        "tax_period_begin": begin,
        "tax_period_end": end,
        "tax_year": tax_year,
        "amended_return": amended,
        "retrieved_at": RETRIEVED,
    }


def _facts(
    filing: dict[str, Any], *, revenue: int, expenses: int, assets: int, liabilities: int
) -> list[dict[str, Any]]:
    values = {
        "total_revenue": revenue,
        "total_expenses": expenses,
        "revenue_less_expenses": revenue - expenses,
        "total_assets_eoy": assets,
        "total_liabilities_eoy": liabilities,
        "net_assets_eoy": assets - liabilities,
        "contributions_grants": revenue // 10,
    }
    labels = {
        "total_revenue": "Total revenue",
        "total_expenses": "Total expenses",
        "revenue_less_expenses": "Revenue less expenses",
        "total_assets_eoy": "Total assets",
        "total_liabilities_eoy": "Total liabilities",
        "net_assets_eoy": "Net assets",
        "contributions_grants": "Contributions and grants",
    }
    return [
        {
            **filing,
            "fact_id": f"fact-{filing['filing_id']}-{concept}",
            "concept": concept,
            "normalization_version": 1,
            "amount": value,
            "source_path": f"/Return/ReturnData/IRS990/{concept}",
            "quality_state": "verified",
            "concept_label": labels[concept],
            "unit": "USD",
        }
        for concept, value in values.items()
    ]


def _post(year: int, observation_id: str) -> dict[str, Any]:
    return {
        "observation_id": observation_id,
        "ein": "333333333",
        "tax_year": year,
        "tax_period_end": f"{year}-12-31",
        "source_record_id": f"source-{observation_id}",
        "retrieved_at": RETRIEVED,
    }


def _person(name: str, comp: int, title: str) -> dict[str, Any]:
    return {
        "person_role_id": f"person-{name}",
        "filing_id": "filing-june-2024",
        "person_name": name,
        "title": title,
        "reportable_compensation": comp,
        "other_compensation": 0,
        "deferred_compensation": 0,
        "nontaxable_benefits": 0,
        "related_organization_compensation": 0,
        "role_flags": [],
        "organization_id": ORG_JUNE,
        "form_type": "990",
        "tax_period_begin": "2024-07-01",
        "tax_period_end": "2025-06-30",
        "tax_year": 2024,
        "amended_return": False,
        "retrieved_at": RETRIEVED,
    }


def _schema(name: str) -> dict[str, Any]:
    repo = Path(__file__).resolve().parents[2]
    return json.loads(
        (repo / "packages" / "contracts" / "schemas" / name).read_text()
    )


def test_all_invariant_gate_failures_are_collected_before_publish_writes() -> None:
    source = source_rows()
    source["organizations"][0]["slug"] = None
    source["organizations"][1]["slug"] = "stolen-slug"
    source["slug_history"] = [
        {"slug": "stolen-slug", "org_id": ORG_JUNE, "is_current": False}
    ]
    for fact in source["facts"]:
        if fact["filing_id"] == "filing-june-2024" and fact["concept"] == "revenue_less_expenses":
            fact["amount"] = 9999
        if fact["filing_id"] == "filing-june-2024" and fact["concept"] == "net_assets_eoy":
            fact["amount"] = 9999
    db = PublishFake(source)

    with pytest.raises(PublishInvariantError) as error:
        publish(db, generated_at=GENERATED)

    message = str(error.value)
    assert "revenue identity" in message
    assert "balance sheet identity" in message
    assert "has no slug" in message
    assert "stolen-slug" in message
    assert not any(name.startswith("read.") for name, _ in db.writes)
    assert not any("INSERT INTO ops.publish_snapshot" in query for query, _ in db.calls)


def test_published_payload_and_source_refs_validate_against_real_contracts() -> None:
    db = PublishFake()
    assert publish(db, generated_at=GENERATED) == "run-publish"

    profile_validator = Draft202012Validator(
        _schema("org-profile-payload.v1.schema.json"), format_checker=FormatChecker()
    )
    source_validator = Draft202012Validator(
        _schema("source-ref.v1.schema.json"), format_checker=FormatChecker()
    )
    profile_rows = db.table_writes("read.org_profile")
    assert len(profile_rows) == 3
    payloads = [json.loads(row[2]) for row in profile_rows]
    assert all(not list(profile_validator.iter_errors(payload)) for payload in payloads)
    june = next(payload for payload in payloads if payload["org_id"] == ORG_JUNE)
    assert june["snapshot"][0]["ref"]["period"]["label"] == "FY2024 (Jul 2024–Jun 2025)"
    assert june["people"][0]["volunteer_count"] == 1
    assert june["people"][0]["compensated"][0]["name"] == "Alice Cox"
    postcard = next(payload for payload in payloads if payload["org_id"] == ORG_POSTCARD)
    assert postcard["snapshot"][0]["key"] == "filing_presence"

    refs = [json.loads(row[9]) for row in db.table_writes("read.org_financial_series")]
    assert refs
    assert all(not list(source_validator.iter_errors(ref)) for ref in refs)
    metric_ref = next(ref for ref in refs if ref["metric"] is not None)
    assert metric_ref["metric"] == {"key": "operating_margin", "version": 1}
    assert metric_ref["unit"] == "USD"


def test_coverage_includes_missing_gap_amendment_and_990n_span() -> None:
    db = PublishFake()
    publish(db, generated_at=GENERATED)
    rows = db.table_writes("read.org_filing_coverage")
    coverage = {(row[1], row[2]): (row[3], row) for row in rows}

    assert coverage[(ORG_JUNE, 2022)][0] == "990"
    assert coverage[(ORG_JUNE, 2023)][0] == "missing"
    assert coverage[(ORG_JUNE, 2023)][1][4] == GENERATED
    assert coverage[(ORG_JUNE, 2024)][0] == "990"
    assert coverage[(ORG_AMENDED, 2024)][0] == "amended"
    assert [coverage[(ORG_POSTCARD, year)][0] for year in (2022, 2023, 2024)] == [
        "990n",
        "990n",
        "990n",
    ]


@pytest.mark.parametrize(
    ("forms", "postcards", "expected"),
    [
        ([{"form_type": "990EZ"}, {"form_type": "990"}], [], "990"),
        ([{"form_type": "990EZ"}], [], "990ez"),
        ([], [{"tax_year": 2024}], "990n_only"),
        ([], [], "none"),
    ],
)
def test_coverage_state_precedence(forms: list[dict[str, Any]], postcards: list[dict[str, Any]], expected: str) -> None:
    assert _coverage_state(forms, postcards) == expected


def test_publish_flip_is_one_atomic_cte_statement_and_stats_are_collected() -> None:
    db = PublishFake()
    publish(db, generated_at=GENERATED)
    flips = [
        query for query, _ in db.calls if query.startswith("WITH target AS MATERIALIZED")
    ]

    assert len(flips) == 1
    assert "UPDATE ops.publish_snapshot" in flips[0]
    assert "status = 'building'" in flips[0]
    assert "INSERT INTO read.published_snapshot" in flips[0]
    assert "ON CONFLICT (singleton) DO UPDATE" in flips[0]
    final = db.table_writes("ingest_run_update")[-1]
    stats = json.loads(final[2])
    assert stats == {
        "orgs_published": 3,
        "series_rows": len(db.table_writes("read.org_financial_series")),
        "coverage_rows": len(db.table_writes("read.org_filing_coverage")),
        "payloads_validated": 3,
        "gc_snapshots_deleted": 1,
    }


def test_gc_retains_exactly_three_snapshots_and_preserves_slug_history() -> None:
    db = PublishFake()
    publish(db, generated_at=GENERATED)

    assert db.snapshot_ids == ["old-2", "old-3", "new-4"]
    assert db.read_snapshot_ids == {"old-2", "old-3", "new-4"}
    gc_query = next(query for query, _ in db.calls if query.startswith("WITH stale AS MATERIALIZED"))
    assert "OFFSET 3" in gc_query
    assert "UPDATE read.org_slug_history" in gc_query
    assert "DELETE FROM ops.publish_snapshot" in gc_query


def test_invalid_profile_contract_blocks_snapshot_creation() -> None:
    source = source_rows()
    source["organizations"][0]["org_type"] = "not_a_real_type"
    db = PublishFake(source)

    with pytest.raises(PublishInvariantError, match="org_type"):
        publish(db, generated_at=GENERATED)

    assert not any("INSERT INTO ops.publish_snapshot" in query for query, _ in db.calls)
