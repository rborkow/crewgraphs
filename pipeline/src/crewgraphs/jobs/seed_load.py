"""Curator-only loader for the hand-reviewed launch cohort.

``curator_db`` is deliberately supplied by the curation entry point, which must
construct it from ``CURATOR_DATABASE_URL`` rather than ``Settings.database_url``.
The curator role has no ``ops`` grants, so this job does not use ``IngestRun``;
the per-mutation audit events are its operational trail.
"""

from __future__ import annotations

import csv
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ..db import DatabaseGateway


# Seed-time curation, not an inference from similarly named CSV rows.
CURATED_RELATIONSHIPS = (
    ("363508216", "272334832", "has_charitable_arm"),
)


def seed_load(curator_db: DatabaseGateway, *, csv_path: str | Path, actor: str = "owner") -> str:
    """Load a reviewed cohort idempotently through the curator connection."""
    created = updated = unchanged = writes = 0
    with Path(csv_path).open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    org_ids: dict[str, str] = {}
    for source in rows:
        ein = str(source["ein"])
        desired = _desired_organization(source)
        identifier_rows = curator_db.execute(
            """
            SELECT id, organization_id, namespace, value, verification_state, valid_from, valid_to
            FROM core.external_identifier
            WHERE namespace = 'irs_ein' AND value = %s AND valid_to IS NULL
            """,
            (ein,),
        )
        if len(identifier_rows) > 1:
            raise ValueError(f"EIN {ein} has more than one active identity link")
        current_identifier = identifier_rows[0] if identifier_rows else None
        current_org: dict[str, Any] | None = None
        if current_identifier:
            org_rows = curator_db.execute(
                """
                SELECT id, slug, display_name, legal_name, org_type, status, city, state, notes
                FROM core.organization WHERE id = %s
                """,
                (current_identifier["organization_id"],),
            )
            if len(org_rows) != 1:
                raise ValueError(f"EIN {ein} points to a missing or ambiguous organization")
            current_org = org_rows[0]

        if current_org is None:
            inserted = curator_db.execute(
                """
                INSERT INTO core.organization
                    (slug, display_name, legal_name, org_type, status, city, state, notes, program_mix)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                _organization_values(desired),
            )
            organization_id = str(inserted[0]["id"])
            _audit(curator_db, actor, "seed_create_org", "organization", organization_id, None, _organization_state(desired))
            created += 1
            writes += 1
        else:
            organization_id = str(current_org["id"])
            before = _organization_state(current_org)
            after = _organization_state(desired)
            if before != after:
                curator_db.execute(
                    """
                    UPDATE core.organization
                    SET slug = %s, display_name = %s, legal_name = %s, org_type = %s,
                        status = %s, city = %s, state = %s, notes = %s, program_mix = %s, updated_at = NOW()
                    WHERE id = %s
                    """,
                    (*_organization_values(desired), organization_id),
                )
                _audit(curator_db, actor, "seed_update_org", "organization", organization_id, before, after)
                updated += 1
                writes += 1
            else:
                unchanged += 1
        org_ids[ein] = organization_id

        writes += _ensure_alias(curator_db, actor, organization_id, source["display_name"])
        writes += _ensure_identifier(curator_db, actor, organization_id, current_identifier, ein)

    for from_ein, to_ein, relationship_type in CURATED_RELATIONSHIPS:
        from_id, to_id = org_ids[from_ein], org_ids[to_ein]
        existing = curator_db.execute(
            """
            SELECT id, from_organization_id, to_organization_id, relationship_type, notes
            FROM core.organization_relationship
            WHERE from_organization_id = %s AND to_organization_id = %s AND relationship_type = %s
            """,
            (from_id, to_id, relationship_type),
        )
        if not existing:
            inserted = curator_db.execute(
                """
                INSERT INTO core.organization_relationship
                    (from_organization_id, to_organization_id, relationship_type, notes)
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (from_id, to_id, relationship_type, "Seed-time curated Lincoln c4/c3 relationship."),
            )
            after = {
                "from_organization_id": from_id,
                "to_organization_id": to_id,
                "relationship_type": relationship_type,
                "notes": "Seed-time curated Lincoln c4/c3 relationship.",
            }
            _audit(curator_db, actor, "seed_create_relationship", "organization_relationship", str(inserted[0]["id"]), None, after)
            writes += 1

    summary = f"seed_load: created={created} updated={updated} unchanged={unchanged} writes={writes}"
    print(summary)
    return summary


def _desired_organization(row: Mapping[str, str]) -> dict[str, Any]:
    notes = row.get("notes", "")
    program_mix = [part for part in row.get("program_mix", "").split("|") if part]
    return {
        "slug": _slug(row["display_name"]),
        "display_name": row["display_name"],
        "legal_name": None,
        "org_type": row["org_type"],
        "status": "candidate" if re.search(r"\b(?:exclude|dormant)\b", notes, re.IGNORECASE) else "included",
        "city": row.get("city") or None,
        "state": row.get("state") or None,
        "notes": notes or None,
        "program_mix": program_mix,
    }


def _organization_state(row: Mapping[str, Any]) -> dict[str, Any]:
    state = {key: row.get(key) for key in ("slug", "display_name", "legal_name", "org_type", "status", "city", "state", "notes")}
    state["program_mix"] = list(row.get("program_mix") or [])
    return state


def _organization_values(state: Mapping[str, Any]) -> tuple[Any, ...]:
    return tuple(state[key] for key in ("slug", "display_name", "legal_name", "org_type", "status", "city", "state", "notes", "program_mix"))


def _ensure_alias(db: DatabaseGateway, actor: str, organization_id: str, alias: str) -> int:
    rows = db.execute(
        "SELECT id, organization_id, alias FROM core.organization_alias WHERE organization_id = %s AND alias = %s",
        (organization_id, alias),
    )
    if rows:
        return 0
    inserted = db.execute(
        "INSERT INTO core.organization_alias (organization_id, alias) VALUES (%s, %s) RETURNING id",
        (organization_id, alias),
    )
    _audit(db, actor, "seed_create_alias", "organization_alias", str(inserted[0]["id"]), None, {"organization_id": organization_id, "alias": alias})
    return 1


def _ensure_identifier(db: DatabaseGateway, actor: str, organization_id: str, current: Mapping[str, Any] | None, ein: str) -> int:
    desired = {"organization_id": organization_id, "namespace": "irs_ein", "value": ein, "verification_state": "verified", "valid_from": None, "valid_to": None}
    if current is None:
        inserted = db.execute(
            """
            INSERT INTO core.external_identifier (organization_id, namespace, value, verification_state)
            VALUES (%s, 'irs_ein', %s, 'verified') RETURNING id
            """,
            (organization_id, ein),
        )
        _audit(db, actor, "seed_create_identifier", "external_identifier", str(inserted[0]["id"]), None, desired)
        return 1
    before = {key: current.get(key) for key in desired}
    if before == desired:
        return 0
    db.execute(
        """
        UPDATE core.external_identifier
        SET organization_id = %s, verification_state = 'verified', valid_from = NULL, valid_to = NULL
        WHERE id = %s
        """,
        (organization_id, current["id"]),
    )
    _audit(db, actor, "seed_update_identifier", "external_identifier", str(current["id"]), before, desired)
    return 1


def _audit(db: DatabaseGateway, actor: str, action: str, entity_type: str, entity_id: str, before: object, after: object) -> None:
    db.execute(
        """
        INSERT INTO core.audit_event (actor, action, entity_type, entity_id, before, after)
        VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb)
        """,
        (actor, action, entity_type, entity_id, json.dumps(before), json.dumps(after)),
    )


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


__all__ = ["CURATED_RELATIONSHIPS", "seed_load"]
