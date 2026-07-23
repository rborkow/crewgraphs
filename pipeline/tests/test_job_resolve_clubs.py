from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from crewgraphs.jobs.resolve_clubs import _open_link_candidate, club_curation, resolve_clubs


class ResolveClubsDb:
    def __init__(
        self,
        *,
        clubs: list[dict[str, Any]],
        organizations: list[dict[str, Any]],
        bmf: list[dict[str, Any]] | None = None,
        exact: set[tuple[str, str]] | None = None,
        regatta_refs: list[dict[str, str]] | None = None,
    ) -> None:
        self.clubs = clubs
        self.organizations = organizations
        self.bmf = bmf or []
        self.exact = exact or set()
        self.regatta_refs = regatta_refs or []
        self.audit_events: list[dict[str, Any]] = []
        self.review_tasks: list[dict[str, Any]] = []
        self.final_stats: dict[str, Any] = {}
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def execute(self, query: str, params: object = None) -> list[dict[str, Any]]:
        values = tuple(params or ())
        self.calls.append((query, values))
        if "INSERT INTO ops.ingest_run" in query:
            return [{"id": "run-clubs"}]
        if "FROM core.provider_club AS club" in query:
            if not self.regatta_refs:
                return self.clubs
            rows = []
            for club in self.clubs:
                regatta_count = len(
                    {
                        (ref["source"], ref["external_key"])
                        for ref in self.regatta_refs
                        if ref["club_id"] == club["id"]
                    }
                )
                rows.append({**club, "regatta_count": regatta_count})
            return rows
        if "FROM core.organization AS organization" in query:
            rows: list[dict[str, Any]] = []
            for org in self.organizations:
                for alias in org.get("aliases") or [None]:
                    rows.append({**org, "alias": alias})
            return rows
        if "FROM staging.bmf_row AS bmf" in query:
            return self.bmf
        if "namespace = 'time_team_club'" in query and "SELECT 1" in query:
            return [{"exists": 1}] if ("time_team", str(values[0])) in self.exact else []
        if "alias_normalized" in query:
            return [{"exists": 1}] if ("alias", str(values[0])) in self.exact else []
        if "FROM core.audit_event" in query:
            wanted = json.loads(values[1])
            return [{"exists": 1}] if any(item["entity_id"] == values[0] and item["after"] == wanted for item in self.audit_events) else []
        if "INSERT INTO core.audit_event" in query:
            self.audit_events.append({"entity_id": values[0], "after": json.loads(values[1])})
            return []
        if "rejected_organization_id" in query and "FROM core.review_task" in query:
            return [
                {"organization_id": item["details"]["rejected_organization_id"]}
                for item in self.review_tasks
                if item["entity_id"] == values[0]
                and item["task_type"] == "club_link"
                and item.get("status") == "dismissed"
                and item["details"].get("source") == values[1]
                and item["details"].get("external_key") == values[2]
            ]
        if "FROM core.review_task" in query:
            wanted = json.loads(values[2])
            return [{"exists": 1}] if any(item["entity_id"] == values[0] and item["task_type"] == values[1] and item.get("status") == "open" and item["details"] == wanted for item in self.review_tasks) else []
        if "INSERT INTO core.review_task" in query:
            self.review_tasks.append({"entity_type": values[0], "entity_id": values[1], "task_type": values[2], "status": "open", "details": json.loads(values[3])})
            return []
        if "UPDATE ops.ingest_run" in query:
            self.final_stats = json.loads(values[2])
            return []
        raise AssertionError(query)


def _club(*, source: str = "time_team", name: str = "Vesper Boat Club", key: str = "club-1", regattas: int = 4) -> dict[str, Any]:
    return {"id": "00000000-0000-0000-0000-000000000001", "source": source, "external_key": key, "display_name": name, "regatta_count": regattas}


def _org(name: str = "Vesper Boat Club", ident: str = "00000000-0000-0000-0000-000000000099", **extra: Any) -> dict[str, Any]:
    return {"id": ident, "slug": name.lower().replace(" ", "-"), "display_name": name, "legal_name": extra.get("legal_name"), "aliases": extra.get("aliases", [])}


def test_tier_zero_skips_a_verified_time_team_identifier() -> None:
    db = ResolveClubsDb(clubs=[_club()], organizations=[_org()], exact={("time_team", "club-1")})

    resolve_clubs(db)

    assert db.review_tasks == []
    assert db.audit_events == []
    assert db.final_stats["clubs_linked_exact"] == 1


def test_high_confidence_candidate_audits_and_deduplicates_task() -> None:
    db = ResolveClubsDb(clubs=[_club()], organizations=[_org()])

    resolve_clubs(db)
    resolve_clubs(db)

    assert len(db.review_tasks) == len(db.audit_events) == 1
    assert db.review_tasks[0]["details"]["auto"] is True
    assert db.audit_events[0]["after"]["organization_slug"] == "vesper-boat-club"


def test_mid_confidence_match_opens_non_auto_review() -> None:
    db = ResolveClubsDb(clubs=[_club(name="Vesper Boat Company")], organizations=[_org()])

    resolve_clubs(db)

    assert db.review_tasks[0]["details"]["auto"] is False
    assert db.review_tasks[0]["details"]["candidates"][0]["score"] == 0.7429


def test_any_two_high_confidence_organizations_are_never_auto() -> None:
    db = ResolveClubsDb(clubs=[], organizations=[])
    outcome = _open_link_candidate(
        db,
        _club(),
        [
            {"organization_id": "org-one", "organization_slug": "first", "score": 0.92},
            {"organization_id": "org-two", "organization_slug": "second", "score": 0.88},
        ],
        auto_allowed=True,
    )

    assert outcome.auto_candidate is False
    assert db.review_tasks[0]["details"]["auto"] is False
    assert len(db.review_tasks[0]["details"]["candidates"]) == 2
    assert db.audit_events == []


def test_time_team_legal_and_crew_suffixes_are_stripped_before_matching() -> None:
    db = ResolveClubsDb(clubs=[_club(name="Saugatuck Rowing Club, LLC A")], organizations=[_org("Saugatuck Rowing Club")])

    resolve_clubs(db)

    assert db.review_tasks[0]["details"]["auto"] is True
    assert db.review_tasks[0]["details"]["score"] == 1.0


def test_name_only_frequency_gate_skips_one_offs() -> None:
    db = ResolveClubsDb(clubs=[_club(source="herenow", regattas=2)], organizations=[_org()])

    resolve_clubs(db)

    assert db.review_tasks == []
    assert db.final_stats["clubs_frequency_gated"] == 1


def test_frequency_gate_counts_natural_regattas_not_superseded_revisions() -> None:
    club = _club(source="herenow", regattas=99)
    db = ResolveClubsDb(
        clubs=[club],
        organizations=[_org()],
        regatta_refs=[
            {"club_id": club["id"], "source": "herenow", "external_key": "race-a"},
            {"club_id": club["id"], "source": "herenow", "external_key": "race-a"},
            {"club_id": club["id"], "source": "herenow", "external_key": "race-b"},
        ],
    )

    resolve_clubs(db)

    assert db.review_tasks == []
    assert db.final_stats["clubs_frequency_gated"] == 1
    provider_query = next(query for query, _values in db.calls if "FROM core.provider_club AS club" in query)
    assert "count(DISTINCT (regatta.source, regatta.external_key))" in provider_query


def test_ein_boost_opens_inclusion_task_for_unlinked_bmf_legal_name() -> None:
    db = ResolveClubsDb(
        clubs=[_club(name="Vesper Boat Club")],
        organizations=[],
        bmf=[{"ein": "237397498", "legal_name": "Vesper Boat Club, Inc."}],
    )

    resolve_clubs(db)

    assert db.review_tasks == [
        {
            "entity_type": "provider_club",
            "entity_id": "00000000-0000-0000-0000-000000000001",
            "task_type": "inclusion",
            "status": "open",
            "details": {"candidate_eins": ["237397498"], "display_name": "Vesper Boat Club", "source": "time_team"},
        }
    ]


def test_ein_boost_caps_candidates_at_five() -> None:
    db = ResolveClubsDb(
        clubs=[_club(name="Vesper Boat Club")],
        organizations=[],
        bmf=[{"ein": f"10000000{number}", "legal_name": "Vesper Boat Club"} for number in range(6)],
    )

    resolve_clubs(db)

    inclusion = next(task for task in db.review_tasks if task["task_type"] == "inclusion")
    assert inclusion["details"]["candidate_eins"] == ["100000000", "100000001", "100000002", "100000003", "100000004"]


def test_curated_rejection_is_not_reopened_by_a_later_resolve(tmp_path: Path) -> None:
    db = ResolveClubsDb(clubs=[_club()], organizations=[_org()])

    resolve_clubs(db)
    curator = CuratorDb()
    curator.clubs = {
        ("time_team", "club-1"): {
            "id": db.clubs[0]["id"],
            "source": "time_team",
            "external_key": "club-1",
            "display_name": "Vesper Boat Club",
        }
    }
    curator.organizations = {"vesper-boat-club": {"id": db.organizations[0]["id"], "slug": "vesper-boat-club"}}
    curator.tasks = db.review_tasks
    csv_path = tmp_path / "club-links.csv"
    csv_path.write_text(
        "source,external_key,org_slug,decision,note\n"
        "time_team,club-1,vesper-boat-club,reject,not this organization\n",
        encoding="utf-8",
    )

    club_curation(curator, csv_path=csv_path)
    resolve_clubs(db)

    assert len(db.review_tasks) == 1
    assert db.review_tasks[0]["status"] == "dismissed"
    assert db.final_stats["clubs_rejected_skipped"] == 1


class CuratorDb:
    def __init__(self) -> None:
        self.clubs = {
            ("time_team", "tt-1"): {"id": "club-tt", "source": "time_team", "external_key": "tt-1", "display_name": "Vesper Boat Club"},
            ("herenow", "hn-1"): {"id": "club-hn", "source": "herenow", "external_key": "hn-1", "display_name": "Vesper RC"},
        }
        self.organizations = {"vesper": {"id": "org-1", "slug": "vesper"}}
        self.identifiers: list[dict[str, Any]] = []
        self.aliases: list[dict[str, Any]] = []
        self.tasks = [
            {"id": "task-1", "entity_id": "club-tt", "source": "time_team", "external_key": "tt-1", "task_type": "club_link", "details": {}, "status": "open"},
            {"id": "task-2", "entity_id": "club-hn", "source": "herenow", "external_key": "hn-1", "task_type": "club_link", "details": {}, "status": "open"},
        ]
        self.audit_events: list[dict[str, Any]] = []

    def execute(self, query: str, params: object = None) -> list[dict[str, Any]]:
        values = tuple(params or ())
        if "FROM core.provider_club WHERE" in query:
            item = self.clubs.get((values[0], values[1]))
            return [item.copy()] if item else []
        if "FROM core.organization WHERE slug" in query:
            item = self.organizations.get(values[0])
            return [item.copy()] if item else []
        if "FROM core.external_identifier" in query:
            return [item.copy() for item in self.identifiers if item["value"] == values[0]]
        if "INSERT INTO core.external_identifier" in query:
            self.identifiers.append({"organization_id": values[0], "namespace": "time_team_club", "value": values[1], "verification_state": "verified"})
            return []
        if "FROM core.organization_alias" in query:
            return [item.copy() for item in self.aliases if item["organization_id"] == values[0] and item["alias"] == values[1]]
        if "INSERT INTO core.organization_alias" in query:
            self.aliases.append({"organization_id": values[0], "alias": values[1]})
            return []
        if "UPDATE core.review_task" in query:
            changed = []
            for task in self.tasks:
                task_source = task.get("source", task["details"].get("source"))
                task_external_key = task.get("external_key", task["details"].get("external_key"))
                if task["entity_id"] == values[3] and task_source == values[4] and task_external_key == values[5] and task["status"] == "open":
                    task["status"] = values[0]
                    if values[1] is not None and task["task_type"] == "club_link":
                        task["details"]["rejected_organization_id"] = values[1]
                    changed.append({"id": task.get("id", f"task-{len(changed) + 1}")})
            return changed
        if "INSERT INTO core.audit_event" in query:
            self.audit_events.append({"actor": values[0], "action": values[1], "entity_id": values[2], "after": json.loads(values[3])})
            return []
        raise AssertionError(query)


def test_club_curation_promotes_identifiers_and_aliases_and_closes_tasks(tmp_path: Path) -> None:
    csv_path = tmp_path / "club-links.csv"
    csv_path.write_text(
        "source,external_key,org_slug,decision,note\n"
        "# commented rows remain examples, not curation data\n"
        "time_team,tt-1,vesper,link,confirmed\n"
        "herenow,hn-1,vesper,link,confirmed alias\n",
        encoding="utf-8",
    )
    db = CuratorDb()

    assert "promoted=2" in club_curation(db, csv_path=csv_path)
    assert db.identifiers[0]["value"] == "tt-1"
    assert db.aliases == [{"organization_id": "org-1", "alias": "Vesper RC"}]
    assert [task["status"] for task in db.tasks] == ["resolved", "resolved"]
    assert [event["action"] for event in db.audit_events] == ["club_link_promoted", "club_link_promoted"]
    assert "unchanged=2" in club_curation(db, csv_path=csv_path)
    assert len(db.audit_events) == 2


def test_club_curation_reject_dismisses_and_persists_the_rejected_organization(tmp_path: Path) -> None:
    csv_path = tmp_path / "club-links.csv"
    csv_path.write_text(
        "source,external_key,org_slug,decision,note\n"
        "time_team,tt-1,vesper,reject,wrong club\n",
        encoding="utf-8",
    )
    db = CuratorDb()

    assert "rejected=1" in club_curation(db, csv_path=csv_path)
    assert db.tasks[0]["status"] == "dismissed"
    assert db.tasks[0]["details"]["rejected_organization_id"] == "org-1"
    assert db.audit_events[0]["action"] == "club_link_rejected"
    assert "unchanged=1" in club_curation(db, csv_path=csv_path)
    assert len(db.audit_events) == 1
