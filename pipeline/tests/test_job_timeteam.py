from __future__ import annotations

import copy
import json
from io import BytesIO
from pathlib import Path
from typing import Any

import httpx

from crewgraphs.config import Settings
from crewgraphs.jobs.timeteam import (
    _regatta_pairs_from_html,
    parse_time_ms,
    timeteam_load,
    timeteam_race_sync,
)
from crewgraphs.raw_store import RawStore


FIXTURES = Path(__file__).parent / "fixtures/timeteam"
RACE_ID = "95efa4c6-cdab-430a-9fbf-4bb57e24be3c"
CREW_ID = "5933eec6-9b37-4572-90dd-42d1dfa5a0da"
EIGHT_RACE_ID = "9ba5af37-18fb-48b3-ae71-473d3b26c6d7"


class FakeS3:
    def __init__(self) -> None:
        self.objects: dict[str, dict[str, Any]] = {}
        self.put_calls = 0

    def head_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:
        if Key not in self.objects:
            raise KeyError(Key)
        item = self.objects[Key]
        return {"Metadata": item["metadata"], "ContentLength": len(item["body"])}

    def put_object(self, **kwargs: Any) -> dict[str, Any]:
        self.put_calls += 1
        self.objects[kwargs["Key"]] = {"body": kwargs["Body"], "metadata": kwargs["Metadata"]}
        return {}

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:
        return {"Body": BytesIO(self.objects[Key]["body"])}


def _store(s3: FakeS3) -> RawStore:
    return RawStore(Settings("postgres://fake", "account", "key", "secret"), s3)


class SyncDb:
    def __init__(self) -> None:
        self.quarantines: list[tuple[Any, ...]] = []
        self.final_stats: dict[str, Any] = {}

    def execute(self, query: str, params: object = None) -> list[dict[str, Any]]:
        values = tuple(params or ())
        if "INSERT INTO ops.ingest_run" in query:
            return [{"id": "run-1"}]
        if "INSERT INTO core.source_record" in query:
            return [{"id": "source-1"}]
        if "INSERT INTO ops.quarantine" in query:
            self.quarantines.append(values)
        if "SET status = %s" in query:
            self.final_stats = json.loads(values[2])
        return []


class SyncStateDb(SyncDb):
    """Small staging fake that exposes logical-update churn to the test."""

    def __init__(self) -> None:
        super().__init__()
        self.regattas: dict[tuple[str, int], dict[str, Any]] = {}
        self.races: dict[str, dict[str, Any]] = {}
        self.stage_writes = 0

    def execute(self, query: str, params: object = None) -> list[dict[str, Any]]:
        values = tuple(params or ())
        stripped = query.lstrip()
        if stripped.startswith("SELECT") and "FROM staging.time_team_regatta" in query:
            row = self.regattas.get((str(values[0]), int(values[1])))
            return [row] if row else []
        if stripped.startswith("SELECT") and "FROM staging.time_team_race" in query:
            row = self.races.get(str(values[0]))
            return [row] if row else []
        if "INSERT INTO staging.time_team_regatta" in query:
            self.stage_writes += 1
            self.regattas[(str(values[2]), int(values[3]))] = {
                "source_record_id": values[1], "raw_payload": json.loads(values[4]) if values[4] else None,
            }
            return []
        if "INSERT INTO staging.time_team_race" in query:
            self.stage_writes += 1
            self.races[str(values[4])] = {"source_record_id": values[1], "raw_payload": json.loads(values[5])}
            return [{"id": "race-stage"}]
        return super().execute(query, params)


class LoadDb:
    def __init__(self, schedule: dict[str, Any], race: dict[str, Any], race_id: str = RACE_ID) -> None:
        self.schedule = schedule
        self.race = race
        self.race_id = race_id
        self.core: dict[str, Any] | None = None
        self.regattas: list[tuple[Any, ...]] = []
        self.events: list[tuple[Any, ...]] = []
        self.entries: list[tuple[Any, ...]] = []
        self.results: list[tuple[Any, ...]] = []
        self.provider_clubs: list[tuple[Any, ...]] = []
        self.people: list[tuple[Any, ...]] = []
        self.quarantines: list[tuple[Any, ...]] = []
        self.final_stats: dict[str, Any] = {}
        self._next = 0

    def _id(self, prefix: str) -> str:
        self._next += 1
        return f"{prefix}-{self._next}"

    def execute(self, query: str, params: object = None) -> list[dict[str, Any]]:
        values = tuple(params or ())
        if "INSERT INTO ops.ingest_run" in query:
            return [{"id": "run-1"}]
        if "FROM staging.time_team_regatta" in query:
            return [{"source_record_id": "source-1", "raw_payload": self.schedule}]
        if "FROM staging.time_team_race" in query:
            return [{"race_uuid": self.race_id, "raw_payload": self.race}]
        if "FROM core.regatta" in query and query.lstrip().startswith("SELECT"):
            return [self.core] if self.core else []
        if "INSERT INTO core.regatta\n" in query:
            self.regattas.append(values)
            self.core = {"revision": values[2], "payload_checksum": values[11]}
            return [{"id": self._id("regatta")}]
        if "INSERT INTO core.regatta_event" in query:
            self.events.append(values)
            return [{"id": self._id("event")}]
        if "INSERT INTO core.provider_club" in query:
            self.provider_clubs.append(values)
            return [{"id": self._id("club")}]
        if "INSERT INTO core.regatta_entry" in query:
            self.entries.append(values)
            return [{"id": self._id("entry")}]
        if "INSERT INTO core.result_person" in query:
            self.people.append(values)
        if "INSERT INTO core.regatta_result" in query:
            self.results.append(values)
        if "INSERT INTO ops.quarantine" in query:
            self.quarantines.append(values)
        if "SET status = %s" in query:
            self.final_stats = json.loads(values[2])
        return []


def _one_race_schedule(race_id: str = RACE_ID) -> dict[str, Any]:
    # The live schedule fixture retains three races.  The load test scopes it
    # to the one race for which the paired live detail fixture is supplied.
    schedule = json.loads((FIXTURES / "schedule-real.json").read_text())
    if race_id not in schedule["race"]:
        # The 8+ capture is a separate real detail response; its race object
        # is the provider's same schedule shape.
        detail = json.loads((FIXTURES / "race-8plus-real.json").read_text())
        schedule["race"][race_id] = detail["race"][race_id]
    schedule["race"] = {race_id: schedule["race"][race_id]}
    return schedule


def test_index_server_rendered_anchors_extract_only_selected_year() -> None:
    pairs = _regatta_pairs_from_html((FIXTURES / "index-2024-real.html").read_bytes(), 2024)
    assert len(pairs) == 12
    assert ("rowfest", 2024) in pairs
    assert ("sscrmc", 2024) in pairs
    assert ("usrowing-central-youth", 2024) in pairs
    assert ("usrowing-midatlantic-youth", 2024) in pairs
    assert ("usrowing-northeast-youth", 2024) in pairs
    assert ("usrowing-northwest-masters", 2024) in pairs
    assert ("usrowing-indoor", 2024) not in pairs  # /view/... is not a regatta API route.


def test_load_maps_results_clubs_people_splits_and_revision() -> None:
    schedule = _one_race_schedule()
    race = json.loads((FIXTURES / "race-real.json").read_text())
    db = LoadDb(schedule, race)

    timeteam_load(db, slug="usrowing-youth-national", year=2026)

    assert db.regattas[0][1:6] == ("usrowing-youth-national/2026", 1, "USRowing Youth National Championships", "2026-06-11", "2026-06-14")
    assert db.events[0][2:7] == ("Mens Youth 1x — Time Trial", "M Y 1x", "1x", None, "M")
    assert db.entries[0][1:7] == (CREW_ID, "4", None, "Miami Rowing and Watersports Center, Inc.", "club-3", None)
    assert "Daniil McLaughlin" not in db.entries[0][-1]
    entry_raw = json.loads(db.entries[0][-1])
    assert entry_raw["is_ooc"] is False
    assert entry_raw["has_tracking_data"] is False
    assert entry_raw["progression"]["target_round_id"] == "b9c1ffe0-b108-4817-8561-a0ea2217d79d"
    assert entry_raw["event_adjusted_pos"] == []
    assert db.results[0][1:7] == ("4", 8, 8, 423350, 423350, 13370)
    # ``handicap_ms`` is a literal SQL NULL, so it is absent from the bind
    # parameters between adjusted time and delta.
    assert db.results[1][1:7] == ("4", 11, 11, 425870, 425870, 15890)
    assert json.loads(db.results[0][-1])[0]["location_name"] == "finish"
    assert db.people[0][1:3] == ("Daniil McLaughlin", '{"stroke_fullname": "Daniil McLaughlin"}')
    assert db.final_stats["clubs_observed"] == 4
    assert db.final_stats["persons_loaded"] == 4
    assert db.final_stats["statuses_unknown"] == 0

    # Exact canonical payload is a no-op; changing a race payload creates the
    # insert-only second tree/revision.
    timeteam_load(db, slug="usrowing-youth-national", year=2026)
    assert len(db.regattas) == 1
    db.race = copy.deepcopy(db.race)
    db.race["round_crew"][CREW_ID]["adjusted_result"] = "07:03.36"
    timeteam_load(db, slug="usrowing-youth-national", year=2026)
    assert [params[2] for params in db.regattas] == [1, 2]


def test_race_404_is_quarantined_without_stopping_sync() -> None:
    schedule = _one_race_schedule()
    schedule["race"]["0e17db50-25a4-4b2d-a1be-c4d63a803019"] = {"uuid": "0e17db50-25a4-4b2d-a1be-c4d63a803019"}
    body = json.dumps(schedule).encode()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/0e17db50-25a4-4b2d-a1be-c4d63a803019"):
            return httpx.Response(404)
        return httpx.Response(200, content=body)

    db, s3 = SyncDb(), FakeS3()
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        timeteam_race_sync(
            db, _store(s3), http, slug="usrowing-youth-national", year=2026, sleep_ms=0, retrieved_date="2026-07-23"
        )

    assert any(values[1] == "timeteam_race_not_found" for values in db.quarantines)
    assert db.final_stats["quarantines"] == 1
    assert db.final_stats["races_fetched"] == 1


def test_timestamp_only_refetch_skips_r2_and_staging_and_does_not_bump_revision() -> None:
    schedule = _one_race_schedule()
    race = json.loads((FIXTURES / "race-real.json").read_text())

    def handler(request: httpx.Request) -> httpx.Response:
        # Every request gets a new volatile provider envelope timestamp while
        # all result content remains identical.
        document = copy.deepcopy(schedule if request.url.path.endswith("/race") else race)
        document["timestamp"] = 1000 + len(request_log)
        request_log.append(str(request.url))
        return httpx.Response(200, content=json.dumps(document).encode())

    request_log: list[str] = []
    db, s3 = SyncStateDb(), FakeS3()
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        timeteam_race_sync(db, _store(s3), http, slug="usrowing-youth-national", year=2026, sleep_ms=0, retrieved_date="2026-07-23")
        initial_writes, initial_puts = db.stage_writes, s3.put_calls
        loader = LoadDb(db.regattas[("usrowing-youth-national", 2026)]["raw_payload"], db.races[RACE_ID]["raw_payload"])
        timeteam_load(loader, slug="usrowing-youth-national", year=2026)
        timeteam_race_sync(db, _store(s3), http, slug="usrowing-youth-national", year=2026, sleep_ms=0, retrieved_date="2026-07-23")

    assert db.stage_writes == initial_writes == 2
    assert s3.put_calls == initial_puts == 2
    assert db.quarantines == []
    timeteam_load(loader, slug="usrowing-youth-national", year=2026)
    assert len(loader.regattas) == 1


def test_empty_list_round_crews_loads_schedule_without_quarantine() -> None:
    schedule = _one_race_schedule()
    race = json.loads((FIXTURES / "race-real.json").read_text())
    race["round_crew"] = []  # Real PHP response shape for a final not yet raced.
    race["race_crew"] = []
    db = LoadDb(schedule, race)

    timeteam_load(db, slug="usrowing-youth-national", year=2026)

    assert len(db.regattas) == len(db.events) == 1
    assert db.entries == db.results == []
    assert db.quarantines == []


def test_out_of_competition_crew_loads_and_keeps_provider_fields_raw() -> None:
    schedule = _one_race_schedule()
    race = json.loads((FIXTURES / "race-real.json").read_text())
    # Synthetic variant: the real capture has no OOC row.  OOC remains a
    # provider-raw status signal, not a reason to skip a result.
    race["round_crew"][CREW_ID]["is_ooc"] = True
    db = LoadDb(schedule, race)

    timeteam_load(db, slug="usrowing-youth-national", year=2026)

    assert len(db.entries) == len(race["round_crew"])
    assert json.loads(db.entries[0][-1])["is_ooc"] is True
    assert db.results[0][1] == "4"


def test_8plus_labels_and_person_names_are_isolated_from_every_other_core_insert() -> None:
    fixtures = ((RACE_ID, "race-real.json"), (EIGHT_RACE_ID, "race-8plus-real.json"))
    loaded: list[LoadDb] = []
    for race_id, filename in fixtures:
        db = LoadDb(_one_race_schedule(race_id), json.loads((FIXTURES / filename).read_text()), race_id)
        timeteam_load(db, slug="usrowing-youth-national", year=2026)
        loaded.append(db)

    assert loaded[1].entries[0][6] == "A"
    for db in loaded:
        person_names = {params[1] for params in db.people}
        non_person_inserts = db.regattas + db.events + db.entries + db.provider_clubs + db.results
        serialized = json.dumps(non_person_inserts, default=str)
        assert all(name not in serialized for name in person_names)


def test_multisplit_finish_uses_last_or_max_distance_point() -> None:
    schedule = _one_race_schedule()
    race = json.loads((FIXTURES / "race-real.json").read_text())
    # Synthetic variant: the real capture has one finish point. A multi-split
    # final must select its terminal 2000m result rather than the first split.
    race["round_crew"][CREW_ID]["times"] = [
        {"location_name": "500m", "total": {"pos": 8, "result": "01:40.00"}},
        {"location_name": "2000m", "total": {"pos": 2, "result": "06:40.00"}},
    ]
    db = LoadDb(schedule, race)

    timeteam_load(db, slug="usrowing-youth-national", year=2026)

    assert db.results[0][2:5] == (2, 8, 400000)


def test_time_parser_handles_finish_and_delta() -> None:
    assert parse_time_ms("07:03.35") == 423350
    assert parse_time_ms("+13.37") == 13370
    assert parse_time_ms("-13.37") == -13370
    assert parse_time_ms("0") is None
    assert parse_time_ms("00:00.00") is None
    assert parse_time_ms("DNS") is None
