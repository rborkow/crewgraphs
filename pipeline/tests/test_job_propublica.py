from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from typing import Any

import httpx

from crewgraphs.config import Settings
from crewgraphs.jobs.propublica import propublica_bootstrap
from crewgraphs.raw_store import RawStore


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "spike/output/030388282/propublica.json"


class FakeS3:
    def __init__(self) -> None:
        self.objects: dict[str, dict[str, Any]] = {}

    def head_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:
        if Key not in self.objects:
            raise KeyError(Key)
        item = self.objects[Key]
        return {"Metadata": item["metadata"], "ContentLength": len(item["body"])}

    def put_object(self, **kwargs: Any) -> dict[str, Any]:
        self.objects[kwargs["Key"]] = {
            "body": kwargs["Body"],
            "metadata": kwargs["Metadata"],
            "content_type": kwargs["ContentType"],
        }
        return {}

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:
        return {"Body": BytesIO(self.objects[Key]["body"])}


class FakeDb:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []
        self.quarantines: list[tuple[Any, ...]] = []
        self.staged: list[tuple[Any, ...]] = []
        self.final_stats: dict[str, Any] = {}

    def execute(self, query: str, params: object = None) -> list[dict[str, Any]]:
        values = tuple(params or ())
        self.calls.append((query, values))
        if "INSERT INTO ops.ingest_run" in query:
            return [{"id": "run-1"}]
        if "INSERT INTO core.source_record" in query:
            return [{"id": "source-1"}]
        if "UPDATE staging.propublica_org" in query:
            return []
        if "INSERT INTO staging.propublica_org" in query:
            self.staged.append(values)
        if "INSERT INTO ops.quarantine" in query:
            self.quarantines.append(values)
        if "SET status = %s" in query:
            self.final_stats = json.loads(values[2])
        return []


def _store(client: FakeS3) -> RawStore:
    return RawStore(Settings("postgres://fake", "account", "key", "secret"), client)


def test_propublica_bootstrap_preserves_fixture_and_strips_leading_zero_for_api() -> None:
    body = FIXTURE.read_bytes()
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        return httpx.Response(200, content=body)

    s3, db = FakeS3(), FakeDb()
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        run_id = propublica_bootstrap(
            db, _store(s3), http, eins=["030388282"], retrieved_date="2026-07-22"
        )

    assert run_id == "run-1"
    assert requested == [
        "https://projects.propublica.org/nonprofits/api/v2/organizations/30388282.json"
    ]
    key = "raw/propublica/org/030388282/2026-07-22.json"
    assert s3.objects[key]["body"] == body
    assert s3.objects[key]["content_type"] == "application/json"
    source_call = next(call for call in db.calls if "INSERT INTO core.source_record" in call[0])
    assert source_call[1][0] == "propublica"
    assert json.loads(db.staged[0][3]) == json.loads(body)
    assert db.final_stats == {
        "eins_fetched": 1,
        "not_found": 0,
        "payload_bytes": len(body),
    }


def test_propublica_404_is_quarantined_and_does_not_stop_remaining_eins() -> None:
    body = FIXTURE.read_bytes()
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(request.url.path)
        if request.url.path.endswith("/30388282.json"):
            return httpx.Response(404)
        return httpx.Response(200, content=body)

    s3, db = FakeS3(), FakeDb()
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        propublica_bootstrap(
            db,
            _store(s3),
            http,
            eins=["030388282", "237397498"],
            retrieved_date="2026-07-22",
        )

    assert requested == [
        "/nonprofits/api/v2/organizations/30388282.json",
        "/nonprofits/api/v2/organizations/237397498.json",
    ]
    assert db.quarantines[0][1] == "propublica_not_found"
    assert len(db.staged) == 1
    assert db.final_stats == {"not_found": 1, "eins_fetched": 1, "payload_bytes": len(body)}
