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

        self._connection = psycopg.connect(
            database_url, autocommit=True, row_factory=dict_row
        )

    def execute(self, query: str, params: DatabaseParams = None) -> DatabaseRows:
        with self._connection.cursor() as cursor:
            cursor.execute(query, params)
            if cursor.description is None:
                return []
            return list(cursor.fetchall())

    def close(self) -> None:
        self._connection.close()
