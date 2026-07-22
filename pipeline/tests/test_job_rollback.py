from __future__ import annotations

import pytest

from crewgraphs.jobs.rollback import rollback_publish


class RollbackFake:
    def __init__(self, eligible: str | None) -> None:
        self.eligible = eligible
        self.calls: list[tuple[str, object]] = []

    def execute(self, query: str, params: object = None) -> list[dict[str, str]]:
        compact = " ".join(query.split())
        self.calls.append((compact, params))
        return [{"id": self.eligible}] if self.eligible is not None else []


def test_rollback_repoints_to_prior_retained_snapshot_in_one_statement() -> None:
    db = RollbackFake("snapshot-prior")

    assert rollback_publish(db) == "snapshot-prior"
    assert len(db.calls) == 1
    query, params = db.calls[0]
    assert params is None
    assert query.startswith("WITH current_snapshot AS")
    assert "ps.status = 'superseded'" in query
    assert "FROM read.org_directory" in query
    assert "SET status = 'rolled_back'" in query
    assert "SET status = 'active'" in query
    assert "UPDATE read.published_snapshot" in query


def test_rollback_refuses_when_no_retained_superseded_snapshot_is_eligible() -> None:
    db = RollbackFake(None)

    with pytest.raises(RuntimeError, match="no eligible superseded"):
        rollback_publish(db)
    assert len(db.calls) == 1

