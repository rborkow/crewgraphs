from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from crewgraphs.jobs.publish import (
    PublishInvariantError,
    _assemble,
    _coverage_state,
    _invariant_failures,
    _is_u13_event,
    _suppression_matches,
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
        if (
            "JOIN core.financial_fact AS ff" in compact
            and "concept_definition" in compact
        ):
            return deepcopy(self.source["facts"])
        if "FROM core.epostcard_observation" in compact:
            return deepcopy(self.source["epostcards"])
        if (
            compact.startswith("WITH latest_regatta AS MATERIALIZED")
            and "candidate_organization_count" in compact
        ):
            return deepcopy(self.source["ambiguous_regatta_clubs"])
        if compact.startswith("WITH latest_regatta AS MATERIALIZED"):
            return deepcopy(self.source["regatta_results"])
        if "FROM core.result_person AS person" in compact:
            return deepcopy(self.source["result_people"])
        if "FROM core.person_suppression" in compact:
            return deepcopy(self.source["person_suppressions"])
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
        if compact.startswith("INSERT INTO core.review_task"):
            self.writes.append(("core.review_task", tuple(params or ())))
            return []
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
        _organization(ORG_AMENDED, "amended-rowing", "Amended Rowing", "222222222"),
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
    facts.extend(
        _facts(june_2022, revenue=1000, expenses=800, assets=5000, liabilities=1000)
    )
    facts.extend(
        _facts(june_2024, revenue=1400, expenses=1000, assets=6000, liabilities=1200)
    )
    facts.extend(
        _facts(amended, revenue=900, expenses=700, assets=3000, liabilities=500)
    )
    return {
        "organizations": organizations,
        "regatta_results": [],
        "ambiguous_regatta_clubs": [],
        "result_people": [],
        "person_suppressions": [],
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
                "input_filing_ids": ["filing-june-2024"],
            }
        ],
        "people": [
            _person(
                "Alice Cox", 100, "Coach", avg_hours_week=40, role_flags=["officer"]
            ),
            _person("Vera Volunteer", 0, "Director"),
            _person(
                "Old Salt",
                60,
                "Head Coach",
                filing_id="filing-june-2022",
                tax_year=2022,
                begin="2022-07-01",
                end="2023-06-30",
            ),
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


def result_source_rows() -> dict[str, list[dict[str, Any]]]:
    source = source_rows()
    time_entry = "20000000-0000-4000-8000-000000000001"
    herenow_entry = "20000000-0000-4000-8000-000000000002"
    time_club = "30000000-0000-4000-8000-000000000001"
    herenow_club = "30000000-0000-4000-8000-000000000002"
    source["aliases"].append({"organization_id": ORG_AMENDED, "alias": "Harbor Rowing"})
    source["regatta_results"] = [
        {
            "organization_id": ORG_JUNE,
            "slug": "june-rowing",
            "regatta_id": "40000000-0000-4000-8000-000000000001",
            "source": "time_team",
            "regatta_external_key": "youth-nationals/2025",
            "regatta_name": "Youth Nationals",
            "start_date": None,
            "venue": "Mercer Lake",
            "parser_version": "timeteam-2026.07.1",
            "retrieved_at": RETRIEVED,
            "event_id": "50000000-0000-4000-8000-000000000001",
            "event_external_key": "race-8",
            "event_name": "Women's 8+ Final",
            "boat_class_raw": "8+",
            "age_class_raw": "U17",
            "round": "Final",
            "entry_id": time_entry,
            "entry_external_key": "crew-a",
            "club_source_name": "June Rowing",
            "provider_club_id": time_club,
            "crew_label": "A",
            "status": "Finished",
            "position": 1,
            "adjusted_position": 2,
            "time_ms": 30_001,
            "adjusted_time_ms": 31_002,
            "handicap_ms": 1_003,
            "delta_ms": 504,
        },
        {
            "organization_id": ORG_AMENDED,
            "slug": "amended-rowing",
            "regatta_id": "40000000-0000-4000-8000-000000000002",
            "source": "herenow",
            "regatta_external_key": "21464",
            "regatta_name": "Harbor Sprints",
            "start_date": "2025-06-15",
            "venue": "Harbor Course",
            "parser_version": "herenow-2026.07.1",
            "retrieved_at": RETRIEVED,
            "event_id": "50000000-0000-4000-8000-000000000002",
            "event_external_key": "flight-12",
            "event_name": "U-13 Mixed Quad",
            "boat_class_raw": "4x",
            "age_class_raw": "U13",
            "round": "Final",
            "entry_id": herenow_entry,
            "entry_external_key": "crew-h",
            "club_source_name": "Harbor Rowing",
            "provider_club_id": herenow_club,
            "crew_label": "Young Rower",
            "status": "Official",
            "position": 1,
            "adjusted_position": None,
            "time_ms": 420_000,
            "adjusted_time_ms": None,
            "handicap_ms": None,
            "delta_ms": None,
        },
    ]
    source["result_people"] = [
        {
            "result_person_id": "60000000-0000-4000-8000-000000000001",
            "entry_id": time_entry,
            "role": "stroke",
            "seat": 8,
            "person_name": "Sam Stroke",
        },
        {
            "result_person_id": "60000000-0000-4000-8000-000000000002",
            "entry_id": time_entry,
            "role": "rower",
            "seat": 7,
            "person_name": "Jane O'Neil",
        },
        {
            "result_person_id": "60000000-0000-4000-8000-000000000003",
            "entry_id": herenow_entry,
            "role": "competitor",
            "seat": None,
            "person_name": "Young Rower",
        },
    ]
    source["person_suppressions"] = [
        {
            "suppression_id": "70000000-0000-4000-8000-000000000001",
            "person_name_normalized": "jane oneil",
            "source": "time_team",
            "provider_club_id": time_club,
        }
    ]
    return source


def _organization(
    org_id: str,
    slug: str | None,
    name: str,
    ein: str,
    *,
    org_type: str = "community_club",
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
    filing: dict[str, Any],
    *,
    revenue: int,
    expenses: int,
    assets: int,
    liabilities: int,
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


def _person(
    name: str,
    comp: int,
    title: str,
    *,
    person_role_id: str | None = None,
    filing_id: str = "filing-june-2024",
    tax_year: int = 2024,
    begin: str = "2024-07-01",
    end: str = "2025-06-30",
    avg_hours_week: float | None = None,
    role_flags: list[str] | None = None,
    captured_at: str = RETRIEVED,
) -> dict[str, Any]:
    return {
        "person_role_id": person_role_id or f"person-{name}",
        "filing_id": filing_id,
        "person_name": name,
        "title": title,
        "reportable_compensation": comp,
        "other_compensation": 0,
        "deferred_compensation": 0,
        "nontaxable_benefits": 0,
        "related_organization_compensation": 0,
        "avg_hours_week": avg_hours_week,
        "role_flags": role_flags or [],
        "captured_at": captured_at,
        "organization_id": ORG_JUNE,
        "form_type": "990",
        "tax_period_begin": begin,
        "tax_period_end": end,
        "tax_year": tax_year,
        "amended_return": False,
        "retrieved_at": RETRIEVED,
    }


def _schema(name: str) -> dict[str, Any]:
    repo = Path(__file__).resolve().parents[2]
    return json.loads((repo / "packages" / "contracts" / "schemas" / name).read_text())


def test_structural_invariant_failures_are_collected_before_publish_writes() -> None:
    source = source_rows()
    source["organizations"][0]["slug"] = None
    source["organizations"][1]["slug"] = "stolen-slug"
    source["slug_history"] = [
        {"slug": "stolen-slug", "org_id": ORG_JUNE, "is_current": False}
    ]
    db = PublishFake(source)

    with pytest.raises(PublishInvariantError) as error:
        publish(db, generated_at=GENERATED)

    message = str(error.value)
    assert "has no slug" in message
    assert "stolen-slug" in message
    assert not any(name.startswith("read.") for name, _ in db.writes)
    assert not any("INSERT INTO ops.publish_snapshot" in query for query, _ in db.calls)


def test_filing_identity_failure_downgrades_to_under_review_instead_of_blocking() -> (
    None
):
    # A filer whose own arithmetic is wrong (net assets ≠ assets − liabilities)
    # publishes with that filing's facts under_review; the cohort still ships.
    source = source_rows()
    for fact in source["facts"]:
        if (
            fact["filing_id"] == "filing-june-2024"
            and fact["concept"] == "revenue_less_expenses"
        ):
            fact["amount"] = 9999
        if (
            fact["filing_id"] == "filing-june-2024"
            and fact["concept"] == "net_assets_eoy"
        ):
            fact["amount"] = 9999
    db = PublishFake(source)

    assert publish(db, generated_at=GENERATED) == "run-publish"

    reviews = db.table_writes("core.review_task")
    assert len(reviews) == 1
    assert reviews[0][0] == "filing-june-2024"
    details = json.loads(reviews[0][1])
    assert "revenue identity" in details["message"]
    assert "balance sheet identity" in details["message"]

    series = db.table_writes("read.org_financial_series")
    by_filing_state: dict[tuple[str, str], set[str]] = {}
    for row in series:
        ref = json.loads(row[9])
        key = (ref["source"]["filing_id"], row[2])
        by_filing_state.setdefault(key, set()).add(row[7])
    # Every fact and metric fed by the bad filing is under_review; the org's
    # clean 2022 filing and the other orgs stay verified.
    for (filing_id, _series_key), states in by_filing_state.items():
        expected = {"under_review"} if filing_id == "filing-june-2024" else {"verified"}
        if filing_id != "filing-june-2024":
            assert "under_review" not in states
        else:
            assert states == expected
    metric_rows = [row for row in series if row[2] == "operating_margin"]
    assert metric_rows and all(row[7] == "under_review" for row in metric_rows)

    # The snapshot facts sourced from the bad filing carry the state too.
    profiles = [json.loads(row[2]) for row in db.table_writes("read.org_profile")]
    june = next(payload for payload in profiles if payload["org_id"] == ORG_JUNE)
    assert all(
        fact["ref"]["quality_state"] == "under_review" for fact in june["snapshot"]
    )


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
    # People cover every filed year that reported officers, newest year first.
    assert [year["tax_year"] for year in june["people"]] == [2024, 2022]
    assert june["people"][0]["volunteer_count"] == 1
    assert june["people"][0]["compensated"][0]["name"] == "Alice Cox"
    assert june["people"][0]["compensated"][0]["avg_hours_week"] == 40
    assert june["people"][0]["compensated"][0]["role_flags"] == ["officer"]
    assert june["people"][1]["volunteer_count"] == 0
    assert june["people"][1]["compensated"][0]["name"] == "Old Salt"
    assert june["people"][1]["ref"]["period"]["label"] == "FY2022 (Jul 2022–Jun 2023)"
    postcard = next(
        payload for payload in payloads if payload["org_id"] == ORG_POSTCARD
    )
    assert postcard["snapshot"][0]["key"] == "filing_presence"

    refs = [json.loads(row[9]) for row in db.table_writes("read.org_financial_series")]
    assert refs
    assert all(not list(source_validator.iter_errors(ref)) for ref in refs)
    metric_ref = next(ref for ref in refs if ref["metric"] is not None)
    assert metric_ref["metric"] == {"key": "operating_margin", "version": 1}
    assert metric_ref["unit"] == "USD"


def test_regatta_build_enforces_linkage_pii_redaction_quality_and_contracts() -> None:
    source = result_source_rows()
    db = PublishFake(source)

    assert publish(db, generated_at=GENERATED) == "run-publish"

    linkage_sql = next(
        query
        for query, _ in db.calls
        if query.startswith("WITH latest_regatta AS MATERIALIZED")
    )
    assert "DISTINCT ON (r.source, r.external_key)" in linkage_sql
    assert "ORDER BY r.source, r.external_key, r.revision DESC" in linkage_sql
    assert "identifier.namespace = 'time_team_club'" in linkage_sql
    assert "identifier.verification_state = 'verified'" in linkage_sql
    assert "identifier.valid_to IS NULL" in linkage_sql
    assert "alias.alias_normalized" in linkage_sql
    assert "club.source <> 'time_team'" in linkage_sql
    assert "HAVING count(DISTINCT candidate.organization_id) = 1" in linkage_sql
    assert "JOIN unambiguous_links AS linked" in linkage_sql

    rows = db.table_writes("read.org_regatta_result")
    assert len(rows) == 8
    by_org = {ORG_JUNE: [], ORG_AMENDED: []}
    for row in rows:
        by_org[row[1]].append(row)
    time_crew = json.loads(by_org[ORG_JUNE][0][14])
    assert time_crew == [{"role": "stroke", "name": "Sam Stroke"}]
    assert all(row[19] == "under_review" for row in by_org[ORG_JUNE])
    assert all(
        json.loads(row[20])["quality_state"] == "under_review"
        for row in by_org[ORG_JUNE]
    )
    assert all(json.loads(row[14]) == [] for row in by_org[ORG_AMENDED])
    assert all(row[13] is None for row in by_org[ORG_AMENDED])

    emitted_time_metrics = {row[15]: row[16] for row in by_org[ORG_JUNE]}
    assert emitted_time_metrics == {
        "finish_time": 30.001,
        "adjusted_time": 31.002,
        "handicap": 1.003,
        "place": 1,
        "adjusted_place": 2,
        "margin": 0.504,
    }
    emitted_herenow_metrics = {row[15]: row[16] for row in by_org[ORG_AMENDED]}
    assert emitted_herenow_metrics == {"finish_time": 420, "place": 1}
    assert {
        "adjusted_time",
        "handicap",
        "adjusted_place",
        "margin",
    }.isdisjoint(emitted_herenow_metrics)
    assert {row[9] for row in rows} == {"crew-a", "crew-h"}

    reviews = db.table_writes("core.review_task")
    assert len(reviews) == 1
    assert reviews[0][0] == source["regatta_results"][0]["entry_id"]
    assert "outside 60s" in json.loads(reviews[0][1])["reasons"][0]

    build = _assemble(
        source,
        generated=GENERATED,
        parser_version="cm-test",
    )
    payload_validator = Draft202012Validator(
        _schema("org-regatta-payload.v1.schema.json"),
        format_checker=FormatChecker(),
    )
    ref_validator = Draft202012Validator(
        _schema("result-ref.v1.schema.json"),
        format_checker=FormatChecker(),
    )
    assert len(build["regatta_payloads"]) == 2
    assert all(
        not list(payload_validator.iter_errors(wrapper["payload"]))
        for wrapper in build["regatta_payloads"]
    )
    assert all(
        not list(ref_validator.iter_errors(row["source_ref"]))
        for row in build["regatta_rows"]
    )
    time_payload = next(
        wrapper["payload"]
        for wrapper in build["regatta_payloads"]
        if wrapper["organization_id"] == ORG_JUNE
    )
    time_ref = time_payload["seasons"][0]["regattas"][0]["events"][0]["entries"][0][
        "results"
    ][0]["ref"]
    assert time_payload["seasons"][0]["season"] == 2025
    assert (
        time_payload["seasons"][0]["regattas"][0]["events"][0]["entries"][0][
            "entry_external_key"
        ]
        == "crew-a"
    )
    assert (
        time_ref["source"]["provider_url"]
        == "https://usrowing.regatta.time-team.com/youth-nationals/2025/races"
    )
    herenow_payload = next(
        wrapper["payload"]
        for wrapper in build["regatta_payloads"]
        if wrapper["organization_id"] == ORG_AMENDED
    )
    assert (
        herenow_payload["seasons"][0]["regattas"][0]["events"][0]["entries"][0]["crew"]
        == []
    )
    assert (
        herenow_payload["seasons"][0]["regattas"][0]["events"][0]["entries"][0][
            "crew_label"
        ]
        is None
    )

    stats = json.loads(db.table_writes("ingest_run_update")[-1][2])
    assert stats["regatta_orgs_published"] == 2
    assert stats["regatta_rows_published"] == 8
    assert stats["regatta_entries_suppressed_names"] == 1
    assert stats["regatta_entries_u13_redacted"] == 1
    assert stats["regatta_downgrades"] == 1
    assert stats["regatta_clubs_ambiguous"] == 0


def test_regatta_fatal_invariants_catch_poisoned_pii_and_duplicate_rows() -> None:
    source = result_source_rows()
    build = _assemble(
        source,
        generated=GENERATED,
        parser_version="cm-test",
    )
    poisoned = deepcopy(build)
    time_payload = next(
        wrapper["payload"]
        for wrapper in poisoned["regatta_payloads"]
        if wrapper["organization_id"] == ORG_JUNE
    )
    payload_entry = time_payload["seasons"][0]["regattas"][0]["events"][0]["entries"][0]
    payload_entry["crew"] = [
        *payload_entry["crew"],
        {"role": "rower", "name": "Jane O'Neil"},
    ]
    assert all(
        member["name"] != "Jane O'Neil"
        for context in poisoned["regatta_crew_contexts"]
        for member in context["crew"]
    )
    poisoned["directories"][0]["aliases"].append("Sam Stroke")
    poisoned["regatta_rows"].append(deepcopy(poisoned["regatta_rows"][0]))

    failures, _ = _invariant_failures(
        source["organizations"],
        source["facts"],
        source["slug_history"],
        build=poisoned,
        suppressions=source["person_suppressions"],
        result_people=source["result_people"],
    )

    assert any("suppressed result person leaked" in failure for failure in failures)
    assert any("appears in directory" in failure for failure in failures)
    assert any("duplicate regatta result key" in failure for failure in failures)


def test_regatta_pii_invariant_scans_crew_label_and_payload_club_name() -> None:
    source = result_source_rows()
    build = _assemble(
        source,
        generated=GENERATED,
        parser_version="cm-test",
    )
    poisoned = deepcopy(build)
    time_row = next(
        row for row in poisoned["regatta_rows"] if row["organization_id"] == ORG_JUNE
    )
    time_row["crew_label"] = "Sam Stroke"
    herenow_payload = next(
        wrapper["payload"]
        for wrapper in poisoned["regatta_payloads"]
        if wrapper["organization_id"] == ORG_AMENDED
    )
    herenow_payload["seasons"][0]["regattas"][0]["events"][0]["entries"][0][
        "club_display_name"
    ] = "Young Rower"

    failures, _ = _invariant_failures(
        source["organizations"],
        source["facts"],
        source["slug_history"],
        build=poisoned,
        suppressions=source["person_suppressions"],
        result_people=source["result_people"],
    )

    assert any("appears in crew_label" in failure for failure in failures)
    assert any("payload club_display_name" in failure for failure in failures)


def test_place_with_non_finished_status_downgrades_the_whole_entry() -> None:
    source = result_source_rows()
    source["regatta_results"][0]["time_ms"] = 420_000
    source["regatta_results"][0]["status"] = "DNS"

    build = _assemble(
        source,
        generated=GENERATED,
        parser_version="cm-test",
    )

    time_rows = [
        row for row in build["regatta_rows"] if row["organization_id"] == ORG_JUNE
    ]
    assert time_rows
    assert all(row["quality_state"] == "under_review" for row in time_rows)
    assert build["regatta_review_findings"][0]["details"]["reasons"] == [
        "place is present for non-finished status 'DNS'"
    ]


def test_ambiguous_provider_club_is_not_published_and_opens_club_link_review() -> None:
    source = result_source_rows()
    ambiguous_club = source["regatta_results"][1]["provider_club_id"]
    source["regatta_results"] = [
        row
        for row in source["regatta_results"]
        if row["provider_club_id"] != ambiguous_club
    ]
    source["ambiguous_regatta_clubs"] = [
        {
            "provider_club_id": ambiguous_club,
            "source": "herenow",
            "external_key": "harbor-provider-42",
            "candidate_organization_count": 2,
        }
    ]
    db = PublishFake(source)

    assert publish(db, generated_at=GENERATED) == "run-publish"

    assert all(
        row[1] != ORG_AMENDED for row in db.table_writes("read.org_regatta_result")
    )
    club_review = next(
        row for row in db.table_writes("core.review_task") if row[0] == ambiguous_club
    )
    details = json.loads(club_review[1])
    assert details == {
        "reason": "provider club matches multiple organizations",
        "source": "herenow",
        "candidate_organization_count": 2,
    }
    assert all(
        person["person_name"] not in club_review[1]
        for person in source["result_people"]
    )
    stats = json.loads(db.table_writes("ingest_run_update")[-1][2])
    assert stats["regatta_clubs_ambiguous"] == 1


def test_distinct_null_label_entries_do_not_collide() -> None:
    source = result_source_rows()
    second_entry = deepcopy(source["regatta_results"][1])
    second_entry["entry_id"] = "20000000-0000-4000-8000-000000000003"
    second_entry["entry_external_key"] = "crew-h-2"
    source["regatta_results"].append(second_entry)

    build = _assemble(
        source,
        generated=GENERATED,
        parser_version="cm-test",
    )
    herenow_rows = [
        row for row in build["regatta_rows"] if row["organization_id"] == ORG_AMENDED
    ]
    assert {row["entry_external_key"] for row in herenow_rows} == {
        "crew-h",
        "crew-h-2",
    }
    assert all(row["crew_label"] is None for row in herenow_rows)
    failures, _ = _invariant_failures(
        source["organizations"],
        source["facts"],
        source["slug_history"],
        build=build,
        suppressions=source["person_suppressions"],
        result_people=source["result_people"],
    )
    assert not any("duplicate regatta result key" in failure for failure in failures)


def test_regatta_without_derivable_season_fails_as_publish_invariant() -> None:
    source = result_source_rows()
    source["regatta_results"][1]["start_date"] = None
    db = PublishFake(source)

    with pytest.raises(
        PublishInvariantError,
        match="has no start_date or Time-Team year",
    ):
        publish(db, generated_at=GENERATED)

    assert not any("INSERT INTO ops.publish_snapshot" in query for query, _ in db.calls)


@pytest.mark.parametrize(
    "label",
    [
        "U13",
        "U 13",
        "Under 13",
        "Under-13",
        "WU13",
        "MU13",
        "BU13",
        "GU13",
        "U13B",
        "U13G",
        "U13x",
        "13U",
        "U10",
        "U11",
        "U12",
    ],
)
def test_u13_detection_covers_provider_forms_and_ages_10_through_13(
    label: str,
) -> None:
    assert _is_u13_event(label, None)


def test_u13_detection_does_not_redact_older_age_classes() -> None:
    assert not _is_u13_event("U14", "Women's Under-17")


@pytest.mark.parametrize(
    ("person_name", "suppression_name"),
    [
        ("Andre\u0301 OBrien", "André OBrien"),
        ("OBrien Andrew", "Andrew OBrien"),
    ],
)
def test_suppression_name_matching_is_unicode_symmetric_and_order_insensitive(
    person_name: str,
    suppression_name: str,
) -> None:
    suppression = {
        "person_name_normalized": suppression_name,
        "source": "time_team",
        "provider_club_id": "club-1",
    }
    assert _suppression_matches(
        person_name,
        "time_team",
        "club-1",
        [suppression],
    )
    assert _suppression_matches(
        suppression_name,
        "time_team",
        "club-1",
        [{**suppression, "person_name_normalized": person_name}],
    )


def test_club_scoped_suppression_is_applied_end_to_end() -> None:
    source = result_source_rows()
    db = PublishFake(source)

    assert publish(db, generated_at=GENERATED) == "run-publish"

    time_rows = [
        row for row in db.table_writes("read.org_regatta_result") if row[1] == ORG_JUNE
    ]
    assert time_rows
    assert all(
        json.loads(row[14]) == [{"role": "stroke", "name": "Sam Stroke"}]
        for row in time_rows
    )


def test_empty_regatta_linkage_publishes_zero_results() -> None:
    db = PublishFake(source_rows())

    assert publish(db, generated_at=GENERATED) == "run-publish"

    assert db.table_writes("read.org_regatta_result") == []
    assert not any(
        "FROM core.result_person AS person" in query for query, _ in db.calls
    )
    stats = json.loads(db.table_writes("ingest_run_update")[-1][2])
    assert stats["regatta_orgs_published"] == 0
    assert stats["regatta_rows_published"] == 0


def test_regatta_read_model_migration_is_snapshot_scoped_and_null_safe() -> None:
    migration = (
        Path(__file__).resolve().parents[2]
        / "db"
        / "migrations"
        / "017_read_regatta.sql"
    ).read_text()

    assert "snapshot_id uuid NOT NULL REFERENCES ops.publish_snapshot(id)" in migration
    assert "entry_external_key text NOT NULL" in migration
    assert (
        "event_key,\n    entry_external_key,\n    COALESCE(crew_label, ''),"
        in migration
    )
    assert "COALESCE(crew_label, '')" in migration
    assert "ON read.org_regatta_result (snapshot_id, organization_id)" in migration
    assert (
        "ON read.org_regatta_result (snapshot_id, organization_id, season)" in migration
    )
    assert "PERFORM app.apply_phase1_role_grants()" in migration
    assert "-- migrate:down\n\nDROP TABLE read.org_regatta_result;" in migration


def test_people_payload_shows_only_the_newest_capture_per_person() -> None:
    earlier = "2026-07-19T12:00:00Z"
    source = source_rows()
    source["people"] = [
        _person(
            "Alice Cox",
            100,
            "Coach",
            person_role_id="alice-sparse",
            captured_at=earlier,
        ),
        _person(
            "Alice Cox",
            100,
            "Coach",
            person_role_id="alice-rich",
            avg_hours_week=12.5,
            role_flags=["officer"],
        ),
        _person(
            "Vera Volunteer",
            0,
            "Director",
            person_role_id="vera-sparse",
            captured_at=earlier,
        ),
        _person(
            "Vera Volunteer",
            0,
            "Director",
            person_role_id="vera-rich",
            avg_hours_week=1,
        ),
    ]
    db = PublishFake(source)

    publish(db, generated_at=GENERATED)

    payloads = [json.loads(row[2]) for row in db.table_writes("read.org_profile")]
    june = next(payload for payload in payloads if payload["org_id"] == ORG_JUNE)
    year = june["people"][0]
    assert [person["name"] for person in year["compensated"]] == ["Alice Cox"]
    assert year["compensated"][0]["avg_hours_week"] == 12.5
    assert year["compensated"][0]["role_flags"] == ["officer"]
    assert year["volunteer_count"] == 1


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
def test_coverage_state_precedence(
    forms: list[dict[str, Any]], postcards: list[dict[str, Any]], expected: str
) -> None:
    assert _coverage_state(forms, postcards) == expected


def test_publish_flip_is_one_atomic_cte_statement_and_stats_are_collected() -> None:
    db = PublishFake()
    publish(db, generated_at=GENERATED)
    flips = [
        query
        for query, _ in db.calls
        if query.startswith("WITH target AS MATERIALIZED")
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
        "identity_downgrades": 0,
        "regatta_orgs_published": 0,
        "regatta_rows_published": 0,
        "regatta_entries_suppressed_names": 0,
        "regatta_entries_u13_redacted": 0,
        "regatta_downgrades": 0,
        "regatta_clubs_ambiguous": 0,
        "gc_snapshots_deleted": 1,
    }


def test_gc_retains_exactly_three_snapshots_and_preserves_slug_history() -> None:
    db = PublishFake()
    publish(db, generated_at=GENERATED)

    assert db.snapshot_ids == ["old-2", "old-3", "new-4"]
    assert db.read_snapshot_ids == {"old-2", "old-3", "new-4"}
    gc_query = next(
        query for query, _ in db.calls if query.startswith("WITH stale AS MATERIALIZED")
    )
    assert "OFFSET 3" in gc_query
    assert "UPDATE read.org_slug_history" in gc_query
    assert "DELETE FROM read.org_regatta_result" in gc_query
    assert "DELETE FROM ops.publish_snapshot" in gc_query


def test_invalid_profile_contract_blocks_snapshot_creation() -> None:
    source = source_rows()
    source["organizations"][0]["org_type"] = "not_a_real_type"
    db = PublishFake(source)

    with pytest.raises(PublishInvariantError, match="org_type"):
        publish(db, generated_at=GENERATED)

    assert not any("INSERT INTO ops.publish_snapshot" in query for query, _ in db.calls)
