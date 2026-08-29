from __future__ import annotations

from typing import Any

import psycopg
import pytest

from crewgraphs.db import PostgresGateway


class FakeCursor:
    def __init__(self, connection: "FakeConnection") -> None:
        self._connection = connection
        self.description: list[tuple[str]] | None = [("id",)]

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, *exc: object) -> bool:
        return False

    def execute(self, query: str, params: Any = None) -> None:
        self._connection.queries.append(query)
        if not self._connection.fails:
            return
        self._connection.closed = self._connection.dies
        raise psycopg.OperationalError(
            "terminating connection due to administrator command"
        )

    def fetchall(self) -> list[dict[str, Any]]:
        return [{"id": "row-1"}]


class FakeConnection:
    """A psycopg connection stand-in that can die the way Neon kills one."""

    def __init__(self, *, fails: bool = False, dies: bool = False) -> None:
        self.fails = fails
        self.dies = dies
        self.closed = False
        self.queries: list[str] = []
        self.close_calls = 0

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)

    def close(self) -> None:
        self.close_calls += 1
        self.closed = True


def _gateway(monkeypatch: pytest.MonkeyPatch, connections: list[FakeConnection]) -> PostgresGateway:
    handed = iter(connections)
    monkeypatch.setattr(psycopg, "connect", lambda *args, **kwargs: next(handed))
    return PostgresGateway("postgres://placeholder/placeholder")


def test_execute_replays_once_on_a_terminated_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dead = FakeConnection(fails=True, dies=True)
    fresh = FakeConnection()
    gateway = _gateway(monkeypatch, [dead, fresh])

    rows = gateway.execute("INSERT INTO core.review_task DEFAULT VALUES")

    assert rows == [{"id": "row-1"}]
    assert dead.close_calls == 1
    assert fresh.queries == ["INSERT INTO core.review_task DEFAULT VALUES"]


def test_execute_does_not_replay_on_a_live_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A statement that fails while the socket is healthy is a real fault, and
    # replaying it could double-apply a write that did commit.
    live = FakeConnection(fails=True, dies=False)
    spare = FakeConnection()
    gateway = _gateway(monkeypatch, [live, spare])

    with pytest.raises(psycopg.OperationalError):
        gateway.execute("SELECT 1")

    assert live.close_calls == 0
    assert spare.queries == []


def test_execute_gives_up_after_one_reconnect(monkeypatch: pytest.MonkeyPatch) -> None:
    dead = FakeConnection(fails=True, dies=True)
    still_dead = FakeConnection(fails=True, dies=True)
    gateway = _gateway(monkeypatch, [dead, still_dead])

    with pytest.raises(psycopg.OperationalError):
        gateway.execute("SELECT 1")

    assert still_dead.queries == ["SELECT 1"]
