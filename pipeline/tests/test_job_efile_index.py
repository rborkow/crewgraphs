from __future__ import annotations

import json
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import httpx

from crewgraphs.config import Settings
from crewgraphs.jobs.efile_index import efile_index_sync
from crewgraphs.raw_store import RawStore


class FakeS3:
    def __init__(self) -> None:
        self.objects: dict[str, dict[str, Any]] = {}

    def head_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:
        if Key not in self.objects:
            raise KeyError(Key)
        object_ = self.objects[Key]
        return {"Metadata": object_["metadata"], "ContentLength": len(object_["body"])}

    def put_object(self, *, Bucket: str, Key: str, Body: bytes, ContentType: str, Metadata: dict[str, str]) -> dict[str, Any]:
        self.objects[Key] = {"body": Body, "metadata": Metadata, "content_type": ContentType}
        return {}

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:
        return {"Body": BytesIO(self.objects[Key]["body"])}


class IndexDb:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

    def execute(self, query: str, params: Any = None) -> list[dict[str, Any]]:
        self.calls.append((query, params))
        if "INSERT INTO ops.ingest_run" in query:
            return [{"id": "run-index"}]
        if "INSERT INTO core.source_record" in query:
            return [{"id": "source-index"}]
        if "INSERT INTO staging.efile_index_row" in query:
            return [{"irs_object_id": params[4]}]
        return []


def test_efile_index_sync_keeps_watchlist_990ez_and_drops_990t() -> None:
    fixture = Path(__file__).parent / "fixtures" / "sources" / "efile_index_excerpt.csv"
    body = fixture.read_bytes() + (
        b"19975908,EFILE,030388282,202106,4/27/2022 7:52:43 AM,FRIENDS OF CONCORD CREW,990T,93492315009482,999999999999999999\n"
    )
    http = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, content=body)))
    db = IndexDb()
    s3 = FakeS3()
    store = RawStore(Settings("postgres://fake", "account", "key", "secret"), s3)

    stats = efile_index_sync(db, store, http, years=[2021], watchlist_eins=["030388282"])

    assert stats == {"rows_seen": 4, "rows_kept": 1, "new_object_ids": 1, "dropped_990t": 1}
    expected_key = f"raw/irs/efile-index/2021/{datetime.now(UTC).date().isoformat()}_index.csv"
    assert list(s3.objects) == [expected_key]
    source_call = next(call for call in db.calls if "INSERT INTO core.source_record" in call[0])
    assert source_call[1][0:2] == ("irs_efile_index", "2021")
    row_call = next(call for call in db.calls if "INSERT INTO staging.efile_index_row" in call[0])
    assert row_call[1][3:6] == ("030388282", "202133159349200948", "")
    assert json.loads(row_call[1][6])["RETURN_TYPE"] == "990EZ"
