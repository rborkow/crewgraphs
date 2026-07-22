"""Quarantine writer for recoverable input failures."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from .db import DatabaseGateway


def quarantine(
    db: DatabaseGateway,
    run_id: str,
    source: str,
    external_key: str,
    reason: str,
    raw_uri: str | None = None,
    details: Mapping[str, Any] | None = None,
) -> None:
    """Insert a quarantine row and atomically increment the run's count.

    ``ops.quarantine`` records only reason, URI, and details, so the source and
    source-system key are retained in its JSONB ``details`` column.
    """
    payload = {"source": source, "external_key": external_key, **(details or {})}
    db.execute(
        """
        INSERT INTO ops.quarantine (ingest_run_id, reason, raw_uri, details)
        VALUES (%s, %s, %s, %s::jsonb)
        """,
        (run_id, reason, raw_uri or "", json.dumps(payload)),
    )
    db.execute(
        """
        UPDATE ops.ingest_run
        SET stats = jsonb_set(
            stats,
            '{quarantines}',
            to_jsonb(COALESCE((stats ->> 'quarantines')::integer, 0) + 1),
            true
        )
        WHERE id = %s
        """,
        (run_id,),
    )
