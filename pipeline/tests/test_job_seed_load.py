from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from crewgraphs.jobs.seed_load import seed_load


COHORT = Path(__file__).resolve().parents[2] / "seed/cohort.csv"


class CuratorDb:
    """Small in-memory identity store; it intentionally exposes no ops tables."""

    def __init__(self) -> None:
        self.organizations: dict[str, dict[str, Any]] = {}
        self.identifiers: dict[str, dict[str, Any]] = {}
        self.aliases: list[dict[str, Any]] = []
        self.relationships: list[dict[str, Any]] = []
        self.audit_events: list[dict[str, Any]] = []

    def execute(self, query: str, params: object = None) -> list[dict[str, Any]]:
        values = tuple(params or ())
        if "FROM core.external_identifier" in query and "WHERE namespace = 'irs_ein'" in query:
            item = self.identifiers.get(str(values[0]))
            return [item.copy()] if item else []
        if "FROM core.organization WHERE id" in query:
            return [self.organizations[str(values[0])].copy()]
        if "INSERT INTO core.organization\n" in query:
            ident = f"org-{len(self.organizations) + 1}"
            fields = ("slug", "display_name", "legal_name", "org_type", "status", "city", "state", "notes", "program_mix")
            self.organizations[ident] = {"id": ident, **dict(zip(fields, values, strict=True))}
            return [{"id": ident}]
        if "UPDATE core.organization" in query:
            fields = ("slug", "display_name", "legal_name", "org_type", "status", "city", "state", "notes", "program_mix")
            self.organizations[str(values[-1])].update(dict(zip(fields, values[:-1], strict=True)))
            return []
        if "FROM core.organization_alias" in query:
            return [row.copy() for row in self.aliases if row["organization_id"] == values[0] and row["alias"] == values[1]]
        if "INSERT INTO core.organization_alias" in query:
            item = {"id": f"alias-{len(self.aliases) + 1}", "organization_id": values[0], "alias": values[1]}
            self.aliases.append(item)
            return [{"id": item["id"]}]
        if "INSERT INTO core.external_identifier" in query:
            item = {"id": f"identifier-{len(self.identifiers) + 1}", "organization_id": values[0], "namespace": "irs_ein", "value": values[1], "verification_state": "verified", "valid_from": None, "valid_to": None}
            self.identifiers[str(values[1])] = item
            return [{"id": item["id"]}]
        if "UPDATE core.external_identifier" in query:
            item = next(row for row in self.identifiers.values() if row["id"] == values[1])
            item.update({"organization_id": values[0], "verification_state": "verified", "valid_from": None, "valid_to": None})
            return []
        if "FROM core.organization_relationship" in query:
            return [row.copy() for row in self.relationships if (row["from_organization_id"], row["to_organization_id"], row["relationship_type"]) == values]
        if "INSERT INTO core.organization_relationship" in query:
            item = {"id": f"relationship-{len(self.relationships) + 1}", "from_organization_id": values[0], "to_organization_id": values[1], "relationship_type": values[2], "notes": values[3]}
            self.relationships.append(item)
            return [{"id": item["id"]}]
        if "INSERT INTO core.audit_event" in query:
            self.audit_events.append({"actor": values[0], "action": values[1], "entity_type": values[2], "entity_id": values[3], "before": json.loads(values[4]), "after": json.loads(values[5])})
            return []
        raise AssertionError(query)


# The tests load the real curated cohort, so expectations track its row count
# rather than freezing a batch size that grows with every promotion.
def _cohort_size() -> int:
    with COHORT.open(newline="", encoding="utf-8") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def test_seed_load_creates_the_reviewed_cohort_and_audits_each_mutation() -> None:
    db = CuratorDb()
    size = _cohort_size()

    assert f"created={size}" in seed_load(db, csv_path=COHORT)

    assert len(db.organizations) == size
    assert next(org for org in db.organizations.values() if org["display_name"].startswith("Olympic Athletes"))["status"] == "candidate"
    assert all(item["verification_state"] == "verified" for item in db.identifiers.values())
    assert len(db.identifiers) == size
    c4 = db.identifiers["363508216"]["organization_id"]
    c3 = db.identifiers["272334832"]["organization_id"]
    assert [(row["from_organization_id"], row["to_organization_id"], row["relationship_type"]) for row in db.relationships] == [(c4, c3, "has_charitable_arm")]
    # One org + one display alias + one EIN identifier each, plus 1 relationship.
    assert len(db.audit_events) == size * 3 + 1


def test_seed_load_is_a_no_write_rerun() -> None:
    db = CuratorDb()
    size = _cohort_size()
    seed_load(db, csv_path=COHORT)
    first_audits = len(db.audit_events)

    assert seed_load(db, csv_path=COHORT).endswith("writes=0")
    assert len(db.audit_events) == first_audits
    assert len(db.organizations) == size
    assert len(db.aliases) == size
