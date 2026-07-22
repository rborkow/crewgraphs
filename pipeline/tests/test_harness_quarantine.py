from __future__ import annotations

import json

from crewgraphs.quarantine import quarantine


class Recorder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def execute(self, query: str, params: object = None) -> list[dict[str, object]]:
        self.calls.append((query, params))
        return []


def test_quarantine_inserts_row_and_increments_run_stat() -> None:
    db = Recorder()

    quarantine(db, "run-1", "irs", "object-7", "unknown XML", "r2://bucket/key")

    assert "INSERT INTO ops.quarantine" in db.calls[0][0]
    assert json.loads(db.calls[0][1][3]) == {
        "source": "irs",
        "external_key": "object-7",
    }
    assert "'{quarantines}'" in db.calls[1][0]
