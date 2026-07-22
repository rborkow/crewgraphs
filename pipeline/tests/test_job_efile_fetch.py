from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

import httpx

from crewgraphs.config import Settings
from crewgraphs.jobs.efile_fetch import GT_LAKE_XML_URL, efile_fetch
from crewgraphs.raw_store import RawStore


class FakeS3:
    def __init__(self) -> None:
        self.objects: dict[str, dict[str, Any]] = {}

    def head_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:
        if Key not in self.objects:
            raise KeyError(Key)
        data = self.objects[Key]
        return {"Metadata": data["metadata"], "ContentLength": len(data["body"])}

    def put_object(self, *, Bucket: str, Key: str, Body: bytes, ContentType: str, Metadata: dict[str, str]) -> dict[str, Any]:
        self.objects[Key] = {"body": Body, "metadata": Metadata, "content_type": ContentType}
        return {}

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:
        return {"Body": BytesIO(self.objects[Key]["body"])}


class FetchDb:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

    def execute(self, query: str, params: Any = None) -> list[dict[str, Any]]:
        self.calls.append((query, params))
        if "INSERT INTO ops.ingest_run" in query:
            return [{"id": "run-fetch"}]
        if "SELECT DISTINCT e.irs_object_id" in query:
            return [
                {"irs_object_id": "202121129349301317", "tax_year": 2021},
                {"irs_object_id": "missing-object", "tax_year": 2021},
            ]
        if "INSERT INTO core.source_record" in query:
            return [{"id": "source-xml"}]
        return []


def test_efile_fetch_writes_200_and_quarantines_expected_lake_404() -> None:
    golden = (Path(__file__).parent / "fixtures" / "golden" / "202121129349301317.xml").read_bytes()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url == GT_LAKE_XML_URL.format(object_id="202121129349301317"):
            return httpx.Response(200, content=golden)
        assert request.url == GT_LAKE_XML_URL.format(object_id="missing-object")
        return httpx.Response(404)

    db = FetchDb()
    s3 = FakeS3()
    store = RawStore(Settings("postgres://fake", "account", "key", "secret"), s3)
    stats = efile_fetch(db, store, httpx.Client(transport=httpx.MockTransport(handler)))

    assert stats["objects_fetched"] == 1
    assert stats["gt_lake_missing"] == 1
    assert list(s3.objects) == ["raw/irs/efile-xml/2021/202121129349301317_public.xml"]
    quarantine_calls = [call for call in db.calls if "INSERT INTO ops.quarantine" in call[0]]
    assert len(quarantine_calls) == 1
    assert quarantine_calls[0][1][1] == "gt_lake_missing"
    assert db.calls[-1][1][0] == "succeeded"
