from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

import httpx

from crewgraphs.config import Settings
from crewgraphs.jobs.bmf import bmf_sync
from crewgraphs.raw_store import RawStore


FIXTURE = Path(__file__).parent / "fixtures/sources/eo_bmf_excerpt.csv"


class FakeS3:
    def __init__(self) -> None:
        self.objects: dict[str, dict[str, object]] = {}

    def head_object(self, *, Bucket: str, Key: str) -> dict[str, object]:
        if Key not in self.objects:
            raise KeyError(Key)
        item = self.objects[Key]
        return {"Metadata": item["metadata"], "ContentLength": len(item["body"])}

    def put_object(self, *, Bucket: str, Key: str, Body: bytes, ContentType: str, Metadata: dict[str, str]) -> dict[str, object]:
        self.objects[Key] = {"body": Body, "metadata": Metadata, "content_type": ContentType}
        return {}

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, object]:
        return {"Body": BytesIO(self.objects[Key]["body"])}


class Recorder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def execute(self, query: str, params: object = None) -> list[dict[str, object]]:
        self.calls.append((query, params))
        if "INSERT INTO ops.ingest_run" in query:
            return [{"id": "run-1"}]
        if "INSERT INTO core.source_record" in query:
            return [{"id": "source-1"}]
        if "INSERT INTO core.ein_observation" in query:
            return [{"id": "observation-1"}]
        return []


def _store(client: FakeS3) -> RawStore:
    return RawStore(Settings("postgres://fake", "account", "key", "secret"), client)


def _client(handler: httpx.MockTransport) -> httpx.Client:
    return httpx.Client(transport=handler)


def test_bmf_stages_watchlist_and_discovery_rows_with_header_release_date() -> None:
    contents = FIXTURE.read_bytes()

    def receive(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://www.irs.gov/pub/irs-soi/eo_nh.csv"
        return httpx.Response(200, content=contents, headers={"Last-Modified": "Mon, 21 Jul 2026 14:00:00 GMT"})

    db, s3 = Recorder(), FakeS3()
    with _client(httpx.MockTransport(receive)) as http:
        run_id = bmf_sync(db, _store(s3), http, states=["NH"], watchlist_eins={"030388282"})

    assert run_id == "run-1"
    assert "raw/irs/bmf/2026-07-21/eo_nh.csv" in s3.objects
    source_insert = next(params for query, params in db.calls if "INSERT INTO core.source_record" in query)
    assert source_insert[0] == "irs_bmf"
    staged = [params for query, params in db.calls if "INSERT INTO staging.bmf_row" in query]
    payloads = [json.loads(params[4]) for params in staged]
    assert any(row["NAME"] == "FRIENDS OF CONCORD CREW" for row in payloads)
    assert any(row["NAME"] == "BEDFORD CREW CLUB" for row in payloads)  # discovery regex
    assert all(row["NAME"] != "GROWING PLACES" for row in payloads)
    assert any("INSERT INTO core.ein_observation" in query for query, _ in db.calls)


def test_bmf_quarantines_conflict_and_http_failure_but_continues() -> None:
    contents = FIXTURE.read_bytes()

    def receive(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("eo_me.csv"):
            return httpx.Response(500)
        return httpx.Response(200, content=contents, headers={"Last-Modified": "Tue, 22 Jul 2026 14:00:00 GMT"})

    db, s3 = Recorder(), FakeS3()
    s3.objects["raw/irs/bmf/2026-07-22/eo_nh.csv"] = {
        "body": b"different", "metadata": {"sha256": "different"}, "content_type": "text/csv"
    }
    with _client(httpx.MockTransport(receive)) as http:
        bmf_sync(db, _store(s3), http, states=["NH", "ME"], watchlist_eins=set())

    quarantines = [call for call in db.calls if "INSERT INTO ops.quarantine" in call[0]]
    assert len(quarantines) == 2
    finish = [params for query, params in db.calls if "UPDATE ops.ingest_run\n            SET status" in query][-1]
    assert finish[0] == "succeeded"
    assert "warnings" in json.loads(finish[2])
