from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from crewgraphs.config import Settings
from crewgraphs.jobs.herenow import (
    _elapsed_ms,
    _payload_checksum,
    _people,
    herenow_catalog_sync,
    herenow_load,
    herenow_race_backfill,
    parse_results_time,
)
from crewgraphs.raw_store import RawStore


FIXTURES = Path(__file__).parent / "fixtures" / "herenow"


class FakeS3:
    def __init__(self) -> None:
        self.objects: dict[str, dict[str, Any]] = {}

    def head_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:
        if Key not in self.objects:
            raise KeyError(Key)
        item = self.objects[Key]
        return {"Metadata": item["metadata"], "ContentLength": len(item["body"])}

    def put_object(self, **kwargs: Any) -> dict[str, Any]:
        self.objects[kwargs["Key"]] = {"body": kwargs["Body"], "metadata": kwargs["Metadata"]}
        return {}


class FakeDb:
    def __init__(self, *, staged: list[dict[str, Any]] | None = None, catalog_count: int = 0) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []
        self.staged = staged or []
        self.catalog_count = catalog_count
        self.quarantines: list[tuple[Any, ...]] = []
        self.latest: dict[str, Any] | None = None
        self.regattas = 0
        self.final_stats: dict[str, Any] = {}

    def execute(self, query: str, params: object = None) -> list[dict[str, Any]]:
        values = tuple(params or ())
        self.calls.append((query, values))
        if "INSERT INTO ops.ingest_run" in query:
            return [{"id": "run-1"}]
        if "SELECT count(*) AS count FROM staging.herenow_catalog_row" in query:
            return [{"count": self.catalog_count}]
        if "INSERT INTO core.source_record" in query:
            return [{"id": "source-1"}]
        if "SELECT id FROM core.source_record" in query:
            return [{"id": "source-1"}]
        if "SELECT b.race_id" in query:
            return self.staged
        if "SELECT id, revision, payload_checksum, parser_version FROM core.regatta" in query:
            return [self.latest] if self.latest else []
        if "INSERT INTO core.regatta\n" in query:
            self.regattas += 1
            self.latest = {"id": f"regatta-{self.regattas}", "revision": self.regattas, "payload_checksum": values[-3], "parser_version": values[-1]}
            return [{"id": self.latest["id"]}]
        if "INSERT INTO core.regatta_event" in query:
            return [{"id": "event-1"}]
        if "INSERT INTO core.regatta_entry" in query:
            return [{"id": "entry-1"}]
        if "INSERT INTO core.provider_club" in query:
            return [{"id": "club-1"}]
        if "SELECT id FROM core.provider_club" in query:
            return [{"id": "club-1"}]
        if "SELECT race_id, raw_row FROM staging.herenow_catalog_row" in query:
            return self.staged
        if "INSERT INTO ops.quarantine" in query:
            self.quarantines.append(values)
        if "SET status = %s" in query:
            self.final_stats = json.loads(values[2])
        return []


def _store(s3: FakeS3) -> RawStore:
    return RawStore(Settings("postgres://fake", "account", "key", "secret"), s3)


def _payloads() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    return (
        json.loads((FIXTURES / "21464-base-real.json").read_text()),
        json.loads((FIXTURES / "21464-flights-real.json").read_text()),
    )


def _renumber_breeze_ids(*values: object) -> None:
    identifiers: dict[str, str] = {}

    def collect(value: object) -> None:
        if isinstance(value, dict):
            if isinstance(value.get("$id"), str):
                identifiers.setdefault(value["$id"], f"node-{len(identifiers) + 1}")
            for child in value.values():
                collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

    def rewrite(value: object) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key in {"$id", "$ref"} and isinstance(child, str):
                    value[key] = identifiers[child]
                else:
                    rewrite(child)
        elif isinstance(value, list):
            for child in value:
                rewrite(child)

    for value in values:
        collect(value)
    for value in values:
        rewrite(value)


def test_catalog_sync_handles_envelope_and_array_shapes() -> None:
    envelope = {"Results": [{"Id": 1, "Name": "One"}], "InlineCount": 2}
    array = [{"Id": 2, "Name": "Two"}]
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(200, json=envelope if requests == 1 else array)

    # The first page is intentionally 1, rather than 5,000, so this proves both
    # shapes through two independent catalog captures.
    for payload in (envelope, array):
        db, s3 = FakeDb(), FakeS3()
        with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))) as http:
            herenow_catalog_sync(db, _store(s3), http, base_url="https://example.test")
        assert db.final_stats["catalog_rows"] == 1
        assert any("ON CONFLICT (race_id) DO UPDATE" in call[0] for call in db.calls)


def test_identical_payload_is_noop_and_changed_payload_bumps_revision() -> None:
    base, flights = _payloads()
    db = FakeDb(staged=[{"race_id": 21464, "base_payload": base, "flights_payload": flights, "source_record_id": "source-1"}])
    herenow_load(db)
    assert db.regattas == 1
    herenow_load(db)
    assert db.regattas == 1
    assert db.final_stats["races_unchanged"] == 1
    flights[0]["EntryResults"][0]["Status"] = "Official"
    herenow_load(db)
    assert db.regattas == 2
    inserted = [call for call in db.calls if "INSERT INTO core.regatta\n" in call[0]]
    assert inserted[-1][1][2] == 2


def test_breeze_id_renumbering_has_stable_checksum_and_is_a_noop() -> None:
    base, flights = _payloads()
    renumbered_base, renumbered_flights = copy.deepcopy(base), copy.deepcopy(flights)
    _renumber_breeze_ids(renumbered_base, renumbered_flights)
    assert _payload_checksum(base, flights) == _payload_checksum(renumbered_base, renumbered_flights)

    db = FakeDb(staged=[{"race_id": 21464, "base_payload": base, "flights_payload": flights, "source_record_id": "source-1"}])
    herenow_load(db)
    db.staged[0]["base_payload"] = renumbered_base
    db.staged[0]["flights_payload"] = renumbered_flights
    herenow_load(db)
    assert db.regattas == 1
    assert db.final_stats["races_unchanged"] == 1


def test_masters_mapping_and_persons_are_written_to_result_person() -> None:
    base, flights = _payloads()
    # Keep the production object shape, but give the first real masters row the
    # published handicap semantics that are otherwise absent from this capture.
    first = flights[0]["EntryResults"][0]
    first["Status"] = "Official"
    first["StartTime1"] = "2026-07-19T11:00:00.000Z"
    first["FinishTime1"] = "2026-07-19T11:03:25.800Z"
    first["HandicapTimespan"] = "-19.22"
    db = FakeDb(staged=[{"race_id": 21464, "base_payload": base, "flights_payload": flights, "source_record_id": "source-1"}])
    herenow_load(db)
    result = next(call for call in db.calls if "INSERT INTO core.regatta_result" in call[0])
    assert result[1][4:7] == (205800, 186580, -19220)
    people = [call for call in db.calls if "INSERT INTO core.result_person" in call[0]]
    assert people and people[0][1][3] == "Daniel DeSnyder"
    entry = next(call for call in db.calls if "INSERT INTO core.regatta_entry" in call[0])
    assert entry[1][4] == "Greater Houston"
    assert entry[1][6] == "Greater Houston"
    assert "Daniel DeSnyder" not in entry[1][7]
    assert "RegEmail" not in entry[1][7]
    club = next(call for call in db.calls if "INSERT INTO core.provider_club" in call[0])
    assert club[1][1] == "name:greaterhouston"
    event = next(call for call in db.calls if "INSERT INTO core.regatta_event" in call[0])
    assert event[1][4:8] == (None, None, None, None)


def test_results_time_parser_edge_cases() -> None:
    assert parse_results_time("3:25.8") == 205800
    assert parse_results_time("1:02:03.45") == 3_723_450
    assert parse_results_time("-19.22") == -19220
    assert parse_results_time("-1:00.03") == -60030
    assert parse_results_time("DNS") is None
    assert parse_results_time("Official") is None
    assert _elapsed_ms({"Time": "0"}) is None


def test_competitor_raw_is_allowlisted_and_unspaced_singles_are_detected() -> None:
    people = _people(
        {"Competitors": [{"Name": "Ava Rower", "Role": "bow", "Seat": 1, "DateOfBirth": "2011-01-01", "Grade": "8", "Email": "ava@example.test"}]},
        {"Name": "LM1x Final"},
    )
    assert people == [{"name": "Ava Rower", "role": "bow", "seat": 1, "raw": {"Role": "bow", "Seat": 1}}]
    assert _people({"Name": "Ava Rower (Riverside)"}, {"Name": "LM1x Final"})[0]["name"] == "Ava Rower"


def test_backfill_quarantines_500_and_skip_set_never_hits_http() -> None:
    rows = [
        {"race_id": 0, "raw_row": {"Id": 0}},
        {"race_id": 42, "raw_row": {"Id": 42, "IsTest": True}},
        {"race_id": 21464, "raw_row": {"Id": 21464, "IsTest": False}},
    ]
    db, s3 = FakeDb(staged=rows), FakeS3()
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(500)

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        herenow_race_backfill(db, _store(s3), http, race_ids=["0", "42", "21464"], sleep_ms=0, base_url="https://example.test")
    assert len(seen) == 1
    assert db.final_stats["races_skipped"] == 2
    assert db.final_stats["quarantines"] == 1
    assert "500 Internal Server Error" in db.quarantines[0][1]
    assert "raceId=21464" in db.quarantines[0][1]


@pytest.mark.parametrize(
    ("flights_response", "reason"),
    [
        ({"Message": "Breeze failed", "ExceptionMessage": "details"}, "Breeze error envelope"),
        ({"Flights": []}, "GetScopedRaceFlights response is not a list"),
    ],
)
def test_backfill_quarantines_breeze_error_and_non_list_flights(flights_response: dict[str, Any], reason: str) -> None:
    base, _ = _payloads()
    db, s3 = FakeDb(staged=[{"race_id": 21464, "raw_row": {"Id": 21464, "IsTest": False}}]), FakeS3()
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=base if calls == 1 else flights_response)

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        herenow_race_backfill(db, _store(s3), http, race_ids=[21464], sleep_ms=0, base_url="https://example.test")
    assert calls == 2
    assert db.final_stats["quarantines"] == 1
    assert reason in db.quarantines[0][1]


def test_club_like_display_names_never_become_persons() -> None:
    """Smoke regression (branch 2026-07-23): stroke-less crew entries carry the
    club in both display halves ('Community (Community B)'); club-like strings
    must not be emitted as result_person rows."""
    from crewgraphs.jobs.herenow import _is_club_like, _people as _derive_persons

    flight = {"Name": "Men's Masters 2x TT"}
    for display, affiliation in [
        ("Community (Community B)", "Community"),
        ("Community B (Community)", "Community"),
        ("CortlandtCommunityRowing (CortlandtCommunityRowing)", "CortlandtCommunityRowing"),
    ]:
        entry = {"Name": display, "AffiliationName": affiliation, "Competitors": []}
        assert _derive_persons(entry, flight) == [], display

    # A real stroke parenthetical still yields a person.
    entry = {"Name": "Community (Douthitt, N.)", "AffiliationName": "Community", "Competitors": []}
    persons = _derive_persons(entry, flight)
    assert [p["name"] for p in persons] == ["Douthitt, N."]

    assert _is_club_like("Community B", "Community")
    assert not _is_club_like("Douthitt, N.", "Community")
