from __future__ import annotations

from crewgraphs.__main__ import run_report_job
from crewgraphs.config import Settings


class FakeGateway:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def execute(self, query: str, params: object = None) -> list[dict[str, object]]:
        self.calls.append((query, params))
        if "INSERT INTO ops.ingest_run" in query:
            return [{"id": "run-1"}]
        if "FROM ops.ingest_run" in query:
            return [{"count": 12}]
        if "FROM core.source_record" in query:
            return [{"count": 34}]
        if "FROM ops.quarantine" in query:
            return [{"count": 2}]
        return []


def test_run_report_uses_the_ingest_lifecycle_and_renders_counts() -> None:
    db = FakeGateway()
    settings = Settings("postgres://fake", "account", "key", "secret", git_sha="abc")

    summary = run_report_job(db, settings)

    assert "CrewGraphs pipeline: `run_report`" in summary
    assert "source_records: **34**" in summary
    assert "Quarantines: **2**" in summary
    assert any("UPDATE ops.ingest_run" in query for query, _ in db.calls)
