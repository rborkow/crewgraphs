from __future__ import annotations

import hashlib
from io import BytesIO

import pytest

from crewgraphs.config import Settings
from crewgraphs.raw_store import (
    QuarantineableError,
    RawStore,
    register_source_record,
)


class FakeS3:
    def __init__(self) -> None:
        self.objects: dict[str, dict[str, object]] = {}
        self.puts = 0

    def head_object(self, *, Bucket: str, Key: str) -> dict[str, object]:
        if Key not in self.objects:
            raise KeyError(Key)
        data = self.objects[Key]
        return {"Metadata": data["metadata"], "ContentLength": len(data["body"])}

    def put_object(self, *, Bucket: str, Key: str, Body: bytes, ContentType: str, Metadata: dict[str, str]) -> dict[str, object]:
        self.puts += 1
        self.objects[Key] = {"body": Body, "metadata": Metadata, "content_type": ContentType}
        return {}

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, object]:
        return {"Body": BytesIO(self.objects[Key]["body"])}


def settings() -> Settings:
    return Settings("postgres://fake", "account", "key", "secret")


def test_raw_store_is_write_once() -> None:
    client = FakeS3()
    store = RawStore(settings(), client)

    first = store.put_raw("raw/irs/file.xml", b"one", "application/xml")
    again = store.put_raw("raw/irs/file.xml", b"one", "application/xml")

    assert first.checksum_sha256 == hashlib.sha256(b"one").hexdigest()
    assert again == first
    assert client.puts == 1
    assert store.get_raw("raw/irs/file.xml") == b"one"

    with pytest.raises(QuarantineableError, match="checksum conflict"):
        store.put_raw("raw/irs/file.xml", b"two", "application/xml")


def test_register_source_record_uses_the_schema_uniqueness_boundary() -> None:
    calls: list[tuple[str, object]] = []

    class FakeDb:
        def execute(self, query: str, params: object = None) -> list[dict[str, object]]:
            calls.append((query, params))
            return [{"id": "source-1"}]

    raw = RawStore(settings(), FakeS3()).put_raw("raw/irs/file.xml", b"one", "application/xml")
    source_id = register_source_record(
        FakeDb(), source="irs_990_xml", external_key="object-1", raw_object=raw
    )

    assert source_id == "source-1"
    assert "INSERT INTO core.source_record" in calls[0][0]
    assert "checksum_sha256" in calls[0][0]
