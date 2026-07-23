from __future__ import annotations

import importlib
import json
import math
from decimal import Decimal
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

from crewgraphs.jobs.derive_ratings import (
    derive_ratings,
    eligibility_met,
    fit_plackett_luce,
    rank_event_rows,
    register,
)


ELIGIBILITY_RULE = {
    "min_ranked_fields": 5,
    "min_distinct_regattas": 2,
    "min_field_size": 3,
}


class FakeRatingsDb:
    """SQL-shaped in-memory boundary for the ratings job."""

    def __init__(
        self,
        rows: list[dict[str, Any]],
        *,
        links: dict[str, str] | None = None,
        rule: dict[str, int] | None = None,
    ) -> None:
        self.rows = rows
        self.links = links or {}
        self.rule = rule or dict(ELIGIBILITY_RULE)
        self.ratings: list[dict[str, Any]] = []
        self.review_tasks: list[dict[str, Any]] = []
        self.final_stats: dict[str, Any] = {}
        self.calls: list[tuple[str, tuple[object, ...]]] = []
        self._counter = 0

    def execute(self, query: str, params: object = None) -> list[dict[str, Any]]:
        values = tuple(params or ())
        self.calls.append((query, values))
        if "INSERT INTO ops.ingest_run" in query:
            self._counter += 1
            return [{"id": f"run-ratings-{self._counter}"}]
        if "FROM core.metric_definition" in query:
            return [
                {
                    "metric_key": "rating_rof",
                    "version": 1,
                    "eligibility_rule": self.rule,
                    "status": "draft",
                }
            ]
        if "WITH latest_regatta AS MATERIALIZED" in query:
            if not values:
                return list(self.rows)
            return [row for row in self.rows if row["season"] == values[0]]
        if "WITH link_candidates AS MATERIALIZED" in query:
            return [
                {"provider_club_id": club, "organization_id": organization}
                for club, organization in sorted(self.links.items())
            ]
        if query.strip().startswith("INSERT INTO core.program_rating"):
            (
                organization_id,
                season,
                boat_class,
                age_bracket,
                gender,
                metric_key,
                metric_version,
                rating,
                rating_sigma,
                ranked_fields,
                distinct_regattas,
                field_sizes,
                computation_version,
                is_eligible,
                input_summary,
            ) = values
            identity = (
                organization_id,
                season,
                boat_class,
                age_bracket,
                gender,
                metric_key,
                metric_version,
                computation_version,
            )
            if any(row["identity"] == identity for row in self.ratings):
                return []
            row = {
                "id": f"rating-{len(self.ratings) + 1}",
                "identity": identity,
                "organization_id": organization_id,
                "season": season,
                "boat_class": boat_class,
                "age_bracket": age_bracket,
                "gender": gender,
                "metric_key": metric_key,
                "metric_version": metric_version,
                "rating": rating,
                "rating_sigma": rating_sigma,
                "ranked_fields": ranked_fields,
                "distinct_regattas": distinct_regattas,
                "field_sizes": json.loads(field_sizes),
                "computation_version": computation_version,
                "eligibility_met": is_eligible,
                "input_summary": json.loads(input_summary),
            }
            self.ratings.append(row)
            return [{"id": row["id"]}]
        if query.strip().startswith("INSERT INTO core.review_task"):
            wanted = json.loads(values[1])
            if not any(
                task["entity_id"] == values[0]
                and task["details"].get("fingerprint") == values[3]
                for task in self.review_tasks
            ):
                self.review_tasks.append({"entity_id": values[0], "details": wanted})
            return []
        if "UPDATE ops.ingest_run" in query:
            self.final_stats = json.loads(values[2])
            return []
        raise AssertionError(query)


def _field_rows(
    event_number: int,
    ranking: tuple[str, ...],
    *,
    regatta: str,
    season: int = 2025,
    age_bracket: str = "open",
    adjusted_times: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    return [
        {
            "event_id": f"event-{event_number}",
            "event_external_key": f"event-{event_number}",
            "entry_id": f"entry-{event_number}-{club}",
            "entry_external_key": f"entry-{event_number}-{club}",
            "provider_club_id": club,
            "entry_raw": {"is_ooc": False},
            "status": "Finished",
            "position": position,
            "adjusted_position": None,
            "time_ms": 100_000 + position * 1_000,
            "adjusted_time_ms": (
                adjusted_times[club] if adjusted_times is not None else None
            ),
            "source": "time_team",
            "regatta_external_key": regatta,
            "season": season,
            "mapping_version": 3,
            "boat_class": "4x",
            "age_bracket": age_bracket,
            "gender": "mixed",
            "mapping_key": "canonical-4x",
        }
        for position, club in enumerate(ranking, start=1)
    ]


def _balanced_rows() -> list[dict[str, Any]]:
    # All six permutations make a connected, exactly balanced PL field set.
    rankings = [
        ("A", "B", "C"),
        ("A", "C", "B"),
        ("B", "A", "C"),
        ("B", "C", "A"),
        ("C", "A", "B"),
        ("C", "B", "A"),
    ]
    return [
        row
        for number, ranking in enumerate(rankings, start=1)
        for row in _field_rows(
            number,
            ranking,
            regatta="regatta-one" if number <= 3 else "regatta-two",
        )
    ]


def _without_ids(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{key: value for key, value in row.items() if key != "id"} for row in rows]


def test_pl_mm_orders_a_hand_checkable_three_competitor_round_robin() -> None:
    fit = fit_plackett_luce([("A", "B"), ("A", "C"), ("B", "C")])

    assert fit.converged
    assert fit.strengths["A"] > fit.strengths["B"] > fit.strengths["C"] > 0


def test_one_mm_step_uses_numeric_multi_competitor_suffix_exposure() -> None:
    fit = fit_plackett_luce([("A", "B", "C")], max_iterations=1)

    assert not fit.converged
    # From unit starting strengths, the two choice-stage suffix denominators
    # are 3 and 2. Exposures including the 0.1 prior are therefore
    # A=0.1+1/3 and B=C=0.1+1/3+1/2.
    assert fit.strengths == pytest.approx(
        {
            "A": 1.1 / (0.1 + 1 / 3),
            "B": 1.1 / (0.1 + 1 / 3 + 1 / 2),
            "C": 0.1 / (0.1 + 1 / 3 + 1 / 2),
        }
    )


def test_two_competitor_fit_matches_smoothed_closed_form() -> None:
    fit = fit_plackett_luce([("A", "B"), ("A", "B"), ("A", "B"), ("B", "A")])

    assert fit.converged
    assert fit.strengths["A"] / fit.strengths["B"] == pytest.approx(
        (3 + 0.1) / (1 + 0.1), rel=1e-10
    )


def test_transitivity_sanity() -> None:
    fit = fit_plackett_luce([("A", "B", "C")])

    assert fit.converged
    assert fit.strengths["A"] > fit.strengths["B"] > fit.strengths["C"]


def test_known_nonfinishers_are_excluded_even_with_stale_order_values() -> None:
    rows = _field_rows(1, ("A", "B", "C", "D"), regatta="regatta")
    rows[1]["status"] = "DNF"
    rows[1]["position"] = 2
    rows[1]["time_ms"] = 102_000

    ranked = rank_event_rows(rows, min_field_size=3)

    assert ranked == (("A", "C", "D"), False)


def test_ooc_and_scratch_rows_are_excluded_but_opaque_integer_status_ranks() -> None:
    rows = _field_rows(1, ("A", "B", "C", "D", "E"), regatta="time-team")
    for row in rows:
        row["status"] = "4"
    rows[1]["entry_raw"] = {"is_ooc": True}
    rows[2]["status"] = "Scratch"

    assert rank_event_rows(rows, min_field_size=3) == (("A", "D", "E"), False)

    db = FakeRatingsDb(
        rows,
        links={"A": "org-a"},
        rule={
            "min_ranked_fields": 1,
            "min_distinct_regattas": 1,
            "min_field_size": 3,
        },
    )
    derive_ratings(db)

    assert db.final_stats["rows_excluded_ooc"] == 1
    assert db.final_stats["rows_excluded_status"] == 1
    assert db.final_stats["fields_ranked"] == 1


def test_positionless_field_falls_back_to_finish_time() -> None:
    rows = _field_rows(1, ("A", "B", "C"), regatta="herenow")
    for row in rows:
        row["position"] = None
    rows[0]["time_ms"] = 103_000
    rows[1]["time_ms"] = 101_000
    rows[2]["time_ms"] = 102_000

    ranked = rank_event_rows(rows, min_field_size=3)

    assert ranked == (("B", "C", "A"), False)


def test_masters_fields_use_published_adjusted_time_order() -> None:
    rows = _field_rows(
        1,
        ("A", "B", "C"),
        regatta="masters",
        age_bracket="masters",
        adjusted_times={"A": 110_000, "B": 100_000, "C": 105_000},
    )

    ranked = rank_event_rows(rows, min_field_size=3)

    assert ranked == (("B", "C", "A"), True)


def test_partial_masters_adjustments_fall_back_without_inventing_last_place() -> None:
    rows = _field_rows(
        1,
        ("A", "B", "C", "D"),
        regatta="masters",
        age_bracket="masters",
        adjusted_times={"A": 110_000, "B": 90_000, "C": 105_000, "D": 100_000},
    )
    rows[1]["position"] = None
    rows[1]["time_ms"] = None
    rows[2]["adjusted_time_ms"] = None

    ranked = rank_event_rows(rows, min_field_size=3)

    assert ranked == (("A", "C", "D"), False)
    assert "B" not in ranked[0]


def test_incomplete_raw_and_adjusted_order_skips_field_with_stat() -> None:
    rows = _field_rows(
        1,
        ("A", "B", "C"),
        regatta="masters",
        age_bracket="masters",
        adjusted_times={"A": 103_000, "B": 102_000, "C": 101_000},
    )
    rows[1]["position"] = None
    rows[1]["time_ms"] = None
    rows[2]["adjusted_time_ms"] = None

    assert rank_event_rows(rows, min_field_size=3) is None

    db = FakeRatingsDb(
        rows,
        rule={
            "min_ranked_fields": 1,
            "min_distinct_regattas": 1,
            "min_field_size": 3,
        },
    )
    derive_ratings(db)

    assert db.final_stats["fields_skipped_incomplete_order"] == 1
    assert db.final_stats["fields_ranked"] == 0


def test_eligibility_evaluates_every_definition_threshold() -> None:
    assert eligibility_met(
        ranked_fields=5,
        distinct_regattas=2,
        field_sizes=[3, 3, 4, 4, 6],
        rule=ELIGIBILITY_RULE,
    )
    assert not eligibility_met(
        ranked_fields=4,
        distinct_regattas=2,
        field_sizes=[3, 3, 4, 4],
        rule=ELIGIBILITY_RULE,
    )
    assert not eligibility_met(
        ranked_fields=5,
        distinct_regattas=1,
        field_sizes=[3] * 5,
        rule=ELIGIBILITY_RULE,
    )
    assert not eligibility_met(
        ranked_fields=5,
        distinct_regattas=2,
        field_sizes=[2, 3, 3, 3, 3],
        rule=ELIGIBILITY_RULE,
    )


def test_job_is_deterministic_and_unlinked_clubs_still_inform_strength() -> None:
    links = {"A": "org-a", "B": "org-b"}  # C is intentionally identity-agnostic.
    first = FakeRatingsDb(_balanced_rows(), links=links)
    second = FakeRatingsDb(_balanced_rows(), links=links)

    derive_ratings(first)
    derive_ratings(second)

    assert _without_ids(first.ratings) == _without_ids(second.ratings)
    assert len(first.ratings) == 2
    assert {row["organization_id"] for row in first.ratings} == {"org-a", "org-b"}
    assert all(row["ranked_fields"] == 6 for row in first.ratings)
    assert all(row["distinct_regattas"] == 2 for row in first.ratings)
    assert all(row["eligibility_met"] for row in first.ratings)
    assert all(
        row["rating_sigma"] == Decimal(f"{1 / math.sqrt(6):.6f}")
        for row in first.ratings
    )
    assert all(
        row["input_summary"]["comparison_pool_provider_programs"] == 3
        for row in first.ratings
    )
    assert all(
        row["input_summary"]["method"] == "appearance_weighted_mean"
        for row in first.ratings
    )
    assert first.final_stats == second.final_stats
    assert first.final_stats["fields_ranked"] == 6
    assert first.final_stats["programs_rated"] == 2
    assert first.final_stats["programs_eligible"] == 2
    assert first.final_stats["orgs_linked_rated"] == 2
    assert first.final_stats["convergence_iterations_max"] == 1
    result_query = next(
        query
        for query, _ in first.calls
        if "WITH latest_regatta AS MATERIALIZED" in query
    )
    assert "max(mapping_version)" in result_query
    assert (
        "latest_mapping.mapping_version = classification.mapping_version"
        in result_query
    )
    assert "entry.raw AS entry_raw" in result_query
    assert "core.organization" not in result_query


def test_org_aggregation_flags_same_field_linked_club_self_competition() -> None:
    db = FakeRatingsDb(
        _balanced_rows(),
        links={"A": "org-shared", "B": "org-shared", "C": "org-c"},
    )

    derive_ratings(db)

    by_org = {row["organization_id"]: row for row in db.ratings}
    assert by_org["org-shared"]["input_summary"]["method"] == (
        "appearance_weighted_mean"
    )
    assert by_org["org-shared"]["input_summary"]["self_competition"] is True
    assert by_org["org-c"]["input_summary"]["self_competition"] is False


def test_new_computation_version_inserts_superseding_rows_without_rewrites() -> None:
    db = FakeRatingsDb(_balanced_rows(), links={"A": "org-a"})

    derive_ratings(db, computation_version="pl-mm-v1")
    first = dict(db.ratings[0])
    derive_ratings(db, computation_version="pl-mm-v1")
    derive_ratings(db, computation_version="pl-mm-v2")

    assert len(db.ratings) == 2
    assert db.ratings[0] == first
    assert [row["computation_version"] for row in db.ratings] == [
        "pl-mm-v1",
        "pl-mm-v2",
    ]


def test_dry_run_emits_coverage_table_without_rating_writes() -> None:
    db = FakeRatingsDb(_balanced_rows(), links={"A": "org-a"})

    summary = derive_ratings(db, dry_run=True)

    assert db.ratings == []
    assert db.review_tasks == []
    assert "### Dry-run coverage" in summary
    assert "| 2025 | 4x | open | mixed | 6 | 3 | 1 | 1 | True |" in summary


def test_convergence_failure_opens_one_review_and_stores_no_rating(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = importlib.import_module("crewgraphs.jobs.derive_ratings")
    monkeypatch.setattr(module, "MM_MAX_ITERATIONS", 1)
    rows = [
        row
        for event in range(1, 3)
        for row in _field_rows(event, ("A", "B", "C"), regatta=f"regatta-{event}")
    ]
    db = FakeRatingsDb(
        rows,
        links={"A": "org-a"},
        rule={
            "min_ranked_fields": 1,
            "min_distinct_regattas": 1,
            "min_field_size": 3,
        },
    )

    derive_ratings(db)
    derive_ratings(db)

    assert db.ratings == []
    assert len(db.review_tasks) == 1
    assert db.review_tasks[0]["details"]["iterations"] == 1
    assert len(db.review_tasks[0]["details"]["fingerprint"]) == 64
    assert db.final_stats["convergence_failures"] == 1
    review_queries = [
        query
        for query, _ in db.calls
        if query.strip().startswith("INSERT INTO core.review_task")
    ]
    assert len(review_queries) == 2
    assert all("WHERE NOT EXISTS" in query for query in review_queries)


def test_register_exposes_filters_and_dry_run_without_root_cli_changes() -> None:
    app = typer.Typer()
    register(app)

    result = CliRunner().invoke(app, ["derive-ratings", "--help"])

    assert result.exit_code == 0
    assert "--season" in result.output
    assert "--computation-version" in result.output
    assert "--dry-run" in result.output
