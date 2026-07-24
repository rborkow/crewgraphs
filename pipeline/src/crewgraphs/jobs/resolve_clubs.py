"""Resolve provider-side clubs into curator-reviewed organization links.

The pipeline role deliberately never mutates the identity graph.  It can only
record evidence (``audit_event``) and work for a curator (``review_task``).
``club_curation`` is the separate, curator-role promotion path.
"""

from __future__ import annotations

import csv
import json
import os
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import typer

from ..config import Settings
from ..db import DatabaseGateway, PostgresGateway
from ..runlog import IngestRun
from ..summary import emit_summary, render_summary
from .resolve import name_similarity


TIME_TEAM = "time_team"
NAME_ONLY_SOURCES = frozenset({"herenow", "regattatiming", "row2k"})
AUTO_THRESHOLD = 0.85
REVIEW_THRESHOLD = 0.60
FREQUENCY_THRESHOLD = 3


def resolve_clubs(db: DatabaseGateway) -> str:
    """Create club-link and inclusion candidates without writing identities."""
    with IngestRun(db, job_name="resolve_clubs", source="results") as run:
        for key in (
            "clubs_total",
            "clubs_linked_exact",
            "clubs_auto_candidates",
            "clubs_review_opened",
            "clubs_inclusion_opened",
            "clubs_frequency_gated",
            "clubs_below_threshold",
            "clubs_rejected_skipped",
        ):
            run.add_stat(key, 0)

        clubs = _provider_clubs(db)
        organizations = _organizations(db)
        bmf_candidates = _unlinked_bmf_names(db)
        source_totals: dict[str, int] = defaultdict(int)
        source_matched: dict[str, int] = defaultdict(int)
        source_auto: dict[str, int] = defaultdict(int)
        source_review: dict[str, int] = defaultdict(int)

        for club in clubs:
            source = str(club["source"])
            source_totals[source] += 1
            run.add_stat("clubs_total")
            if _is_exactly_linked(db, club):
                run.add_stat("clubs_linked_exact")
                source_matched[source] += 1
                continue

            if source == TIME_TEAM:
                outcome = _resolve_time_team_club(db, club, organizations, bmf_candidates)
                if outcome.auto_candidate:
                    run.add_stat("clubs_auto_candidates")
                    source_auto[source] += 1
                if outcome.candidate:
                    source_matched[source] += 1
                    if not outcome.auto_candidate:
                        source_review[source] += 1
                if outcome.review_opened:
                    run.add_stat("clubs_review_opened")
                if outcome.inclusion_opened:
                    run.add_stat("clubs_inclusion_opened")
                if outcome.below_threshold:
                    run.add_stat("clubs_below_threshold")
                if outcome.rejected_skipped:
                    run.add_stat("clubs_rejected_skipped")
            elif source in NAME_ONLY_SOURCES:
                if int(club["regatta_count"]) < FREQUENCY_THRESHOLD:
                    run.add_stat("clubs_frequency_gated")
                    continue
                outcome = _resolve_name_only_club(db, club, organizations)
                if outcome.review_opened:
                    run.add_stat("clubs_review_opened")
                if outcome.candidate:
                    source_matched[source] += 1
                    source_review[source] += 1
                if outcome.below_threshold:
                    run.add_stat("clubs_below_threshold")
                if outcome.rejected_skipped:
                    run.add_stat("clubs_rejected_skipped")

        # Store the source denominators and numerator consistently so the
        # summary has an explicit, machine-readable match-rate surface.
        for source, total in sorted(source_totals.items()):
            prefix = f"source_{source}_"
            run.add_stat(prefix + "clubs_total", total)
            run.add_stat(prefix + "clubs_matched", source_matched[source])
            run.add_stat(prefix + "clubs_auto_candidates", source_auto[source])
            run.add_stat(prefix + "clubs_review_candidates", source_review[source])
            run.add_stat(prefix + "match_rate", source_matched[source] / total if total else 0)

    summary = render_summary(job_name="resolve_clubs", run_id=run.id or "", status="succeeded", counts=run.stats)
    emit_summary(summary)
    return summary


class _Outcome:
    def __init__(self, *, candidate: bool = False, auto_candidate: bool = False, review_opened: bool = False, inclusion_opened: bool = False, below_threshold: bool = False, rejected_skipped: bool = False) -> None:
        self.candidate = candidate
        self.auto_candidate = auto_candidate
        self.review_opened = review_opened
        self.inclusion_opened = inclusion_opened
        self.below_threshold = below_threshold
        self.rejected_skipped = rejected_skipped


def _provider_clubs(db: DatabaseGateway) -> list[dict[str, Any]]:
    return db.execute(
        """
        SELECT club.id, club.source::text AS source, club.external_key, club.display_name,
               count(DISTINCT (regatta.source, regatta.external_key))
                   FILTER (WHERE regatta.id IS NOT NULL)::integer AS regatta_count
        FROM core.provider_club AS club
        LEFT JOIN core.regatta_entry AS entry ON entry.provider_club_id = club.id
        LEFT JOIN core.regatta_event AS event ON event.id = entry.event_id
        LEFT JOIN core.regatta AS regatta ON regatta.id = event.regatta_id
        GROUP BY club.id, club.source, club.external_key, club.display_name
        ORDER BY club.source, club.display_name, club.id
        """
    )


def _organizations(db: DatabaseGateway) -> list[dict[str, Any]]:
    """Build one candidate record per organization, including aliases."""
    rows = db.execute(
        """
        SELECT organization.id, organization.slug, organization.display_name,
               organization.legal_name, organization_alias.alias
        FROM core.organization AS organization
        LEFT JOIN core.organization_alias ON organization_alias.organization_id = organization.id
        WHERE organization.status <> 'merged'
        ORDER BY organization.id, organization_alias.alias
        """
    )
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row["id"])
        org = indexed.setdefault(
            key,
            {
                "id": row["id"],
                "slug": row["slug"],
                "display_name": row.get("display_name"),
                "legal_name": row.get("legal_name"),
                "aliases": [],
            },
        )
        if row.get("alias"):
            org["aliases"].append(str(row["alias"]))
    return list(indexed.values())


def _unlinked_bmf_names(db: DatabaseGateway) -> list[dict[str, Any]]:
    """Read BMF's uppercase ``NAME`` field for EINs outside the identity graph."""
    return db.execute(
        """
        SELECT DISTINCT ON (bmf.ein)
               bmf.ein, COALESCE(bmf.raw_row->>'NAME', bmf.raw_row->>'NAME_EIN', bmf.raw_row->>'name') AS legal_name
        FROM staging.bmf_row AS bmf
        WHERE COALESCE(bmf.raw_row->>'NAME', bmf.raw_row->>'NAME_EIN', bmf.raw_row->>'name') IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM core.external_identifier AS identifier
              WHERE identifier.namespace = 'irs_ein' AND identifier.value = bmf.ein
          )
        ORDER BY bmf.ein, bmf.bmf_release_date DESC, bmf.id DESC
        """
    )


def _is_exactly_linked(db: DatabaseGateway, club: Mapping[str, Any]) -> bool:
    if club["source"] == TIME_TEAM:
        rows = db.execute(
            """
            SELECT 1 FROM core.external_identifier
            WHERE namespace = 'time_team_club' AND value = %s
              AND verification_state = 'verified' AND valid_to IS NULL
            LIMIT 1
            """,
            (club["external_key"],),
        )
    else:
        rows = db.execute(
            """
            SELECT 1 FROM core.organization_alias
            WHERE alias_normalized = lower(regexp_replace(%s, '[[:punct:]]', '', 'g'))
            LIMIT 1
            """,
            (club["display_name"],),
        )
    return bool(rows)


def _resolve_time_team_club(
    db: DatabaseGateway,
    club: Mapping[str, Any],
    organizations: Iterable[Mapping[str, Any]],
    bmf_candidates: Iterable[Mapping[str, Any]],
) -> _Outcome:
    candidates = _scored_organizations(club["display_name"], organizations, include_legal=True)
    outcome = _open_link_candidate(db, club, candidates, auto_allowed=True)
    eins = _candidate_eins(club["display_name"], bmf_candidates)
    if eins:
        details = {"candidate_eins": eins, "display_name": club["display_name"], "source": club["source"]}
        if not _open_task(db, str(club["id"]), "inclusion", details):
            _review_task(db, "provider_club", str(club["id"]), "inclusion", details)
            outcome.inclusion_opened = True
    return outcome


def _resolve_name_only_club(db: DatabaseGateway, club: Mapping[str, Any], organizations: Iterable[Mapping[str, Any]]) -> _Outcome:
    candidates = _scored_organizations(club["display_name"], organizations, include_legal=False)
    return _open_link_candidate(db, club, candidates, auto_allowed=False)


def _scored_organizations(display_name: object, organizations: Iterable[Mapping[str, Any]], *, include_legal: bool) -> list[dict[str, Any]]:
    provider_name = _match_name(display_name)
    scored: list[dict[str, Any]] = []
    for org in organizations:
        names = [org.get("display_name"), *org.get("aliases", [])]
        if include_legal:
            names.append(org.get("legal_name"))
        score = name_similarity(provider_name, (_match_name(name) for name in names if name))
        scored.append({"organization_id": str(org["id"]), "organization_slug": str(org["slug"]), "score": round(score, 4)})
    return sorted(scored, key=lambda item: (-float(item["score"]), item["organization_slug"], item["organization_id"]))


def _open_link_candidate(db: DatabaseGateway, club: Mapping[str, Any], candidates: list[dict[str, Any]], *, auto_allowed: bool) -> _Outcome:
    dismissed_organization_ids = _dismissed_club_link_organizations(db, club)
    active_candidates = [
        candidate
        for candidate in candidates
        if candidate["organization_id"] not in dismissed_organization_ids
    ]
    if candidates and not active_candidates:
        return _Outcome(rejected_skipped=True)
    candidates = active_candidates
    best = candidates[0] if candidates else None
    top_score = float(best["score"]) if best else 0.0
    # Separate high-confidence organizations always require curator judgment.
    ambiguous = sum(float(candidate["score"]) >= AUTO_THRESHOLD for candidate in candidates) >= 2
    if best and top_score >= AUTO_THRESHOLD and not ambiguous and auto_allowed:
        details = {
            "source": club["source"],
            "external_key": club["external_key"],
            "display_name": club["display_name"],
            "organization_id": best["organization_id"],
            "organization_slug": best["organization_slug"],
            "score": top_score,
            "auto": True,
        }
        opened = False
        if not _open_task(db, str(club["id"]), "club_link", details):
            _review_task(db, "provider_club", str(club["id"]), "club_link", details)
            opened = True
        if not _prior_candidate(db, best["organization_id"], details):
            _audit_candidate(db, best["organization_id"], details)
        return _Outcome(candidate=True, auto_candidate=True, review_opened=opened)

    if best and top_score >= REVIEW_THRESHOLD:
        details = {
            "source": club["source"],
            "external_key": club["external_key"],
            "display_name": club["display_name"],
            "auto": False,
            "candidates": [item for item in candidates if float(item["score"]) >= REVIEW_THRESHOLD],
        }
        if not _open_task(db, str(club["id"]), "club_link", details):
            _review_task(db, "provider_club", str(club["id"]), "club_link", details)
            return _Outcome(candidate=True, review_opened=True)
        return _Outcome(candidate=True)
    return _Outcome(below_threshold=True)


def _candidate_eins(display_name: object, bmf_candidates: Iterable[Mapping[str, Any]]) -> list[str]:
    scored = [
        (name_similarity(_match_name(display_name), [_match_name(item["legal_name"])]), str(item["ein"]))
        for item in bmf_candidates
        if item.get("ein") and item.get("legal_name")
    ]
    # EIN growth fuel should still be a high-confidence legal-name candidate;
    # lower scores are already represented by ordinary club-link review work.
    return [ein for score, ein in sorted(scored, key=lambda item: (-item[0], item[1])) if score >= AUTO_THRESHOLD][:5]


def _match_name(value: object) -> str:
    """Drop provider legal/crew suffixes before resolve.py's token-set scorer."""
    name = str(value or "").strip()
    name = re.sub(r"\s+(?:[A-Za-z]|[0-9]+[A-Za-z]?)$", "", name)
    name = re.sub(r",?\s+(?:L\.?L\.?C\.?|LLC|INC\.?|INCORPORATED)$", "", name, flags=re.IGNORECASE)
    return name.strip()


def _prior_candidate(db: DatabaseGateway, organization_id: str, details: Mapping[str, Any]) -> bool:
    rows = db.execute(
        """
        SELECT 1 FROM core.audit_event
        WHERE action = 'club_link_candidate' AND entity_type = 'organization' AND entity_id = %s
          AND after = %s::jsonb
        LIMIT 1
        """,
        (organization_id, json.dumps(details)),
    )
    return bool(rows)


def _audit_candidate(db: DatabaseGateway, organization_id: str, details: Mapping[str, Any]) -> None:
    db.execute(
        """
        INSERT INTO core.audit_event (actor, action, entity_type, entity_id, before, after)
        VALUES ('pipeline_rw', 'club_link_candidate', 'organization', %s, NULL, %s::jsonb)
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


def _dismissed_club_link_organizations(db: DatabaseGateway, club: Mapping[str, Any]) -> set[str]:
    """Return club/org pairs a curator explicitly rejected in one lookup."""
    rows = db.execute(
        """
        SELECT details->>'rejected_organization_id' AS organization_id
        FROM core.review_task
        WHERE entity_type = 'provider_club' AND entity_id = %s
          AND task_type = 'club_link' AND status = 'dismissed'
          AND details->>'source' = %s AND details->>'external_key' = %s
          AND details ? 'rejected_organization_id'
        """,
        (club["id"], club["source"], club["external_key"]),
    )
    return {str(row["organization_id"]) for row in rows if row.get("organization_id")}


def _review_task(db: DatabaseGateway, entity_type: str, entity_id: str, task_type: str, details: Mapping[str, Any]) -> None:
    db.execute(
        """
        INSERT INTO core.review_task (entity_type, entity_id, task_type, details)
        VALUES (%s, %s, %s, %s::jsonb)
        """,
        (entity_type, entity_id, task_type, json.dumps(details)),
    )


def club_curation(curator_db: DatabaseGateway, *, csv_path: str | Path, actor: str = "owner") -> str:
    """Promote hand-reviewed CSV decisions through the curator connection."""
    promoted = rejected = unchanged = 0
    for row in _csv_rows(csv_path):
        source, external_key, decision = (row[key].strip() for key in ("source", "external_key", "decision"))
        if source not in {TIME_TEAM, *NAME_ONLY_SOURCES}:
            raise ValueError(f"unsupported club-link source: {source}")
        if decision not in {"link", "reject"}:
            raise ValueError(f"unsupported club-link decision: {decision}")
        club = _curator_club(curator_db, source, external_key)
        if club is None:
            raise ValueError(f"provider club not found: {source}/{external_key}")
        if decision == "reject":
            slug = row["org_slug"].strip()
            if not slug:
                raise ValueError("org_slug is required for a reject decision")
            organization = _curator_organization(curator_db, slug)
            if organization is None:
                raise ValueError(f"organization not found: {slug}")
            if _close_tasks(
                curator_db,
                club["id"],
                source,
                external_key,
                "dismissed",
                rejected_organization_id=str(organization["id"]),
            ):
                _curation_audit(curator_db, actor, "club_link_rejected", club, row, organization)
                rejected += 1
            else:
                unchanged += 1
            continue

        slug = row["org_slug"].strip()
        if not slug:
            raise ValueError("org_slug is required for a link decision")
        organization = _curator_organization(curator_db, slug)
        if organization is None:
            raise ValueError(f"organization not found: {slug}")
        if source == TIME_TEAM:
            wrote_identity = _ensure_time_team_identifier(curator_db, club, organization)
        else:
            wrote_identity = _ensure_alias(curator_db, club, organization)
        closed = _close_tasks(curator_db, club["id"], source, external_key, "resolved")
        if wrote_identity or closed:
            _curation_audit(curator_db, actor, "club_link_promoted", club, row, organization)
            promoted += 1
        else:
            unchanged += 1
    summary = f"club_curation: promoted={promoted} rejected={rejected} unchanged={unchanged}"
    print(summary)
    return summary


def _csv_rows(csv_path: str | Path) -> Iterable[dict[str, str]]:
    with Path(csv_path).open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(line for line in handle if not line.lstrip().startswith("#"))
        required = {"source", "external_key", "org_slug", "decision", "note"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError("club-links CSV requires source,external_key,org_slug,decision,note columns")
        for row in reader:
            if row and any((value or "").strip() for value in row.values()):
                yield {key: value or "" for key, value in row.items()}


def _curator_club(db: DatabaseGateway, source: str, external_key: str) -> dict[str, Any] | None:
    rows = db.execute(
        "SELECT id, source::text AS source, external_key, display_name FROM core.provider_club WHERE source = %s AND external_key = %s",
        (source, external_key),
    )
    return rows[0] if len(rows) == 1 else None


def _curator_organization(db: DatabaseGateway, slug: str) -> dict[str, Any] | None:
    rows = db.execute("SELECT id, slug FROM core.organization WHERE slug = %s", (slug,))
    return rows[0] if len(rows) == 1 else None


def _ensure_time_team_identifier(db: DatabaseGateway, club: Mapping[str, Any], organization: Mapping[str, Any]) -> bool:
    rows = db.execute(
        """
        SELECT id, organization_id FROM core.external_identifier
        WHERE namespace = 'time_team_club' AND value = %s
          AND verification_state = 'verified' AND valid_to IS NULL
        """,
        (club["external_key"],),
    )
    if rows:
        if str(rows[0]["organization_id"]) != str(organization["id"]):
            raise ValueError(f"time_team_club {club['external_key']} is already verified for another organization")
        return False
    db.execute(
        """
        INSERT INTO core.external_identifier (organization_id, namespace, value, verification_state)
        VALUES (%s, 'time_team_club', %s, 'verified')
        """,
        (organization["id"], club["external_key"]),
    )
    return True


def _ensure_alias(db: DatabaseGateway, club: Mapping[str, Any], organization: Mapping[str, Any]) -> bool:
    rows = db.execute(
        "SELECT id FROM core.organization_alias WHERE organization_id = %s AND alias = %s",
        (organization["id"], club["display_name"]),
    )
    if rows:
        return False
    db.execute(
        "INSERT INTO core.organization_alias (organization_id, alias) VALUES (%s, %s)",
        (organization["id"], club["display_name"]),
    )
    return True


def _close_tasks(
    db: DatabaseGateway,
    club_id: object,
    source: str,
    external_key: str,
    status: str,
    *,
    rejected_organization_id: str | None = None,
) -> bool:
    rows = db.execute(
        """
        UPDATE core.review_task
        SET status = %s,
            details = CASE WHEN task_type = 'club_link' AND %s::text IS NOT NULL
                THEN details || jsonb_build_object('rejected_organization_id', %s::text)
                ELSE details END
        WHERE entity_type = 'provider_club' AND entity_id = %s
          AND task_type IN ('club_link', 'inclusion') AND status = 'open'
          AND details->>'source' = %s
          AND (
              (task_type = 'club_link' AND details->>'external_key' = %s)
              OR task_type = 'inclusion'
          )
        RETURNING id
        """,
        (status, rejected_organization_id, rejected_organization_id, club_id, source, external_key),
    )
    return bool(rows)


def _curation_audit(
    db: DatabaseGateway,
    actor: str,
    action: str,
    club: Mapping[str, Any],
    row: Mapping[str, str],
    organization: Mapping[str, Any] | None = None,
) -> None:
    after: dict[str, Any] = {
        "source": club["source"],
        "external_key": club["external_key"],
        "display_name": club["display_name"],
        "decision": row["decision"],
        "note": row.get("note", ""),
    }
    if organization is not None:
        after.update({"organization_id": str(organization["id"]), "organization_slug": organization["slug"]})
    db.execute(
        """
        INSERT INTO core.audit_event (actor, action, entity_type, entity_id, before, after)
        VALUES (%s, %s, 'provider_club', %s, NULL, %s::jsonb)
        """,
        (actor, action, club["id"], json.dumps(after)),
    )


def register(app: typer.Typer) -> None:
    """Attach identity-safe results resolver and curator promotion commands."""

    @app.command(name="resolve-clubs")
    def resolve_clubs_cmd() -> None:
        settings = Settings.from_env()
        gateway = PostgresGateway(settings.database_url)
        try:
            typer.echo(resolve_clubs(gateway))
        finally:
            gateway.close()

    @app.command(name="club-curation")
    def club_curation_cmd(
        csv_path: str = typer.Option("seed/club_links.csv", "--csv", help="Reviewed club-link decisions CSV"),
        actor: str = typer.Option("owner", help="Audit-event actor"),
    ) -> None:
        curator_url = os.environ.get("CURATOR_DATABASE_URL")
        if not curator_url:
            typer.echo("CURATOR_DATABASE_URL is required (identity writes are curator-only)")
            raise typer.Exit(code=1)
        gateway = PostgresGateway(curator_url)
        try:
            typer.echo(club_curation(gateway, csv_path=csv_path, actor=actor))
        finally:
            gateway.close()


__all__ = ["club_curation", "register", "resolve_clubs"]
