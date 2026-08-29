"""Small database boundary used by pipeline jobs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol


DatabaseParams = Sequence[Any] | Mapping[str, Any] | None
DatabaseRows = list[dict[str, Any]]


class DatabaseGateway(Protocol):
    """The narrow database interface used by the offline-testable harness."""

    def execute(self, query: str, params: DatabaseParams = None) -> DatabaseRows: ...


class PostgresGateway:
    """Autocommitting psycopg gateway for production CLI wiring."""

    def __init__(self, database_url: str) -> None:
        # Import here so fake-backed unit tests do not need psycopg installed.
        import psycopg
        from psycopg.rows import dict_row

        self._database_url = database_url
        self._psycopg = psycopg
        self._row_factory = dict_row
        self._connection = self._open()

    def _open(self) -> Any:
        return self._psycopg.connect(
            self._database_url, autocommit=True, row_factory=self._row_factory
        )

    def _run(self, query: str, params: DatabaseParams) -> DatabaseRows:
        with self._connection.cursor() as cursor:
            cursor.execute(query, params)
            if cursor.description is None:
                return []
            return list(cursor.fetchall())

    def execute(self, query: str, params: DatabaseParams = None) -> DatabaseRows:
        try:
            return self._run(query, params)
        except (self._psycopg.OperationalError, self._psycopg.InterfaceError):
            # Neon suspends an idle compute and terminates its connections, so a
            # job that pauses between writes -- publish assembles in memory for
            # ten minutes at a stretch -- wakes to a dead socket (AdminShutdown,
            # then "the connection is closed"). Every statement is its own
            # autocommit transaction, so a terminated one never committed and
            # replaying it on a fresh connection cannot double-apply. A failure
            # on a live connection is a real fault: re-raise it untouched.
            if not self._connection.closed:
                raise
            self._reconnect()
            return self._run(query, params)

    def _reconnect(self) -> None:
        self._connection.close()
        self._connection = self._open()

    def close(self) -> None:
        self._connection.close()
