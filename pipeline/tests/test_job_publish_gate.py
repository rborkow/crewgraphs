from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from typer.testing import CliRunner

import crewgraphs.__main__ as cli


class FakeDb:
    def __init__(self, quarantines: list[dict[str, Any]]) -> None:
        self.quarantines = quarantines
        self.final_stats: dict[str, Any] = {}
        self.final_status = ""
        self.closed = False

    def close(self) -> None:
        self.closed = True

    def execute(self, query: str, params: object = None) -> list[dict[str, Any]]:
        values = tuple(params or ())
        if "INSERT INTO ops.ingest_run" in query:
            return [{"id": "run-publish-gate"}]
        if "FROM ops.quarantine AS quarantine" in query:
            since = datetime.fromisoformat(str(values[0]).replace("Z", "+00:00"))
            return [
                {
                    "job_name": row["job_name"],
                    "reason": row["reason"],
                    "external_key": row["external_key"],
                }
                for row in self.quarantines
                if datetime.fromisoformat(row["run_created_at"].replace("Z", "+00:00"))
                >= since
            ]
        if "SET status = %s" in query:
            self.final_status = str(values[0])
            self.final_stats = json.loads(values[2])
            return []
        raise AssertionError(query)


def _invoke(monkeypatch, db: FakeDb, since: str):
    monkeypatch.setattr(cli, "PostgresGateway", lambda _url: db)
    monkeypatch.setattr(
        cli.Settings,
        "from_env",
        classmethod(lambda _cls: type("Settings", (), {"database_url": "fake"})()),
    )
    return CliRunner().invoke(cli.app, ["publish-gate", "--since", since])


def test_publish_gate_clean_run_exits_zero(monkeypatch) -> None:
    db = FakeDb([])

    result = _invoke(monkeypatch, db, "2026-07-05T09:00:00Z")

    assert result.exit_code == 0
    assert result.output == "Publish gate clear: no quarantines since 2026-07-05T09:00:00Z.\n"
    assert db.final_status == "succeeded"
    assert db.final_stats == {"quarantines": 0}
    assert db.closed


def test_publish_gate_lists_quarantine_after_since_and_fails(monkeypatch) -> None:
    db = FakeDb(
        [
            {
                "run_created_at": "2026-07-05T09:01:00Z",
                "job_name": "efile_parse",
                "reason": "invalid_xml",
                "external_key": "202513219349307836",
            }
        ]
    )

    result = _invoke(monkeypatch, db, "2026-07-05T09:00:00Z")

    assert result.exit_code == 1
    assert result.output == (
        "Publish gate blocked by 1 quarantine(s):\n"
        "- job_name=efile_parse reason=invalid_xml external_key=202513219349307836\n"
    )
    assert db.final_status == "failed"
    assert db.final_stats == {"quarantines": 1}


def test_publish_gate_ignores_quarantine_before_since(monkeypatch) -> None:
    db = FakeDb(
        [
            {
                "run_created_at": "2026-07-05T08:59:59Z",
                "job_name": "bmf_sync",
                "reason": "bad_row",
                "external_key": "237397498",
            }
        ]
    )

    result = _invoke(monkeypatch, db, "2026-07-05T09:00:00Z")

    assert result.exit_code == 0
    assert "Publish gate clear" in result.output
    assert db.final_status == "succeeded"
