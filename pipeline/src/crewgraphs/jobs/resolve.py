"""Attach staged IRS observations to curator-owned identities without mutating them."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping
from difflib import SequenceMatcher
from typing import Any

from ..db import DatabaseGateway
from ..runlog import IngestRun
from ..summary import emit_summary, render_summary
from . import is_discovery_name, verified_irs_eins


def resolve(db: DatabaseGateway) -> str:
    """Resolve staged EINs using read-only identity lookups and append-only ops."""
    with IngestRun(db, job_name="resolve", source="identity") as run:
        for key in ("resolved_eins", "conflicts", "candidates", "ignored_eins"):
            run.add_stat(key, 0)
        verified = verified_irs_eins(db)
        organizations = _organizations_by_ein(db, verified)
        for staged in _staged_eins(db):
            ein = str(staged["ein"])
            name = str(staged.get("staged_name") or "")
            matches = organizations.get(ein, [])
            if len(matches) == 1:
                org = matches[0]
                ratio = name_similarity(name, _org_names(org))
                if ratio >= 0.6:
                    details = {"ein": ein, "matched_name": name, "ratio": ratio}
                    if not _prior_attach(db, str(org["id"]), details):
                        _audit_attach(db, str(org["id"]), details)
                    run.add_stat("resolved_eins")
                else:
                    details = {"ein": ein, "staged_name": name, "org_names": _org_names(org), "ratio": ratio}
                    if not _open_task(db, str(org["id"]), "ein_conflict", details):
                        _review_task(db, "organization", str(org["id"]), "ein_conflict", details)
                    run.add_stat("conflicts")
            elif is_discovery_name(name):
                details = {"ein": ein, "staged_name": name, "candidate": "discovery"}
                entity_id = str(staged["entity_id"])
                if not _open_task(db, entity_id, "inclusion", details):
                    _review_task(db, "staged_ein", entity_id, "inclusion", details)
                run.add_stat("candidates")
            else:
                run.add_stat("ignored_eins")
    summary = render_summary(job_name="resolve", run_id=run.id or "", status="succeeded", counts=run.stats)
    emit_summary(summary)
    return summary


def _organizations_by_ein(db: DatabaseGateway, verified: set[str]) -> dict[str, list[dict[str, Any]]]:
    if not verified:
        return {}
    rows = db.execute(
        """
        SELECT identifier.value AS ein, organization.id, organization.display_name,
               organization.legal_name, organization_alias.alias
        FROM core.external_identifier AS identifier
        JOIN core.organization AS organization ON organization.id = identifier.organization_id
        LEFT JOIN core.organization_alias ON organization_alias.organization_id = organization.id
        WHERE identifier.namespace = 'irs_ein'
          AND identifier.verification_state = 'verified'
          AND identifier.valid_to IS NULL
          AND identifier.value = ANY(%s)
        """,
        (list(verified),),
    )
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        ein = str(row["ein"])
        key = f"{ein}:{row['id']}"
        org = indexed.setdefault(key, {"id": row["id"], "display_name": row.get("display_name"), "legal_name": row.get("legal_name"), "aliases": []})
        if row.get("alias"):
            org["aliases"].append(str(row["alias"]))
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for key, org in indexed.items():
        result[key.split(":", 1)[0]].append(org)
    return dict(result)


def _staged_eins(db: DatabaseGateway) -> list[dict[str, Any]]:
    return db.execute(
        """
        WITH staged AS (
            SELECT id AS entity_id, ein, NULL::text AS staged_name FROM staging.filing_extract
            UNION ALL
            SELECT id, ein, COALESCE(raw_row->>'NAME', raw_row->>'NAME_EIN', raw_row->>'name') FROM staging.bmf_row
            UNION ALL
            SELECT id, ein, COALESCE(raw_row->>'NAME', raw_row->>'FILER_NAME', raw_row->>'name') FROM staging.epostcard_row
        )
        SELECT DISTINCT ON (ein) entity_id, ein, staged_name
        FROM staged
        WHERE ein IS NOT NULL
        ORDER BY ein, staged_name NULLS LAST, entity_id
        """
    )


def _org_names(org: Mapping[str, Any]) -> list[str]:
    values = [org.get("display_name"), org.get("legal_name"), *org.get("aliases", [])]
    return [str(value) for value in values if value]


def name_similarity(staged_name: str, org_names: Iterable[str]) -> float:
    """Return the best token-set SequenceMatcher ratio for the supplied names."""
    staged = _token_sort(staged_name)
    if not staged:
        return 0.0
    return max((SequenceMatcher(None, staged, _token_sort(name)).ratio() for name in org_names), default=0.0)


def _token_sort(value: str) -> str:
    return " ".join(sorted(set(re.findall(r"[a-z0-9]+", value.lower()))))


def _prior_attach(db: DatabaseGateway, organization_id: str, details: Mapping[str, Any]) -> bool:
    rows = db.execute(
        """
        SELECT 1 FROM core.audit_event
        WHERE action = 'auto_attach_ein' AND entity_type = 'organization' AND entity_id = %s
          AND after = %s::jsonb
        LIMIT 1
        """,
        (organization_id, json.dumps(details)),
    )
    return bool(rows)


def _audit_attach(db: DatabaseGateway, organization_id: str, details: Mapping[str, Any]) -> None:
    db.execute(
        """
        INSERT INTO core.audit_event (actor, action, entity_type, entity_id, before, after)
        VALUES ('pipeline_rw', 'auto_attach_ein', 'organization', %s, NULL, %s::jsonb)
        """,
        (organization_id, json.dumps(details)),
    )


def _open_task(db: DatabaseGateway, entity_id: str, task_type: str, details: Mapping[str, Any]) -> bool:
    rows = db.execute(
        """
        SELECT 1 FROM core.review_task
        WHERE entity_id = %s AND task_type = %s AND status = 'open' AND details = %s::jsonb
        LIMIT 1
        """,
        (entity_id, task_type, json.dumps(details)),
    )
    return bool(rows)


def _review_task(db: DatabaseGateway, entity_type: str, entity_id: str, task_type: str, details: Mapping[str, Any]) -> None:
    db.execute(
        """
        INSERT INTO core.review_task (entity_type, entity_id, task_type, details)
        VALUES (%s, %s, %s, %s::jsonb)
        """,
        (entity_type, entity_id, task_type, json.dumps(details)),
    )


__all__ = ["name_similarity", "resolve"]
