"""Lifecycle logging for entries in ``ops.ingest_run``."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, Self

from .db import DatabaseGateway


class IngestRun:
    """Create, finish, and annotate one ingestion run."""

    def __init__(
        self,
        db: DatabaseGateway,
        *,
        job_name: str,
        source: str,
        git_sha: str | None = None,
        code_version: str = "0.0.0",
        params: Mapping[str, Any] | None = None,
    ) -> None:
        self.db = db
        self.job_name = job_name
        self.source = source
        self.git_sha = git_sha or "unknown"
        self.code_version = code_version
        self.params = dict(params or {})
        self.id: str | None = None
        self._stats: dict[str, Any] = {}

    @property
    def stats(self) -> dict[str, Any]:
        """A copy of the locally accumulated stats suitable for a summary."""
        return dict(self._stats)

    def __enter__(self) -> Self:
        rows = self.db.execute(
            """
            INSERT INTO ops.ingest_run
                (job_name, source, git_sha, code_version, params, stats, status, started_at)
            VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, 'running', NOW())
            RETURNING id
            """,
            (
                self.job_name,
                self.source,
                self.git_sha,
                self.code_version,
                json.dumps(self.params),
                json.dumps(self._stats),
            ),
        )
        if not rows or "id" not in rows[0]:
            raise RuntimeError("ops.ingest_run insert did not return an id")
        self.id = str(rows[0]["id"])
        return self

    def add_stat(self, key: str, n: int = 1) -> None:
        """Accumulate a numeric stat for the run."""
        current = self._stats.get(key, 0)
        if not isinstance(current, (int, float)) or isinstance(current, bool):
            raise ValueError(f"stat {key!r} is not numeric")
        self._stats[key] = current + n

    def warn(self, message: str) -> None:
        """Record a non-fatal warning for the run summary."""
        self._stats.setdefault("warnings", []).append(message)

    def __exit__(self, exc_type: object, exc: BaseException | None, tb: object) -> bool:
        if self.id is None:
            return False
        final_stats = dict(self._stats)
        status = "succeeded"
        error: str | None = None
        if exc is not None:
            status = "failed"
            error = str(exc)
        # JSONB concatenation retains atomic stats (for example ``quarantines``)
        # written by helpers during the body of this context manager.
        self.db.execute(
            """
            UPDATE ops.ingest_run
            SET status = %s,
                error = %s,
                finished_at = NOW(),
                stats = stats || %s::jsonb
            WHERE id = %s
            """,
            (status, error, json.dumps(final_stats), self.id),
        )
        return False
