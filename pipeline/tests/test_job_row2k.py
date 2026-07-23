from __future__ import annotations

import json
import re
from datetime import date
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any

import httpx
import typer
from typer.testing import CliRunner

from crewgraphs.config import Settings
from crewgraphs.jobs.row2k import (
    GAP_REPORT_SQL,
    discover_archive_urls,
    parse_directory,
    parse_years,
    provider_from_host,
    provider_key,
    register,
    results_gap_report,
    row2k_index_sync,
)
from crewgraphs.raw_store import RawStore


ROOT = Path(__file__).resolve().parents[2]
REAL_FIXTURE = ROOT / "pipeline/tests/fixtures/row2k/results-2025-real.html"
# This deliberately synthetic slice covers legacy heading markup, a multi-day
# date heading, and ``Location:`` tails that are absent from the real capture.
SYNTHETIC_VARIANTS_FIXTURE = ROOT / "pipeline/tests/fixtures/row2k/results-index-slice.html"


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
    def __init__(self, gap_rows: list[dict[str, Any]] | None = None) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []
        self.quarantines: list[tuple[Any, ...]] = []
        self.staged: list[tuple[Any, ...]] = []
        self.links: list[tuple[Any, ...]] = []
        self.final_stats: dict[str, Any] = {}
        self.gap_rows = gap_rows or []

    def execute(self, query: str, params: object = None) -> list[dict[str, Any]]:
        values = tuple(params or ())
        self.calls.append((query, values))
        if "INSERT INTO ops.ingest_run" in query:
            return [{"id": "run-1"}]
        if "INSERT INTO core.source_record" in query:
            return [{"id": "source-1"}]
        if "INSERT INTO staging.row2k_index_page" in query:
            self.staged.append(values)
        if "INSERT INTO core.regatta_source_link" in query:
            self.links.append(values)
            return [{"id": f"link-{len(self.links)}"}]
        if "INSERT INTO ops.quarantine" in query:
            self.quarantines.append(values)
        if "WITH registry AS" in query:
            return self.gap_rows
        if "SET status = %s" in query:
            self.final_stats = json.loads(values[2])
        return []


def _store(s3: FakeS3) -> RawStore:
    return RawStore(Settings("postgres://fake", "account", "key", "secret"), s3)


def test_parse_real_directory_tracks_table_dates_span_categories_and_select_years() -> None:
    links = parse_directory(REAL_FIXTURE.read_bytes(), "https://www.row2k.com/results/?year=2025")

    assert [(item.regatta_name, item.event_date, item.category, item.location) for item in links] == [
        ("23rd Annual Central Catholic Biathlon", date(2025, 12, 12), "Mixed Regatta", "Pittsburgh, PA"),
        ("Long Beach Bill Lockyer Christmas Regatta", date(2025, 12, 7), "Mixed Regatta", "Long Beach CA"),
        ("Head of the Lagoon - Juniors", date(2025, 11, 16), "Head Race", "Foster City, CA"),
        ("RowOn Championships", date(2025, 7, 20), "Club", "Welland, ON"),
        ("USRowing RowFest National Championships", date(2025, 7, 20), "Mixed Regatta", "Ypsilanti, MI"),
        ("Cromwell Cup", date(2025, 7, 20), "Mixed Regatta", "Cambridge, MA"),
    ]
    assert [item.outbound_host for item in links] == [
        "www.row2k.com",
        "clockcaster.com",
        "legacy.herenow.com",
        "www.crewtimer.com",
        "usrowing.regatta.time-team.com",
        "legacy.herenow.com",
    ]
    assert [item.provider for item in links] == [None, None, "herenow", "crewtimer", "time_team", "herenow"]
    assert links[0].outbound_url.startswith("https://www.row2k.com/results/resultspage.cfm")
    assert all("trc.live" not in item.outbound_url for item in links)
    archives = discover_archive_urls(REAL_FIXTURE.read_bytes())
    assert {year: archives[year] for year in (2024, 2025)} == {
        2024: "https://www.row2k.com/results/index.cfm?year=2024",
        2025: "https://www.row2k.com/results/index.cfm?year=2025",
    }


def test_synthetic_variants_cover_multi_day_heading_markup_and_live_video() -> None:
    links = parse_directory(SYNTHETIC_VARIANTS_FIXTURE.read_bytes(), "https://www.row2k.com/results/")

    assert [(item.event_date, item.category, item.location) for item in links[:3]] == [
        (date(2026, 5, 30), "JUNIOR", "Sarasota, FL"),
        (date(2026, 5, 30), "JUNIOR", "Lowell, MA"),
        (date(2026, 5, 30), "MASTERS", "Worcester, MA"),
    ]
    assert all("video.example.test" not in item.outbound_url for item in links)
    assert discover_archive_urls(SYNTHETIC_VARIANTS_FIXTURE.read_bytes()) == {
        2024: "https://www.row2k.com/results/?year=2024",
        2025: "https://www.row2k.com/results/?year=2025",
    }


def test_provider_host_mapping_and_native_key_parsing() -> None:
    assert provider_from_host("usrowing.regatta.time-team.com") == "time_team"
    assert provider_from_host("club.time-team.com") == "time_team"
    assert provider_from_host("bigresults.herenow.com") == "herenow"
    assert provider_from_host("www.crewtimer.com") == "crewtimer"
    assert provider_from_host("results.regattatiming.com") == "regattatiming"
    assert provider_from_host("example.test") is None
    assert provider_key("https://legacy.herenow.com/#/races/21464") == "21464"
    assert provider_key("https://usrowing.regatta.time-team.com/youth-nats/2026/results") == "youth-nats/2026"
    assert provider_key("https://www.crewtimer.com/regatta/r16088") == "r16088"
    assert provider_key("https://results.regattatiming.com/summary.jsp?raceId=644") == "644"


def test_index_sync_stores_raw_page_stages_and_inserts_facts() -> None:
    body = REAL_FIXTURE.read_bytes()
    s3, db = FakeS3(), FakeDb()
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        run_id = row2k_index_sync(
            db,
            _store(s3),
            http,
            years=[2025],
            retrieved_date=date(2025, 12, 12),
            sleep=sleeps.append,
        )

    assert run_id == "run-1"
    assert sleeps == []
    assert list(s3.objects) == ["raw/row2k/results-index/2025/2025-12-12.html"]
    assert len(db.staged) == 1
    assert len(db.links) == 6
    assert db.links[0][0:8] == (
        "23rd Annual Central Catholic Biathlon",
        date(2025, 12, 12),
        "Mixed Regatta",
        "Pittsburgh, PA",
        "https://www.row2k.com/results/resultspage.cfm?UID=C7BCD9B4118CE4652FF8FCE00C258244&cat=6",
        "www.row2k.com",
        None,
        "https://www.row2k.com/results/",
    )
    assert db.final_stats == {
        "pages_fetched": 1,
        "links_seen": 6,
        "links_inserted": 6,
        "quarantines": 0,
    }
    insert_query = next(query for query, _ in db.calls if "INSERT INTO core.regatta_source_link" in query)
    assert "ON CONFLICT ON CONSTRAINT regatta_source_link_event_date_outbound_url_uniq" in insert_query


def test_index_sync_403_quarantines_and_stops_without_retrying() -> None:
    s3, db = FakeS3(), FakeDb()
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        return httpx.Response(403)

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        row2k_index_sync(
            db,
            _store(s3),
            http,
            years=[2026],
            retrieved_date=date(2026, 7, 23),
        )

    assert requests == ["https://www.row2k.com/results/"]
    assert db.quarantines[0][1] == "row2k_blocked"
    assert not s3.objects
    assert not db.staged
    assert db.final_stats["quarantines"] == 1


def test_gap_report_uses_provider_year_coverage_rows_and_run_stats() -> None:
    db = FakeDb(
        [
            {"provider": "herenow", "year": 2025, "covered": 4, "uncovered": 2},
            {"provider": "time_team", "year": 2026, "covered": 7, "uncovered": 1},
        ]
    )
    output = StringIO()

    report = results_gap_report(db, stdout=output)

    assert report == (
        "provider\tyear\tcovered\tuncovered\n"
        "herenow\t2025\t4\t2\n"
        "time_team\t2026\t7\t1"
    )
    assert output.getvalue() == report + "\n"
    assert db.final_stats == {"covered": 11, "uncovered": 3, "provider_year_rows": 2}
    assert "SELECT DISTINCT source, external_key\n              FROM core.regatta" in GAP_REPORT_SQL
    assert "LEFT JOIN (" in GAP_REPORT_SQL


def test_gap_report_sql_key_patterns_match_provider_key() -> None:
    cases = [
        ("https://legacy.herenow.com/results/#/races/21464/results", "#/races/([0-9]+)"),
        ("https://usrowing.regatta.time-team.com/youth-nats/2026/results", "https?://[^/]+/([^/]+/(?:19|20)[0-9]{2})(?:/|$)"),
        ("https://www.crewtimer.com/regatta/r16088", "/regatta/(r[0-9]+)(?:/|$)"),
        ("https://results.regattatiming.com/summary.jsp?raceId=644", "[?&]raceId=([^&]+)"),
    ]

    for url, sql_pattern in cases:
        match = re.search(sql_pattern, url)
        assert match is not None
        assert match.group(1) == provider_key(url)
        assert sql_pattern in GAP_REPORT_SQL


def test_year_range_parser_and_registry_schema_have_no_result_content_columns() -> None:
    assert parse_years("1997-1998,2026") == [1997, 1998, 2026]
    migration = (ROOT / "db/migrations/015_row2k_registry.sql").read_text()
    table = migration.split("CREATE TABLE core.regatta_source_link (", 1)[1].split(");", 1)[0]
    columns = {
        line.strip().split()[0]
        for line in table.splitlines()
        if line.startswith("  ")
        and not line.strip().startswith(("CONSTRAINT", "FOREIGN", "UNIQUE"))
    }
    assert columns == {
        "id",
        "regatta_name",
        "event_date",
        "category",
        "location",
        "outbound_url",
        "outbound_host",
        "provider",
        "credit_url",
        "source_record_id",
        "retrieved_at",
        "created_at",
    }
    assert not columns & {"raw", "result", "entry", "person_name", "time_ms", "position", "splits"}
    assert "UNIQUE NULLS NOT DISTINCT (event_date, outbound_url)" in migration


def test_register_exposes_the_two_row2k_commands() -> None:
    app = typer.Typer()
    register(app)

    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "row2k-index-sync" in result.output
    assert "results-gap-report" in result.output
