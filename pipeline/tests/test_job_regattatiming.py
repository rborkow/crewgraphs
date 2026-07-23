from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Any

import httpx
import pytest

from crewgraphs.config import Settings
from crewgraphs.jobs.regattatiming import (
    ParseShapeError,
    _entry_external_key,
    _parse_hero_dates,
    _scheduled_at,
    _split_entry,
    parse_page,
    parse_race_ids,
    parse_time_ms,
    regattatiming_load,
    regattatiming_sync,
)
from crewgraphs.raw_store import RawStore


FIXTURE = Path(__file__).parent / "fixtures/regattatiming/625-real.html"


class FakeS3:
    def __init__(self) -> None:
        self.objects: dict[str, dict[str, Any]] = {}

    def head_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:
        if Key not in self.objects:
            raise KeyError(Key)
        value = self.objects[Key]
        return {"Metadata": value["Metadata"], "ContentLength": len(value["Body"])}

    def put_object(self, **kwargs: Any) -> dict[str, Any]:
        self.objects[kwargs["Key"]] = kwargs
        return {}

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:
        return {"Body": BytesIO(self.objects[Key]["Body"])}


class SyncDb:
    def __init__(self) -> None:
        self.quarantines: list[tuple[Any, ...]] = []
        self.stats: dict[str, Any] = {}

    def execute(self, query: str, params: object = None) -> list[dict[str, Any]]:
        values = tuple(params or ())
        if "INSERT INTO ops.ingest_run" in query:
            return [{"id": "run-1"}]
        if "INSERT INTO core.source_record" in query:
            return [{"id": "source-1"}]
        if "INSERT INTO ops.quarantine" in query:
            self.quarantines.append(values)
        if "SET status = %s" in query:
            self.stats = json.loads(values[2])
        return []


def store(client: FakeS3) -> RawStore:
    return RawStore(Settings("postgres://fake", "account", "key", "secret"), client)


def test_real_header_event_section_and_stroke_extraction() -> None:
    parsed = parse_page(FIXTURE.read_bytes())

    assert parsed.title == "IRA National Championship"
    assert parsed.venue == "Pennsauken, NJ United States"
    assert (parsed.start_date.isoformat(), parsed.end_date.isoformat()) == ("2025-05-30", "2025-06-01")
    assert [(event.event_id, event.number, event.round) for event in parsed.events] == [("56037", "1", "Heat 1")]
    assert parsed.events[0].rows[0].club == "Harvard"
    assert parsed.events[0].rows[0].stroke == "Stevenson, J."
    assert parsed.events[0].rows[0].provider_external_key == "92"
    assert parsed.events[0].rows[1].delta_ms == 3090


@pytest.mark.parametrize(
    ("value", "expected"),
    [("05:49.930", 349930), ("5:49.9", 349900), ("0:02.170", 2170), ("12.003", 12003), ("-", None)],
)
def test_time_and_margin_to_ms_edge_cases(value: str, expected: int | None) -> None:
    assert parse_time_ms(value, field="margin", blank_is_none=True) == expected


def test_invalid_time_raises() -> None:
    with pytest.raises(Exception):
        parse_time_ms("five minutes", field="time")


def test_shape_mismatch_is_not_best_effort() -> None:
    broken = FIXTURE.read_text().replace('data-mdb-field="margin"', 'data-mdb-field="gap"', 1)
    with pytest.raises(ParseShapeError):
        parse_page(broken.encode())


@pytest.mark.parametrize(
    ("status_code", "content"),
    [
        (403, b""),
        (429, b""),
        (503, b""),
        (200, b"<html><title>Just a moment...</title>Enable JavaScript and cookies to continue</html>"),
    ],
)
def test_blocked_responses_quarantine_and_stop_without_requesting_later_ids(status_code: int, content: bytes) -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(status_code, content=content, request=request)

    db, s3 = SyncDb(), FakeS3()
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        regattatiming_sync(db, store(s3), http, race_ids="625,626", sleep_ms=0)

    assert len(seen) == 1
    assert db.quarantines[0][1] == "regattatiming_blocked"
    assert db.stats["quarantines"] == 1


def test_stroke_extraction_requires_surname_initial_shape() -> None:
    assert _split_entry("Yale (B)") == ("Yale (B)", None)
    assert _split_entry("Trinity College (Dublin) (Smith, A.)") == ("Trinity College (Dublin)", "Smith, A.")


def test_cross_year_dates_single_digit_schedule_and_entry_key_fallback() -> None:
    assert _parse_hero_dates("Dec 31 - Jan 1, 2025") == (
        date(2024, 12, 31),
        date(2025, 1, 1),
    )
    parsed = parse_page(FIXTURE.read_bytes().replace(b"(08:00)", b"(8:00)"))
    assert _scheduled_at(parsed.start_date, parsed.events[0].scheduled_time).hour == 8
    empty_identity = replace(parsed.events[0].rows[0], position=None, lane=None)
    assert _entry_external_key("56037:Heat 1", empty_identity, 1) == "56037:Heat 1:row-1"
    assert _entry_external_key("56037:Heat 1", empty_identity, 2) == "56037:Heat 1:row-2"


def test_range_and_probe_forward_stop_at_consecutive_misses() -> None:
    seen: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        race_id = int(request.url.params["raceId"])
        seen.append(race_id)
        status = 404 if race_id >= 651 else 200
        return httpx.Response(status, content=FIXTURE.read_bytes(), request=request)

    db, s3 = SyncDb(), FakeS3()
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        regattatiming_sync(db, store(s3), http, race_ids="649-650", probe_forward=2, sleep_ms=0)

    assert seen == [649, 650, 651, 652]
    assert parse_race_ids("369-370,370,650") == [369, 370, 650]
    assert db.stats["pages_probed"] == 2


def test_checksum_conflict_is_quarantined_but_not_a_probe_miss() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        race_id = int(request.url.params["raceId"])
        return httpx.Response(404 if race_id == 626 else 200, content=FIXTURE.read_bytes(), request=request)

    db, s3 = SyncDb(), FakeS3()
    raw_store = store(s3)
    raw_store.put_raw("raw/regattatiming/summary/625/2026-07-23.html", b"different", "text/html")
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        regattatiming_sync(
            db, raw_store, http, race_ids="625", probe_forward=1, sleep_ms=0,
            today=date(2026, 7, 23),
        )

    assert db.quarantines[0][1] == "regattatiming_checksum_conflict"
    assert db.stats["pages_missing"] == 1  # only the forward 626 404
    assert db.stats["pages_probed"] == 1


class LoadDb(SyncDb):
    def __init__(self, raw_uri: str, checksum: str) -> None:
        super().__init__()
        self.raw_uri, self.checksum = raw_uri, checksum
        self.revision = 0
        self.latest_checksum: str | None = None
        self.inserted_regattas = 0
        self.next_id = 0
        self.event_external_keys: list[str] = []
        self.club_external_keys: list[str] = []
        self.non_person_raw_payloads: list[str] = []
        self.person_raw_payloads: list[str] = []

    def execute(self, query: str, params: object = None) -> list[dict[str, Any]]:
        values = tuple(params or ())
        if "FROM staging.regattatiming_page" in query:
            return [{"race_id": 625, "source_record_id": "source-1", "raw_uri": self.raw_uri}]
        if "SELECT checksum_sha256" in query:
            return [{"checksum_sha256": self.checksum}]
        if "SELECT id, revision, payload_checksum" in query:
            return ([] if self.latest_checksum is None else [{"id": "old", "revision": self.revision, "payload_checksum": self.latest_checksum}])
        if "INSERT INTO core.regatta (" in query:
            self.revision = values[2]
            self.latest_checksum = values[8]
            self.inserted_regattas += 1
            self.non_person_raw_payloads.append(values[7])
            return [{"id": f"regatta-{self.revision}"}]
        if "INSERT INTO core.regatta_event" in query:
            self.event_external_keys.append(values[1])
            self.non_person_raw_payloads.append(values[6])
            self.next_id += 1
            return [{"id": f"id-{self.next_id}"}]
        if "INSERT INTO core.provider_club" in query:
            self.club_external_keys.append(values[1])
            self.next_id += 1
            return [{"id": f"id-{self.next_id}"}]
        if "INSERT INTO core.regatta_entry" in query:
            self.non_person_raw_payloads.append(values[5])
            self.next_id += 1
            return [{"id": f"id-{self.next_id}"}]
        if "INSERT INTO core.result_person" in query:
            self.person_raw_payloads.append(values[2])
        if "RETURNING id" in query and ("core.regatta_event" in query or "core.regatta_entry" in query or "core.provider_club" in query):
            self.next_id += 1
            return [{"id": f"id-{self.next_id}"}]
        if "SELECT id FROM core.provider_club" in query:
            return [{"id": "club-existing"}]
        return super().execute(query, params)


def test_checksum_noop_then_revision_bump() -> None:
    s3 = FakeS3()
    raw_store = store(s3)
    raw = raw_store.put_raw("raw/regattatiming/summary/625/2026-07-23.html", FIXTURE.read_bytes(), "text/html")
    db = LoadDb(raw.uri, raw.checksum_sha256)

    regattatiming_load(db, raw_store, race_ids="625")
    regattatiming_load(db, raw_store, race_ids="625")
    assert db.inserted_regattas == 1
    assert db.revision == 1
    assert db.event_external_keys == ["56037:Heat 1"]
    assert db.club_external_keys == ["92", "50", "29430", "33607"]
    assert all("Stevenson, J." not in raw for raw in db.non_person_raw_payloads)
    assert any("Stevenson, J." in raw for raw in db.person_raw_payloads)

    db.checksum = "different-checksum"
    regattatiming_load(db, raw_store, race_ids="625")
    assert db.inserted_regattas == 2
    assert db.revision == 2
