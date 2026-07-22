from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from typing import Any

from crewgraphs.config import Settings
from crewgraphs.jobs.efile_parse import efile_parse
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


class ParseDb:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

    def execute(self, query: str, params: Any = None) -> list[dict[str, Any]]:
        self.calls.append((query, params))
        if "INSERT INTO ops.ingest_run" in query:
            return [{"id": "run-parse"}]
        if "JOIN core.source_record" in query:
            return [
                {"irs_object_id": "202121129349301317", "tax_year": 2021, "source_record_id": "source-990", "raw_uri": "r2://crewgraphs-raw/raw/irs/efile-xml/2021/202121129349301317_public.xml"},
                {"irs_object_id": "202133159349200948", "tax_year": 2021, "source_record_id": "source-ez", "raw_uri": "r2://crewgraphs-raw/raw/irs/efile-xml/2021/202133159349200948_public.xml"},
                {"irs_object_id": "bad-object", "tax_year": 2021, "source_record_id": "source-bad", "raw_uri": "r2://crewgraphs-raw/raw/irs/efile-xml/2021/bad-object_public.xml"},
            ]
        return []


def _put(store: RawStore, key: str, content: bytes) -> None:
    store.put_raw(key, content, "application/xml")


def test_efile_parse_drives_validated_extractor_and_quarantines_bad_xml() -> None:
    fixtures = Path(__file__).parent / "fixtures" / "golden"
    store = RawStore(Settings("postgres://fake", "account", "key", "secret"), FakeS3())
    _put(store, "raw/irs/efile-xml/2021/202121129349301317_public.xml", (fixtures / "202121129349301317.xml").read_bytes())
    _put(store, "raw/irs/efile-xml/2021/202133159349200948_public.xml", (fixtures / "202133159349200948.xml").read_bytes())
    _put(store, "raw/irs/efile-xml/2021/bad-object_public.xml", b"this is not XML")
    db = ParseDb()

    stats = efile_parse(db, store)

    assert stats["objects_parsed"] == 2
    assert stats["parse_failures"] == 1
    inserts = [call for call in db.calls if "INSERT INTO staging.filing_extract" in call[0]]
    assert len(inserts) == 2
    inserted_concepts = {params[3]: json.loads(params[9]) for _, params in inserts}
    golden_990 = json.loads((fixtures / "202121129349301317.parsed.json").read_text())["concepts"]
    golden_ez = json.loads((fixtures / "202133159349200948.parsed.json").read_text())["concepts"]
    for name in ("total_revenue", "total_expenses", "officer_compensation"):
        assert inserted_concepts["202121129349301317"][name] == golden_990[name]
    inserted_people = {params[3]: json.loads(params[10]) for _, params in inserts}
    ceo = next(row for row in inserted_people["202121129349301317"] if row["name"] == "AMANDA KRAUS")
    assert ceo == {
        "name": "AMANDA KRAUS",
        "title": "FOUNDER & CEO",
        "comp": 185000,
        "avg_hours": "40.00",
        "other_comp": 0,
        "related_org_comp": 0,
        "role_flags": ["individual_trustee_or_director", "officer"],
    }
    assert inserted_concepts["202133159349200948"]["total_revenue"] == golden_ez["total_revenue"]
    assert inserted_concepts["202133159349200948"]["professional_fundraising_fees"] == golden_ez["professional_fundraising_fees"]
    assert inserted_concepts["202133159349200948"]["professional_fundraising_fees"]["status"] == "not_on_form"
    quarantine_calls = [call for call in db.calls if "INSERT INTO ops.quarantine" in call[0]]
    assert len(quarantine_calls) == 1
    assert quarantine_calls[0][1][1] == "parse_failure"
    candidates_query = next(query for query, _ in db.calls if "FROM staging.efile_index_row" in query)
    assert "NOT EXISTS" in candidates_query
    assert all("ON CONFLICT DO NOTHING" in query for query, _ in inserts)


def test_efile_parse_reparse_revisits_parsed_rows_and_overwrites_in_place() -> None:
    fixtures = Path(__file__).parent / "fixtures" / "golden"
    store = RawStore(Settings("postgres://fake", "account", "key", "secret"), FakeS3())
    _put(store, "raw/irs/efile-xml/2021/202121129349301317_public.xml", (fixtures / "202121129349301317.xml").read_bytes())
    _put(store, "raw/irs/efile-xml/2021/202133159349200948_public.xml", (fixtures / "202133159349200948.xml").read_bytes())
    _put(store, "raw/irs/efile-xml/2021/bad-object_public.xml", b"this is not XML")
    db = ParseDb()

    stats = efile_parse(db, store, reparse=True)

    assert stats["objects_parsed"] == 2
    candidates_query = next(query for query, _ in db.calls if "FROM staging.efile_index_row" in query)
    assert "NOT EXISTS" not in candidates_query
    inserts = [call for call in db.calls if "INSERT INTO staging.filing_extract" in call[0]]
    assert len(inserts) == 2
    for query, _ in inserts:
        assert "ON CONFLICT (irs_object_id) DO UPDATE" in query
        assert "people = EXCLUDED.people" in query
