from __future__ import annotations

import json
from typing import Any

import pytest

from crewgraphs.db import DatabaseParams, DatabaseRows
from crewgraphs.runlog import IngestRun


class Recorder:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def execute(self, query: str, params: DatabaseParams = None) -> DatabaseRows:
        self.calls.append((query, tuple(params or ())))
        if "INSERT INTO ops.ingest_run" in query:
            return [{"id": "run-1"}]
        return []


def test_ingest_run_marks_a_success_and_persists_stats() -> None:
    db = Recorder()

    with IngestRun(db, job_name="bmf_sync", source="irs", git_sha="abc") as run:
        run.add_stat("rows", 3)
        run.warn("late file")

    insert_params = db.calls[0][1]
    assert insert_params[1] == "irs"
    assert json.loads(insert_params[4]) == {}
    update_params = db.calls[-1][1]
    assert update_params[0] == "succeeded"
    assert update_params[1] is None
    assert json.loads(update_params[2]) == {"rows": 3, "warnings": ["late file"]}


def test_ingest_run_marks_a_failure_and_reraises() -> None:
    db = Recorder()

    with pytest.raises(RuntimeError, match="boom"):
        with IngestRun(db, job_name="bmf_sync", source="irs"):
            raise RuntimeError("boom")

    update_params = db.calls[-1][1]
    assert update_params[0] == "failed"
    assert update_params[1] == "boom"


class CloseOutFails(Recorder):
    """A gateway whose ``ops.ingest_run`` close-out write is dead."""

    def execute(self, query: str, params: DatabaseParams = None) -> DatabaseRows:
        if "UPDATE ops.ingest_run" in query:
            raise RuntimeError("the connection is closed")
        return super().execute(query, params)


def test_close_out_failure_does_not_bury_the_job_failure(
    capsys: pytest.CaptureFixture[str],
) -> None:
    db = CloseOutFails()

    # A Neon compute suspend kills the job mid-write and the close-out with it;
    # the AdminShutdown must still be what reaches the operator.
    with pytest.raises(RuntimeError, match="terminating connection"):
        with IngestRun(db, job_name="publish", source="ops"):
            raise RuntimeError("terminating connection due to administrator command")

    assert "could not be closed out" in capsys.readouterr().err


def test_close_out_failure_on_a_clean_run_still_raises() -> None:
    db = CloseOutFails()

    # Nothing to bury here: a run we cannot record as finished is a real fault.
    with pytest.raises(RuntimeError, match="the connection is closed"):
        with IngestRun(db, job_name="publish", source="ops"):
            pass
