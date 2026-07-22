"""Atomically roll the public read-model pointer back one retained snapshot."""

from __future__ import annotations

from ..db import DatabaseGateway


def rollback_publish(db: DatabaseGateway) -> str:
    """Activate the newest retained superseded snapshot, or refuse safely."""
    rows = db.execute(
        """
        WITH current_snapshot AS (
            SELECT ps.id
            FROM read.published_snapshot AS pointer
            JOIN ops.publish_snapshot AS ps ON ps.id = pointer.snapshot_id
            WHERE pointer.singleton = true AND ps.status = 'active'
        ), candidate AS (
            SELECT ps.id
            FROM ops.publish_snapshot AS ps
            WHERE ps.status = 'superseded'
              AND EXISTS (
                  SELECT 1 FROM read.org_directory AS directory
                  WHERE directory.snapshot_id = ps.id
              )
            ORDER BY ps.created_at DESC, ps.id DESC
            LIMIT 1
        ), rolled_back AS (
            UPDATE ops.publish_snapshot AS ps
            SET status = 'rolled_back'
            FROM current_snapshot AS current
            WHERE ps.id = current.id
            RETURNING ps.id
        ), activated AS (
            UPDATE ops.publish_snapshot AS ps
            SET status = 'active', activated_at = NOW()
            FROM candidate
            WHERE ps.id = candidate.id
              AND EXISTS (SELECT 1 FROM rolled_back)
            RETURNING ps.id
        ), pointer AS (
            UPDATE read.published_snapshot AS published
            SET snapshot_id = activated.id, updated_at = NOW()
            FROM activated
            WHERE published.singleton = true
            RETURNING published.snapshot_id
        )
        SELECT candidate.id
        FROM candidate
        WHERE EXISTS (SELECT 1 FROM pointer)
        """
    )
    if not rows:
        raise RuntimeError("no eligible superseded publish snapshot remains")
    return str(rows[0]["id"])


__all__ = ["rollback_publish"]
