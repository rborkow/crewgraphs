from __future__ import annotations

import json
from typing import Any

from crewgraphs.jobs.resolve import resolve


class ResolveDb:
    def __init__(self, *, staged: list[dict[str, Any]], organizations: list[dict[str, Any]]) -> None:
        self.staged = staged
        self.organizations = organizations
        self.audit_events: list[dict[str, Any]] = []
        self.review_tasks: list[dict[str, Any]] = []
        self.final_stats: dict[str, Any] = {}

    def execute(self, query: str, params: object = None) -> list[dict[str, Any]]:
        values = tuple(params or ())
        if "INSERT INTO ops.ingest_run" in query:
            return [{"id": "run-1"}]
        if "SELECT value AS ein" in query:
            return [{"ein": item["ein"]} for item in self.organizations]
        if "JOIN core.organization AS organization" in query:
            rows: list[dict[str, Any]] = []
            for item in self.organizations:
                aliases = item.get("aliases") or [None]
                rows.extend({"ein": item["ein"], "id": item["id"], "display_name": item["display_name"], "legal_name": item.get("legal_name"), "alias": alias} for alias in aliases)
            return rows
        if "WITH staged AS" in query:
            return self.staged
        if "FROM core.audit_event" in query and "auto_attach_ein" in query:
            wanted = json.loads(values[1])
            return [{"exists": 1}] if any(item["entity_id"] == values[0] and item["after"] == wanted for item in self.audit_events) else []
        if "INSERT INTO core.audit_event" in query:
            self.audit_events.append({"entity_id": values[0], "after": json.loads(values[1])})
            return []
        if "FROM core.review_task" in query:
            wanted = json.loads(values[2])
            return [{"exists": 1}] if any(item["entity_id"] == values[0] and item["task_type"] == values[1] and item["details"] == wanted for item in self.review_tasks) else []
        if "INSERT INTO core.review_task" in query:
            self.review_tasks.append({"entity_type": values[0], "entity_id": values[1], "task_type": values[2], "details": json.loads(values[3])})
            return []
        if "SET status = %s" in query:
            self.final_stats = json.loads(values[2])
            return []
        raise AssertionError(query)


def _mapped(staged_name: str) -> ResolveDb:
    return ResolveDb(staged=[{"entity_id": "00000000-0000-0000-0000-000000000001", "ein": "237397498", "staged_name": staged_name}], organizations=[{"ein": "237397498", "id": "00000000-0000-0000-0000-000000000099", "display_name": "Vesper Boat Club", "legal_name": None, "aliases": ["Vesper Boat Club"]}])


def test_resolve_auto_attaches_good_name_once_across_reruns() -> None:
    db = _mapped("Vesper Boat Club Inc")

    assert "resolved_eins" in resolve(db)
    resolve(db)

    assert len(db.audit_events) == 1
    assert db.audit_events[0]["after"]["ein"] == "237397498"
    assert db.final_stats["resolved_eins"] == 1


def test_resolve_creates_conflict_for_a_bad_mapped_name() -> None:
    db = _mapped("Completely Different Foundation")

    resolve(db)

    assert len(db.review_tasks) == 1
    assert db.review_tasks[0]["task_type"] == "ein_conflict"
    assert db.review_tasks[0]["details"]["ratio"] < 0.6
    assert db.final_stats["conflicts"] == 1


def test_resolve_creates_and_deduplicates_an_unmapped_discovery_task() -> None:
    db = ResolveDb(staged=[{"entity_id": "00000000-0000-0000-0000-000000000002", "ein": "999999999", "staged_name": "River City Rowing"}], organizations=[])

    resolve(db)
    resolve(db)

    assert len(db.review_tasks) == 1
    assert db.review_tasks[0]["task_type"] == "inclusion"
    assert db.final_stats["candidates"] == 1


def test_resolve_ignores_unmapped_nondiscovery_rows() -> None:
    db = ResolveDb(staged=[{"entity_id": "00000000-0000-0000-0000-000000000003", "ein": "888888888", "staged_name": "Neighborhood Food Pantry"}], organizations=[])

    resolve(db)

    assert db.review_tasks == []
    assert db.final_stats["ignored_eins"] == 1
