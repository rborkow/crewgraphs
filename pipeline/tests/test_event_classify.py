from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import typer
from typer.testing import CliRunner

from crewgraphs.event_map import load_event_map
from crewgraphs.jobs.event_classify import UNMAPPED_TASK_TYPE, event_classify, register
from crewgraphs.jobs.herenow import _flights, _reference_index
from crewgraphs.jobs.regattatiming import parse_page


class EventClassifyDb:
    def __init__(self, events: list[dict[str, Any]]) -> None:
        self.events = events
        self.classifications: list[dict[str, Any]] = []
        self.review_tasks: list[dict[str, Any]] = []
        self.final_stats: dict[str, Any] = {}

    def execute(self, query: str, params: object = None) -> list[dict[str, Any]]:
        values = tuple(params or ())
        if "INSERT INTO ops.ingest_run" in query:
            return [{"id": "run-events"}]
        if "WITH latest_regatta" in query:
            version = str(values[0])
            return [
                {
                    **event,
                    "has_classification": any(
                        item["event_id"] == event["id"] and item["mapping_version"] == version
                        for item in self.classifications
                    ),
                }
                for event in self.events
            ]
        if "INSERT INTO core.event_classification" in query:
            event_id, version, boat, age, gender, key = values
            if not any(item["event_id"] == event_id and item["mapping_version"] == version for item in self.classifications):
                self.classifications.append(
                    {
                        "event_id": event_id,
                        "mapping_version": version,
                        "boat_class": boat,
                        "age_bracket": age,
                        "gender": gender,
                        "mapping_key": key,
                    }
                )
            return []
        if "details->'pattern'" in query:
            task_type, source, pattern = values
            return [{"exists": 1}] if any(
                task["task_type"] == task_type
                and task["details"]["source"] == source
                and task["details"]["pattern"] == json.loads(pattern)
                for task in self.review_tasks
            ) else []
        if "INSERT INTO core.review_task" in query:
            event_id, task_type, details = values
            self.review_tasks.append(
                {
                    "entity_type": "regatta_event_pattern",
                    "entity_id": event_id,
                    "task_type": task_type,
                    "details": json.loads(details),
                }
            )
            return []
        if "UPDATE ops.ingest_run" in query:
            self.final_stats = json.loads(values[2])
            return []
        raise AssertionError(query)


def _event(
    ident: str,
    *,
    source: str = "herenow",
    name: str = "Mens Masters 1x 50+ (D+)",
    event_code: str | None = None,
    boat_class_raw: str | None = None,
    age_class_raw: str | None = None,
    gender_raw: str | None = None,
) -> dict[str, Any]:
    return {
        "id": ident,
        "source": source,
        "name": name,
        "event_code": event_code,
        "boat_class_raw": boat_class_raw,
        "age_class_raw": age_class_raw,
        "gender_raw": gender_raw,
    }


def test_real_fixture_event_patterns_have_full_coverage() -> None:
    fixtures = Path(__file__).parent / "fixtures"
    flights_payload = json.loads((fixtures / "herenow/21464-flights-real.json").read_text(encoding="utf-8"))
    fixture_events = [
        _event(
            f"hn-{index}",
            name=str(flight["Name"]),
            event_code=flight.get("Code"),
            boat_class_raw=(flight.get("Event") or {}).get("BoatClass"),
            age_class_raw=(flight.get("Event") or {}).get("AgeClass"),
            gender_raw=(flight.get("Event") or {}).get("Gender"),
        )
        for index, flight in enumerate(_flights(flights_payload, _reference_index(flights_payload)))
    ]
    time_team_patterns = {
        pair
        for fixture in (fixtures / "timeteam").glob("*.json")
        for pair in _time_team_patterns(json.loads(fixture.read_text(encoding="utf-8")))
    }
    fixture_events.extend(
        _event(f"tt-{index}", source="time_team", event_code=code, name=name)
        for index, (code, name) in enumerate(sorted(time_team_patterns))
    )
    parsed = parse_page((fixtures / "regattatiming/625-real.html").read_bytes())
    fixture_events.extend(
        _event(f"rt-{event.event_id}", source="regattatiming", event_code=event.number, name=event.name)
        for event in parsed.events
    )
    event_map = load_event_map()

    results = [event_map.classify(event) for event in fixture_events]

    assert all(results)
    expected = {
        "Mens Masters 1x 50+ (D+) TT": ("1x", "masters_unspecified", "men"),
        "Women's Masters 8+ (A-M) TT": ("8+", "masters_unspecified", "women"),
        "U-15 Men’s 1x TT": ("1x", "u15", "men"),
        "Mens Ltwt Varsity 2nd 8+": ("8+", "collegiate", "men"),
    }
    actual = {
        event["name"]: (result.boat_class, result.age_bracket, result.gender)
        for event, result in zip(fixture_events, results, strict=True)
    }
    assert {name: actual[name] for name in expected} == expected


def test_structural_gender_and_age_gauntlet() -> None:
    event_map = load_event_map()

    cases = {
        # A bare flight letter cannot override an explicit gender word.
        "B/Womens": ({"event_code": "B", "name": "Womens Masters 1x (C)"}, ("1x", "masters_c", "women")),
        "G/Mens": ({"event_code": "G", "name": "Mens U16 8+"}, ("8+", "u16", "men")),
        "bare flight": ({"event_code": "B Final", "name": "Masters 8+ (A-M)"}, None),
        # A populated provider field wins over conflicting display text.
        "raw wins": ({"event_code": "W 8+", "name": "Mens Youth 8+", "gender_raw": "W"}, ("8+", "u19_youth", "women")),
        "masters exact": ({"name": "Mens Masters 1x (D)"}, ("1x", "masters_d", "men")),
        "masters open ended": ({"name": "Mens Masters 1x (D+)"}, ("1x", "masters_unspecified", "men")),
        "collegiate novice": ({"name": "Womens Collegiate Novice 8+"}, ("8+", "collegiate", "women")),
        "novice unaged": ({"name": "Men's Novice 1x"}, None),
        "M1x": ({"event_code": "M1x", "name": "Youth"}, ("1x", "u19_youth", "men")),
        "W2-": ({"event_code": "W2-", "name": "Youth"}, ("2-", "u19_youth", "women")),
        "W8+": ({"event_code": "W8+", "name": "Youth"}, ("8+", "u19_youth", "women")),
        "LM2x": ({"event_code": "LM2x", "name": "Youth"}, ("2x", "u19_youth", "men")),
        "junior 16": ({"name": "Mens Junior 16 8+"}, ("8+", "u16", "men")),
        "PR1": ({"event_code": "PR1 M 1x", "name": ""}, None),
        "mixed missing age": ({"name": "Directors Challenge Mixed 8+"}, None),
    }

    for _label, (event, expected) in cases.items():
        result = event_map.classify(event)
        actual = None if result is None else (result.boat_class, result.age_bracket, result.gender)
        assert actual == expected


def _time_team_patterns(value: object) -> list[tuple[str, str]]:
    """Extract every distinct provider event code/name pair from the fixture."""
    found: set[tuple[str, str]] = set()
    if isinstance(value, dict):
        code, name = value.get("event_code"), value.get("event_name")
        if isinstance(code, str) and isinstance(name, str):
            found.add((code, name))
        for item in value.values():
            found.update(_time_team_patterns(item))
    elif isinstance(value, list):
        for item in value:
            found.update(_time_team_patterns(item))
    return sorted(found)


def test_unmapped_pattern_opens_one_deduplicated_review_task() -> None:
    db = EventClassifyDb(
        [
            _event("unknown-1", source="herenow", name="Mystery Invitational Dinghy"),
            _event("unknown-2", source="herenow", name="Mystery Invitational Dinghy"),
        ]
    )

    event_classify(db)
    event_classify(db)

    assert db.classifications == []
    assert len(db.review_tasks) == 1
    task = db.review_tasks[0]
    assert task["task_type"] == UNMAPPED_TASK_TYPE
    assert task["details"] == {
        "source": "herenow",
        "pattern": {
            "event_code": None,
            "name": "Mystery Invitational Dinghy",
            "boat_class_raw": None,
            "age_class_raw": None,
            "gender_raw": None,
        },
        "example_event_names": ["Mystery Invitational Dinghy"],
        "occurrence_count": 2,
    }


def test_mapping_version_bump_inserts_a_new_row_without_rewriting_old_rows() -> None:
    db = EventClassifyDb([_event("master")])
    first = load_event_map()
    bumped = replace(first, version="2026.07.3")

    event_classify(db, event_map=first)
    event_classify(db, event_map=bumped)

    assert [(item["mapping_version"], item["age_bracket"]) for item in db.classifications] == [
        ("2026.07.2", "masters_unspecified"),
        ("2026.07.3", "masters_unspecified"),
    ]


def test_dry_run_writes_nothing_and_prints_coverage() -> None:
    db = EventClassifyDb([_event("master"), _event("unknown", name="Mystery Dinghy")])

    output = event_classify(db, dry_run=True)

    assert db.classifications == []
    assert db.review_tasks == []
    assert "dry-run" in output
    assert "herenow: 50.00%" in output


def _grants_body(sql: str) -> str:
    start = sql.index("CREATE OR REPLACE FUNCTION app.apply_phase1_role_grants()")
    end = sql.index("$$;", start) + 3
    return sql[start:end]


def test_event_classification_migration_down_restores_016_grants_body() -> None:
    root = Path(__file__).resolve().parents[2]
    previous = (root / "db/migrations/016_row2k_registry.sql").read_text(encoding="utf-8").split("-- migrate:down")[0]
    migration_down = (root / "db/migrations/019_event_classification.sql").read_text(encoding="utf-8").split("-- migrate:down", 1)[1]

    assert _grants_body(migration_down) == _grants_body(previous)


def test_register_attaches_event_classify_command() -> None:
    app = typer.Typer()
    register(app)

    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "event-classify" in result.output
