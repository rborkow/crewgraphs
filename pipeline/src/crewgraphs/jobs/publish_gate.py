"""Block publication when this pipeline chain created quarantines."""

from __future__ import annotations

from typing import Any

from ..db import DatabaseGateway
from ..runlog import IngestRun


class PublishGateFailure(RuntimeError):
    """Raised when one or more quarantines block publication."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        super().__init__(f"publish gate blocked by {len(rows)} quarantine(s)")


def publish_gate(db: DatabaseGateway, *, since: str) -> None:
    """Fail when quarantines belong to ingest runs created since ``since``."""
    with IngestRun(
        db,
        job_name="publish_gate",
        source="ops",
        params={"since": since},
    ) as run:
        rows = db.execute(
            """
            SELECT ingest_run.job_name,
                   quarantine.reason,
                   COALESCE(quarantine.details ->> 'external_key', quarantine.raw_uri)
                     AS external_key
            FROM ops.quarantine AS quarantine
            JOIN ops.ingest_run AS ingest_run
              ON ingest_run.id = quarantine.ingest_run_id
            WHERE ingest_run.created_at >= %s::timestamptz
            ORDER BY ingest_run.created_at, quarantine.created_at, quarantine.id
            """,
            (since,),
        )
        run.add_stat("quarantines", len(rows))
        if rows:
            raise PublishGateFailure(rows)


__all__ = ["PublishGateFailure", "publish_gate"]
