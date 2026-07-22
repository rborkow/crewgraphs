from __future__ import annotations

import json
import zipfile
from datetime import date
from io import BytesIO
from pathlib import Path

import httpx

from crewgraphs.config import Settings
from crewgraphs.jobs.epostcard import epostcard_sync
from crewgraphs.raw_store import RawStore


FIXTURE = Path(__file__).parent / "fixtures/sources/epostcard_excerpt.txt"


class FakeS3:
    def __init__(self) -> None:
        self.objects: dict[str, dict[str, object]] = {}

    def head_object(self, *, Bucket: str, Key: str) -> dict[str, object]:
        if Key not in self.objects:
            raise KeyError(Key)
        item = self.objects[Key]
        return {"Metadata": item["metadata"], "ContentLength": len(item["body"])}

    def put_object(self, *, Bucket: str, Key: str, Body: object, ContentType: str, Metadata: dict[str, str]) -> dict[str, object]:
        self.objects[Key] = {"body": Body, "metadata": Metadata, "content_type": ContentType}
        return {}

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, object]:
        return {"Body": BytesIO(bytes(self.objects[Key]["body"]))}


class Recorder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def execute(self, query: str, params: object = None) -> list[dict[str, object]]:
        self.calls.append((query, params))
        if "INSERT INTO ops.ingest_run" in query:
            return [{"id": "run-1"}]
        if "INSERT INTO core.source_record" in query:
            return [{"id": "source-1"}]
        if "INSERT INTO core.epostcard_observation" in query:
            return [{"id": "observation-1"}]
        return []


def _zip_bytes() -> bytes:
    destination = BytesIO()
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("epostcard.txt", FIXTURE.read_bytes())
    return destination.getvalue()


def test_epostcard_stages_husky_and_writes_retrieval_date_key() -> None:
    archive = _zip_bytes()

    def receive(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://apps.irs.gov/pub/epostcard/data-download-epostcard.zip"
        return httpx.Response(200, content=archive)

    db, s3 = Recorder(), FakeS3()
    store = RawStore(Settings("postgres://fake", "account", "key", "secret"), s3)
    with httpx.Client(transport=httpx.MockTransport(receive)) as http:
        run_id = epostcard_sync(db, store, http, watchlist_eins=set(), retrieved_date="2026-07-22")

    assert run_id == "run-1"
    assert "raw/irs/990n/2026-07-22/data-download-epostcard.zip" in s3.objects
    staged = [params for query, params in db.calls if "INSERT INTO staging.epostcard_row" in query]
    assert len(staged) == 1
    assert json.loads(staged[0][3])["ORGANIZATION_NAME"] == "HUSKY ROWING FOUNDATION"
    observation = next(params for query, params in db.calls if "INSERT INTO core.epostcard_observation" in query)
    assert observation[1:4] == ("811495108", 2024, date(2024, 12, 31))
