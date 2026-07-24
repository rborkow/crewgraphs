"""Build and atomically activate the public CrewGraphs read model."""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from urllib.parse import urlparse

from ..concept_map import load_concept_map
from ..db import DatabaseGateway
from ..runlog import IngestRun
from .efile_fetch import GT_LAKE_XML_URL


PROFILE_SCHEMA_VERSION = 1
RESULTS_SCHEMA_VERSION = 1
SNAPSHOT_FACTS = {
    "total_revenue": ("total_revenue", "Total revenue"),
    "total_expenses": ("total_expenses", "Total expenses"),
    "net_assets_eoy": ("net_assets", "Net assets"),
    "contributions_grants": ("grant_revenue", "Grant revenue"),
}
SOURCE_REGISTRY = {
    "irs_990_xml": {
        "description": "Authoritative IRS Form 990 and 990-EZ electronic filing facts.",
        "attribution": "IRS e-file data; concept mapping acknowledges the Nonprofit Open Data Collective (NODC) concordance as reference material.",
    },
    "irs_bmf": {
        "description": "IRS Exempt Organizations Business Master File identity observations.",
        "attribution": "Source: Internal Revenue Service Exempt Organizations Business Master File.",
    },
    "irs_990n": {
        "description": "IRS Form 990-N e-Postcard filing-presence observations.",
        "attribution": "Source: Internal Revenue Service Tax Exempt Organization Search bulk data.",
    },
    "propublica": {
        "description": "ProPublica Nonprofit Explorer identity and filing cross-checks.",
        "attribution": "Data cross-checked with ProPublica Nonprofit Explorer; ProPublica values are not canonical CrewGraphs facts.",
    },
    "givingtuesday": {
        "description": "GivingTuesday 990 Data Lake per-filing IRS XML mirror.",
        "attribution": "GivingTuesday 990 Data Lake data is used under the Open Database License (ODbL); derivative databases remain subject to share-alike.",
    },
    "herenow": {
        "description": "HereNow Sports regatta timing results ingested from the public Breeze API.",
        "attribution": "Results are linked back to legacy.herenow.com.",
    },
    "time_team": {
        "description": "TIME TEAM Regatta Systems / USRowing white-label public JSON API results.",
        "attribution": "Results are linked back to usrowing.regatta.time-team.com.",
    },
    "regattatiming": {
        "description": "Regatta Timing LLC public results pages.",
        "attribution": "Results are linked back to results.regattatiming.com.",
    },
    "row2k": {
        "description": "row2k results directory; discovery index only.",
        "attribution": "Results are linked, never copied, per row2k policy; credit row2k.",
    },
}


class PublishInvariantError(RuntimeError):
    """Raised after all pre-publish gates have been evaluated."""


def publish(db: DatabaseGateway, *, generated_at: str) -> str:
    """Build a validated snapshot, atomically activate it, retain the newest three."""
    with IngestRun(
        db,
        job_name="publish",
        source="ops",
        params={"generated_at": generated_at},
    ) as run:
        generated = _iso_datetime(generated_at)
        concept_map = load_concept_map()
        for stat in (
            "orgs_published",
            "series_rows",
            "coverage_rows",
            "payloads_validated",
            "identity_downgrades",
            "regatta_orgs_published",
            "regatta_rows_published",
            "regatta_entries_suppressed_names",
            "regatta_entries_u13_redacted",
            "regatta_downgrades",
            "regatta_clubs_ambiguous",
            "gc_snapshots_deleted",
        ):
            run.add_stat(stat, 0)

        source = _load_source_rows(db)
        failures, identity_findings = _invariant_failures(
            source["organizations"], source["facts"], source["slug_history"]
        )
        if failures:
            raise PublishInvariantError(
                "publish invariant gates failed:\n- " + "\n- ".join(failures)
            )
        # A filer's own arithmetic error is that filing's quality problem, not a
        # site outage: its facts publish as under_review (suppressed in compare,
        # state shown on profiles) and a curator review task records the finding.
        for filing_id, message in sorted(identity_findings.items()):
            db.execute(
                """
                INSERT INTO core.review_task (entity_type, entity_id, task_type, details)
                VALUES ('filing', %s, 'identity_check', %s::jsonb)
                ON CONFLICT DO NOTHING
                """,
                (filing_id, json.dumps({"message": message})),
            )
        run.add_stat("identity_downgrades", len(identity_findings))

        build = _assemble(
            source,
            generated=generated,
            parser_version=concept_map.version,
            under_review_filing_ids=frozenset(identity_findings),
        )
        validation_failures, _ = _invariant_failures(
            source["organizations"],
            source["facts"],
            source["slug_history"],
            build=build,
            suppressions=source["person_suppressions"],
            result_people=source["result_people"],
        )
        if validation_failures:
            raise PublishInvariantError(
                "publish invariant gates failed:\n- " + "\n- ".join(validation_failures)
            )
        for ambiguity in source["ambiguous_regatta_clubs"]:
            details = {
                "reason": "provider club matches multiple organizations",
                "source": str(ambiguity["source"]),
                "candidate_organization_count": int(
                    ambiguity["candidate_organization_count"]
                ),
            }
            db.execute(
                """
                INSERT INTO core.review_task
                    (entity_type, entity_id, task_type, details)
                SELECT 'provider_club', %s, 'club_link', %s::jsonb
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM core.review_task
                    WHERE entity_type = 'provider_club'
                      AND entity_id = %s
                      AND task_type = 'club_link'
                      AND status IN ('open', 'in_progress')
                )
                """,
                (
                    ambiguity["provider_club_id"],
                    json.dumps(details),
                    ambiguity["provider_club_id"],
                ),
            )
        run.add_stat(
            "regatta_clubs_ambiguous",
            len(source["ambiguous_regatta_clubs"]),
        )
        for finding in build["regatta_review_findings"]:
            db.execute(
                """
                INSERT INTO core.review_task
                    (entity_type, entity_id, task_type, details)
                SELECT 'regatta_entry', %s, 'result_sanity', %s::jsonb
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM core.review_task
                    WHERE entity_type = 'regatta_entry'
                      AND entity_id = %s
                      AND task_type = 'result_sanity'
                      AND status IN ('open', 'in_progress')
                )
                """,
                (
                    finding["entry_id"],
                    json.dumps(finding["details"]),
                    finding["entry_id"],
                ),
            )
        run.add_stat("regatta_downgrades", len(build["regatta_review_findings"]))

        snapshot_rows = db.execute(
            """
            INSERT INTO ops.publish_snapshot
                (ingest_run_id, status, manifest, created_at)
            VALUES (%s, 'building', %s::jsonb, %s::timestamptz)
            RETURNING id
            """,
            (
                run.id,
                json.dumps(
                    {
                        "generated_at": generated,
                        "orgs_published": len(build["directories"]),
                        "series_rows": len(build["series"]),
                        "coverage_rows": len(build["coverage"]),
                        "payloads_validated": len(build["profiles"]),
                        "regatta_orgs_published": len(build["regatta_payloads"]),
                        "regatta_rows_published": len(build["regatta_rows"]),
                        "regatta_clubs_ambiguous": len(
                            source["ambiguous_regatta_clubs"]
                        ),
                    }
                ),
                generated,
            ),
        )
        if not snapshot_rows:
            raise RuntimeError("ops.publish_snapshot insert did not return an id")
        snapshot_id = str(snapshot_rows[0]["id"])

        _insert_build(db, snapshot_id=snapshot_id, generated=generated, build=build)
        run.add_stat("orgs_published", len(build["directories"]))
        run.add_stat("series_rows", len(build["series"]))
        run.add_stat("coverage_rows", len(build["coverage"]))
        run.add_stat("payloads_validated", len(build["profiles"]))
        run.add_stat("regatta_orgs_published", len(build["regatta_payloads"]))
        run.add_stat("regatta_rows_published", len(build["regatta_rows"]))
        run.add_stat(
            "regatta_entries_suppressed_names",
            len(build["regatta_suppressed_entries"]),
        )
        run.add_stat(
            "regatta_entries_u13_redacted",
            len(build["regatta_u13_entries"]),
        )

        flipped = db.execute(
            """
            WITH target AS MATERIALIZED (
                SELECT id
                FROM ops.publish_snapshot
                WHERE id = %s AND status = 'building'
            ), superseded AS (
                UPDATE ops.publish_snapshot
                SET status = 'superseded'
                WHERE status = 'active'
                  AND EXISTS (SELECT 1 FROM target)
                RETURNING id
            ), pointer AS (
                INSERT INTO read.published_snapshot
                    (singleton, snapshot_id, created_at, updated_at)
                SELECT true, target.id, %s::timestamptz, %s::timestamptz
                FROM target
                ON CONFLICT (singleton) DO UPDATE
                SET snapshot_id = EXCLUDED.snapshot_id,
                    updated_at = EXCLUDED.updated_at
                RETURNING snapshot_id
            )
            UPDATE ops.publish_snapshot AS snapshot
            SET status = 'active', activated_at = %s::timestamptz
            FROM target
            WHERE snapshot.id = target.id
              AND EXISTS (SELECT 1 FROM pointer)
            RETURNING snapshot.id
            """,
            (snapshot_id, generated, generated, generated),
        )
        if not flipped:
            raise RuntimeError("publish snapshot was not atomically activated")

        gc_rows = db.execute(_GC_SQL, (snapshot_id,))
        gc_count = int(gc_rows[0]["deleted_count"]) if gc_rows else 0
        run.add_stat("gc_snapshots_deleted", gc_count)
    return run.id or ""


def _load_source_rows(db: DatabaseGateway) -> dict[str, list[dict[str, Any]]]:
    organizations = db.execute(
        """
        SELECT o.id AS organization_id, o.slug, o.display_name, o.legal_name,
               o.org_type, o.city, o.state, o.website,
               array_agg(DISTINCT ei.value ORDER BY ei.value) AS eins
        FROM core.organization AS o
        JOIN core.external_identifier AS ei
          ON ei.organization_id = o.id
         AND ei.namespace = 'irs_ein'
         AND ei.verification_state = 'verified'
        WHERE o.status = 'included'
        GROUP BY o.id, o.slug, o.display_name, o.legal_name, o.org_type,
                 o.city, o.state, o.website
        ORDER BY o.id
        """
    )
    org_ids = [row["organization_id"] for row in organizations]
    eins = sorted(
        {str(ein) for row in organizations for ein in _sequence(row.get("eins"))}
    )
    regatta_results = db.execute(
        """
        WITH latest_regatta AS MATERIALIZED (
            SELECT DISTINCT ON (r.source, r.external_key)
                   r.id, r.source, r.external_key, r.name, r.start_date,
                   r.venue, r.source_record_id, r.parser_version, r.created_at
            FROM core.regatta AS r
            WHERE r.source IN ('herenow', 'time_team', 'regattatiming')
            ORDER BY r.source, r.external_key, r.revision DESC
        ), link_candidates AS MATERIALIZED (
            SELECT club.id AS provider_club_id, identifier.organization_id
            FROM core.provider_club AS club
            JOIN core.external_identifier AS identifier
              ON club.source = 'time_team'
             AND identifier.namespace = 'time_team_club'
             AND identifier.value = club.external_key
             AND identifier.verification_state = 'verified'
             AND identifier.valid_to IS NULL
            UNION
            SELECT club.id AS provider_club_id, alias.organization_id
            FROM core.provider_club AS club
            JOIN core.organization_alias AS alias
              ON club.source <> 'time_team'
             AND alias.alias_normalized =
                 lower(regexp_replace(club.display_name, '[[:punct:]]', '', 'g'))
        ), unambiguous_provider_clubs AS MATERIALIZED (
            SELECT candidate.provider_club_id
            FROM link_candidates AS candidate
            GROUP BY candidate.provider_club_id
            HAVING count(DISTINCT candidate.organization_id) = 1
        ), unambiguous_links AS MATERIALIZED (
            SELECT DISTINCT candidate.provider_club_id,
                            candidate.organization_id
            FROM link_candidates AS candidate
            JOIN unambiguous_provider_clubs AS unambiguous
              ON unambiguous.provider_club_id = candidate.provider_club_id
        ), linked_results AS (
            SELECT DISTINCT
                   linked.organization_id, o.slug,
                   r.id AS regatta_id, r.source, r.external_key AS regatta_external_key,
                   r.name AS regatta_name, r.start_date, r.venue,
                   r.parser_version,
                   COALESCE(sr.created_at, r.created_at) AS retrieved_at,
                   event.id AS event_id, event.external_key AS event_external_key,
                   event.name AS event_name, event.boat_class_raw,
                   event.age_class_raw, event.round,
                   entry.id AS entry_id, entry.external_key AS entry_external_key,
                   entry.club_source_name, entry.provider_club_id, entry.crew_label,
                   result.status, result.position, result.adjusted_position,
                   result.time_ms, result.adjusted_time_ms,
                   result.handicap_ms, result.delta_ms
            FROM latest_regatta AS r
            JOIN core.regatta_event AS event ON event.regatta_id = r.id
            JOIN core.regatta_entry AS entry ON entry.event_id = event.id
            JOIN core.regatta_result AS result ON result.entry_id = entry.id
            JOIN core.provider_club AS club ON club.id = entry.provider_club_id
            JOIN unambiguous_links AS linked
              ON linked.provider_club_id = club.id
            JOIN core.organization AS o
              ON o.id = linked.organization_id
             AND o.id = ANY(%s)
            LEFT JOIN core.source_record AS sr ON sr.id = r.source_record_id
            WHERE result.time_ms IS NOT NULL
               OR result.adjusted_time_ms IS NOT NULL
               OR result.handicap_ms IS NOT NULL
               OR result.position IS NOT NULL
               OR result.adjusted_position IS NOT NULL
               OR result.delta_ms IS NOT NULL
        )
        SELECT *
        FROM linked_results
        ORDER BY organization_id, source, regatta_external_key,
                 event_external_key, entry_external_key
        """,
        (org_ids,),
    )
    ambiguous_regatta_clubs = db.execute(
        """
        WITH latest_regatta AS MATERIALIZED (
            SELECT DISTINCT ON (r.source, r.external_key) r.id
            FROM core.regatta AS r
            WHERE r.source IN ('herenow', 'time_team', 'regattatiming')
            ORDER BY r.source, r.external_key, r.revision DESC
        ), active_provider_clubs AS MATERIALIZED (
            SELECT DISTINCT club.id, club.source, club.external_key,
                            club.display_name
            FROM latest_regatta AS r
            JOIN core.regatta_event AS event ON event.regatta_id = r.id
            JOIN core.regatta_entry AS entry ON entry.event_id = event.id
            JOIN core.regatta_result AS result ON result.entry_id = entry.id
            JOIN core.provider_club AS club ON club.id = entry.provider_club_id
            WHERE result.time_ms IS NOT NULL
               OR result.adjusted_time_ms IS NOT NULL
               OR result.handicap_ms IS NOT NULL
               OR result.position IS NOT NULL
               OR result.adjusted_position IS NOT NULL
               OR result.delta_ms IS NOT NULL
        ), link_candidates AS MATERIALIZED (
            SELECT club.id AS provider_club_id, club.source, club.external_key,
                   identifier.organization_id
            FROM active_provider_clubs AS club
            JOIN core.external_identifier AS identifier
              ON club.source = 'time_team'
             AND identifier.namespace = 'time_team_club'
             AND identifier.value = club.external_key
             AND identifier.verification_state = 'verified'
             AND identifier.valid_to IS NULL
            UNION
            SELECT club.id AS provider_club_id, club.source, club.external_key,
                   alias.organization_id
            FROM active_provider_clubs AS club
            JOIN core.organization_alias AS alias
              ON club.source <> 'time_team'
             AND alias.alias_normalized =
                 lower(regexp_replace(club.display_name, '[[:punct:]]', '', 'g'))
        )
        SELECT candidate.provider_club_id, candidate.source,
               candidate.external_key,
               count(DISTINCT candidate.organization_id)::integer
                   AS candidate_organization_count
        FROM link_candidates AS candidate
        GROUP BY candidate.provider_club_id, candidate.source,
                 candidate.external_key
        HAVING count(DISTINCT candidate.organization_id) > 1
        ORDER BY candidate.source, candidate.external_key,
                 candidate.provider_club_id
        """
    )
    published_entry_ids = sorted({str(row["entry_id"]) for row in regatta_results})
    result_people = (
        db.execute(
            """
            SELECT person.id AS result_person_id, person.entry_id,
                   person.role, person.seat, person.person_name
            FROM core.result_person AS person
            WHERE person.entry_id = ANY(%s::uuid[])
            ORDER BY person.entry_id, person.seat NULLS LAST,
                     person.role, person.person_name, person.id
            """,
            (published_entry_ids,),
        )
        if published_entry_ids
        else []
    )
    person_suppressions = (
        db.execute(
            """
            SELECT id AS suppression_id, person_name_normalized,
                   source, provider_club_id
            FROM core.person_suppression
            ORDER BY person_name_normalized, source, provider_club_id, id
            """
        )
        if published_entry_ids
        else []
    )
    return {
        "organizations": organizations,
        "regatta_results": regatta_results,
        "ambiguous_regatta_clubs": ambiguous_regatta_clubs,
        "result_people": result_people,
        "person_suppressions": person_suppressions,
        "slug_history": db.execute(
            "SELECT slug, org_id, is_current, snapshot_id FROM read.org_slug_history"
        ),
        "filings": db.execute(
            """
            SELECT f.id AS filing_id, f.organization_id, f.source_record_id,
                   f.form_type, f.tax_period_begin, f.tax_period_end, f.tax_year,
                   f.amended_return, sr.created_at AS retrieved_at,
                   sr.metadata AS source_metadata,
                   sr.external_key AS source_external_key
            FROM core.filing AS f
            JOIN core.source_record AS sr ON sr.id = f.source_record_id
            WHERE f.is_authoritative = true
              AND f.organization_id = ANY(%s)
            ORDER BY f.organization_id, f.tax_year, f.tax_period_end, f.id
            """,
            (org_ids,),
        ),
        "facts": db.execute(
            """
            SELECT ff.id AS fact_id, ff.filing_id, ff.concept,
                   ff.normalization_version, ff.amount, ff.source_path,
                   ff.quality_state, f.organization_id, f.form_type,
                   f.tax_period_begin, f.tax_period_end, f.tax_year,
                   f.amended_return, sr.created_at AS retrieved_at,
                   sr.metadata AS source_metadata,
                   sr.external_key AS source_external_key,
                   cd.label AS concept_label, cd.unit
            FROM core.filing AS f
            JOIN core.financial_fact AS ff ON ff.filing_id = f.id
            JOIN core.source_record AS sr ON sr.id = f.source_record_id
            JOIN core.concept_definition AS cd ON cd.concept = ff.concept
            WHERE f.is_authoritative = true
              AND f.organization_id = ANY(%s)
            ORDER BY f.organization_id, f.tax_year, ff.concept,
                     ff.normalization_version
            """,
            (org_ids,),
        ),
        "epostcards": db.execute(
            """
            SELECT ep.id AS observation_id, ep.ein, ep.tax_year,
                   ep.tax_period_end, ep.source_record_id,
                   sr.created_at AS retrieved_at
            FROM core.epostcard_observation AS ep
            JOIN core.source_record AS sr ON sr.id = ep.source_record_id
            WHERE ep.ein = ANY(%s)
            ORDER BY ep.ein, ep.tax_year, ep.id
            """,
            (eins,),
        ),
        "aliases": db.execute(
            """
            SELECT organization_id, alias
            FROM core.organization_alias
            WHERE organization_id = ANY(%s)
            ORDER BY organization_id, alias
            """,
            (org_ids,),
        ),
        "metrics": db.execute(
            """
            SELECT mv.id AS metric_value_id, mv.metric_key, mv.metric_version,
                   mv.organization_id, mv.tax_year, mv.fiscal_year_end,
                   mv.value, mv.quality_state, md.unit,
                   ff.source_path, ff.normalization_version,
                   f.id AS filing_id, f.form_type, f.tax_period_begin,
                   f.tax_period_end, f.amended_return,
                   sr.created_at AS retrieved_at,
                   sr.metadata AS source_metadata,
                   sr.external_key AS source_external_key,
                   ARRAY(
                       SELECT DISTINCT input_ff.filing_id::text
                       FROM unnest(mv.input_fact_ids) AS input(id)
                       JOIN core.financial_fact AS input_ff ON input_ff.id = input.id
                   ) AS input_filing_ids
            FROM core.metric_value AS mv
            JOIN core.metric_definition AS md
              ON md.metric_key = mv.metric_key
             AND md.version = mv.metric_version
             AND md.status = 'active'
            LEFT JOIN LATERAL (
                SELECT input_ff.*
                FROM unnest(mv.input_fact_ids) WITH ORDINALITY AS input(id, ordinal)
                JOIN core.financial_fact AS input_ff ON input_ff.id = input.id
                JOIN core.filing AS input_f ON input_f.id = input_ff.filing_id
                ORDER BY (input_f.tax_year = mv.tax_year) DESC, input.ordinal DESC
                LIMIT 1
            ) AS ff ON true
            LEFT JOIN core.filing AS f ON f.id = ff.filing_id
            LEFT JOIN core.source_record AS sr ON sr.id = f.source_record_id
            WHERE mv.organization_id = ANY(%s)
            ORDER BY mv.organization_id, mv.tax_year, mv.metric_key, mv.metric_version
            """,
            (org_ids,),
        ),
        "people": db.execute(
            """
            SELECT pr.id AS person_role_id, pr.filing_id, pr.person_name,
                   pr.title, pr.reportable_compensation, pr.other_compensation,
                   pr.deferred_compensation, pr.nontaxable_benefits,
                   pr.related_organization_compensation, pr.avg_hours_week,
                   pr.role_flags, pr.created_at AS captured_at,
                   f.organization_id, f.form_type, f.tax_period_begin,
                   f.tax_period_end, f.tax_year, f.amended_return,
                   sr.created_at AS retrieved_at,
                   sr.metadata AS source_metadata,
                   sr.external_key AS source_external_key
            FROM core.person_role AS pr
            JOIN core.filing AS f ON f.id = pr.filing_id
            JOIN core.source_record AS sr ON sr.id = f.source_record_id
            WHERE f.is_authoritative = true
              AND f.organization_id = ANY(%s)
            ORDER BY f.organization_id, f.tax_year, pr.person_name, pr.id
            """,
            (org_ids,),
        ),
        "relationships": db.execute(
            """
            SELECT r.from_organization_id AS organization_id,
                   r.relationship_type, r.notes,
                   other.slug AS other_org_slug,
                   other.display_name AS other_display_name
            FROM core.organization_relationship AS r
            JOIN core.organization AS other ON other.id = r.to_organization_id
            WHERE r.from_organization_id = ANY(%s)
            ORDER BY r.from_organization_id, r.relationship_type, other.display_name
            """,
            (org_ids,),
        ),
        "metric_definitions": db.execute(
            """
            SELECT metric_key, version, label, description, unit,
                   eligibility_rule, limitation
            FROM core.metric_definition
            WHERE status = 'active'
            ORDER BY metric_key, version
            """
        ),
    }


def _invariant_failures(
    organizations: list[dict[str, Any]],
    facts: list[dict[str, Any]],
    slug_history: list[dict[str, Any]],
    *,
    build: Mapping[str, list[dict[str, Any]]] | None = None,
    suppressions: Iterable[Mapping[str, Any]] = (),
    result_people: Iterable[Mapping[str, Any]] = (),
) -> tuple[list[str], dict[str, str]]:
    """Fatal structural failures, plus per-filing accounting-identity findings.

    Structural problems (slugs, scope) abort the publish. An accounting
    identity that fails inside a single filing is the filer's error, not
    ours — those filings publish with every fact downgraded to under_review
    rather than blocking the rest of the cohort.
    """
    failures: list[str] = []
    identity_findings: dict[str, str] = {}
    by_filing: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for fact in facts:
        filing_id = str(fact["filing_id"])
        concept = str(fact["concept"])
        current = by_filing[filing_id].get(concept)
        if current is None or int(fact["normalization_version"]) > int(
            current["normalization_version"]
        ):
            by_filing[filing_id][concept] = fact
    identities = (
        ("revenue_less_expenses", "total_revenue", "total_expenses", "revenue"),
        (
            "net_assets_eoy",
            "total_assets_eoy",
            "total_liabilities_eoy",
            "balance sheet",
        ),
    )
    for filing_id, filing_facts in sorted(by_filing.items()):
        for result, left, right, label in identities:
            names = (result, left, right)
            if all(name in filing_facts for name in names) and all(
                filing_facts[name].get("amount") is not None for name in names
            ):
                actual = _decimal(filing_facts[result]["amount"])
                expected = _decimal(filing_facts[left]["amount"]) - _decimal(
                    filing_facts[right]["amount"]
                )
                if abs(actual - expected) > Decimal("1"):
                    message = (
                        f"filing {filing_id} fails {label} identity: "
                        f"{result}={actual}, expected {expected}"
                    )
                    identity_findings[filing_id] = (
                        f"{identity_findings[filing_id]}; {message}"
                        if filing_id in identity_findings
                        else message
                    )
    org_ids = {str(row["organization_id"]) for row in organizations}
    for organization in organizations:
        if not str(organization.get("slug") or "").strip():
            failures.append(
                f"organization {organization['organization_id']} has no slug"
            )
    for history in slug_history:
        slug = str(history.get("slug") or "")
        for organization in organizations:
            if slug == str(organization.get("slug") or "") and str(
                history.get("org_id")
            ) != str(organization["organization_id"]):
                failures.append(
                    f"slug {slug!r} belongs to {history.get('org_id')}, not "
                    f"{organization['organization_id']}"
                )
    # Keep this explicit so malformed fake/source rows do not silently evade scope.
    if any(str(row["organization_id"]) not in org_ids for row in facts):
        failures.append(
            "authoritative facts contain an organization outside publish scope"
        )
    if build is not None:
        failures.extend(_regatta_pii_failures(build, suppressions, result_people))
        failures.extend(_validate_build(build))
    return failures, identity_findings


def _regatta_pii_failures(
    build: Mapping[str, list[dict[str, Any]]],
    suppressions: Iterable[Mapping[str, Any]],
    result_people: Iterable[Mapping[str, Any]],
) -> list[str]:
    """Re-check the assembled public surface for athlete-name leakage."""
    failures: list[str] = []
    suppression_rows = list(suppressions)
    people = [
        person
        for person in result_people
        if _normalize_person_name(person.get("person_name"))
    ]
    contexts = build.get("regatta_crew_contexts", [])
    context_by_identity = {
        (
            str(context["organization_id"]),
            str(context["regatta_key"]),
            str(context["event_key"]),
            str(context["entry_external_key"]),
        ): context
        for context in contexts
    }
    for context in contexts:
        for member in context["crew"]:
            if _suppression_matches(
                str(member["name"]),
                str(context["source"]),
                context.get("provider_club_id"),
                suppression_rows,
            ):
                failures.append(
                    "suppressed result person leaked into assembled crew for "
                    f"entry {context['entry_id']}: {member['name']!r}"
                )
        crew_label = context.get("crew_label")
        for person in people:
            if _person_name_appears(
                person.get("person_name"),
                crew_label,
            ):
                failures.append(
                    "published result person appears in crew_label for "
                    f"entry {context['entry_id']}: {crew_label!r}"
                )
                break

    # Payloads deliberately omit provider_club_id. Recover its scope from the
    # provider entry identity so this traversal independently catches a poisoned
    # payload, including club-scoped suppressions.
    for wrapper in build.get("regatta_payloads", []):
        payload = wrapper["payload"]
        for season in payload.get("seasons", []):
            for regatta in season.get("regattas", []):
                source = str(regatta.get("source_key") or "")
                for event in regatta.get("events", []):
                    for entry in event.get("entries", []):
                        context = context_by_identity.get(
                            (
                                str(wrapper["organization_id"]),
                                str(regatta.get("regatta_key") or ""),
                                str(event.get("event_key") or ""),
                                str(entry.get("entry_external_key") or ""),
                            )
                        )
                        provider_club_id = (
                            context.get("provider_club_id")
                            if context is not None
                            else None
                        )
                        for member in entry.get("crew", []):
                            if _suppression_matches(
                                str(member.get("name") or ""),
                                source,
                                provider_club_id,
                                suppression_rows,
                            ):
                                failures.append(
                                    "suppressed result person leaked into regatta "
                                    f"payload for {wrapper['organization_id']}: "
                                    f"{member.get('name')!r}"
                                )
                        for field_name in ("crew_label", "club_display_name"):
                            value = entry.get(field_name)
                            for person in people:
                                if _person_name_appears(
                                    person.get("person_name"),
                                    value,
                                ):
                                    failures.append(
                                        "published result person appears in "
                                        f"payload {field_name} for "
                                        f"{wrapper['organization_id']}: {value!r}"
                                    )
                                    break

    directory_strings = [
        value for row in build.get("directories", []) for value in _string_values(row)
    ]
    for person in people:
        normalized_name = _normalize_person_name(person.get("person_name"))
        for value in directory_strings:
            if _person_name_appears(normalized_name, value):
                failures.append(
                    "published result person appears in directory search payload: "
                    f"{person.get('person_name')!r}"
                )
                break

    seen: set[tuple[str, str, str, str, str, str]] = set()
    for row in build.get("regatta_rows", []):
        crew_label = row.get("crew_label")
        for person in people:
            if _person_name_appears(person.get("person_name"), crew_label):
                failures.append(
                    "published result person appears in crew_label for "
                    f"entry {row['entry_external_key']}: {crew_label!r}"
                )
                break
        key = (
            str(row["organization_id"]),
            str(row["regatta_key"]),
            str(row["event_key"]),
            str(row["entry_external_key"]),
            str(row.get("crew_label") or ""),
            str(row["metric_key"]),
        )
        if key in seen:
            failures.append(
                "duplicate regatta result key "
                f"{key[0]} {key[1]} {key[2]} {key[3]} {key[4]!r} {key[5]}"
            )
        seen.add(key)
    return failures


def _assemble(
    source: Mapping[str, list[dict[str, Any]]],
    *,
    generated: str,
    parser_version: str,
    under_review_filing_ids: frozenset[str] = frozenset(),
) -> dict[str, list[dict[str, Any]]]:
    organizations = source["organizations"]
    org_by_id = {str(row["organization_id"]): row for row in organizations}
    org_by_ein = {
        str(ein): str(row["organization_id"])
        for row in organizations
        for ein in _sequence(row.get("eins"))
    }
    filings_by_org = _group(source["filings"], "organization_id")
    facts_by_org = _group(source["facts"], "organization_id")
    posts_by_org: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for post in source["epostcards"]:
        org_id = org_by_ein.get(str(post["ein"]))
        if org_id:
            posts_by_org[org_id].append(post)
    aliases_by_org = _group(source["aliases"], "organization_id")
    people_by_org = _group(source["people"], "organization_id")
    relationships_by_org = _group(source["relationships"], "organization_id")

    build: dict[str, list[dict[str, Any]]] = {
        "directories": [],
        "series": [],
        "coverage": [],
        "profiles": [],
        "peers": [],
        "metric_catalog": [],
        "source_registry": [],
        "slugs": [],
        "assembly_errors": [],
        "regatta_rows": [],
        "regatta_payloads": [],
        "regatta_crew_contexts": [],
        "regatta_review_findings": [],
        "regatta_suppressed_entries": [],
        "regatta_u13_entries": [],
    }
    coverage_by_org: dict[str, list[dict[str, Any]]] = {}
    coverage_state_by_org: dict[str, str] = {}
    latest_filing_by_org: dict[str, dict[str, Any]] = {}

    for org_id, organization in org_by_id.items():
        filings = filings_by_org.get(org_id, [])
        posts = posts_by_org.get(org_id, [])
        coverage_state = _coverage_state(filings, posts)
        coverage_state_by_org[org_id] = coverage_state
        coverage = _coverage_rows(org_id, filings, posts)
        coverage_by_org[org_id] = coverage
        build["coverage"].extend(coverage)
        months = [int(_date(row["tax_period_end"]).month) for row in filings]
        fye_month = _mode(months)
        aliases = [str(row["alias"]) for row in aliases_by_org.get(org_id, [])]
        build["directories"].append(
            {
                "organization_id": org_id,
                "slug": str(organization["slug"]),
                "display_name": str(organization["display_name"]),
                "coverage_state": coverage_state,
                "aliases": aliases,
                "search_document": " ".join(
                    [
                        str(organization["display_name"]),
                        str(organization["slug"]),
                        *aliases,
                    ]
                ),
                "fye_month": fye_month,
            }
        )
        if filings:
            latest_filing_by_org[org_id] = max(
                filings,
                key=lambda row: (
                    int(row["tax_year"]),
                    _date(row["tax_period_end"]),
                    str(row["filing_id"]),
                ),
            )
        build["peers"].append(
            {
                "organization_id": org_id,
                "cohort_key": f"type:{organization['org_type']}",
                "reason_labels": ["Same organization type"],
                "label": _humanize(str(organization["org_type"])),
            }
        )
        build["slugs"].append({"slug": str(organization["slug"]), "org_id": org_id})

    for fact in source["facts"]:
        build["series"].append(
            _fact_series(
                fact,
                parser_version,
                downgraded=str(fact["filing_id"]) in under_review_filing_ids,
            )
        )
    for metric in source["metrics"]:
        # A metric inherits under_review when any input fact came from a
        # downgraded filing — a ratio over unreliable inputs is unreliable.
        downgraded = any(
            str(filing_id) in under_review_filing_ids
            for filing_id in _sequence(metric.get("input_filing_ids"))
        )
        try:
            build["series"].append(
                _metric_series(metric, parser_version, downgraded=downgraded)
            )
        except (KeyError, TypeError, ValueError) as exc:
            build["assembly_errors"].append(
                {"message": f"metric {metric.get('metric_value_id')}: {exc}"}
            )

    for org_id, organization in org_by_id.items():
        latest_filing = latest_filing_by_org.get(org_id)
        facts = facts_by_org.get(org_id, [])
        snapshot: list[dict[str, Any]] = []
        if latest_filing is not None:
            latest_id = str(latest_filing["filing_id"])
            latest_by_concept: dict[str, dict[str, Any]] = {}
            for fact in facts:
                if str(fact["filing_id"]) != latest_id:
                    continue
                concept = str(fact["concept"])
                old = latest_by_concept.get(concept)
                if old is None or int(fact["normalization_version"]) > int(
                    old["normalization_version"]
                ):
                    latest_by_concept[concept] = fact
            for concept, (key, label) in SNAPSHOT_FACTS.items():
                if concept in latest_by_concept:
                    fact = latest_by_concept[concept]
                    snapshot.append(
                        {
                            "key": key,
                            "label": label,
                            "ref": _fact_ref(
                                fact,
                                parser_version,
                                downgraded=str(fact["filing_id"])
                                in under_review_filing_ids,
                            ),
                        }
                    )
        elif posts_by_org.get(org_id):
            latest_post = max(
                posts_by_org[org_id],
                key=lambda row: (int(row["tax_year"]), str(row["observation_id"])),
            )
            snapshot.append(
                {
                    "key": "filing_presence",
                    "label": "990-N filing present",
                    "ref": _epostcard_ref(latest_post, parser_version),
                }
            )

        people = _people_payloads(
            filings_by_org.get(org_id, []),
            people_by_org.get(org_id, []),
            parser_version=parser_version,
        )
        profile = {
            "payload_schema_version": PROFILE_SCHEMA_VERSION,
            "org_id": org_id,
            "slug": str(organization["slug"]),
            "header": {
                "display_name": str(organization["display_name"]),
                "legal_name": _optional_string(organization.get("legal_name")),
                "city": _optional_string(organization.get("city")),
                "state": _optional_string(organization.get("state")),
                "org_type": str(organization["org_type"]),
                "program_mix": [],
                "website": _optional_string(organization.get("website")),
                "coverage_state": coverage_state_by_org[org_id],
                "blade_state": "none",
                "filer_note": None,
            },
            "snapshot": snapshot,
            "coverage": [
                {
                    "tax_year": row["tax_year"],
                    "fy_end": row["fy_end"],
                    "status": row["status"],
                }
                for row in coverage_by_org[org_id]
            ],
            "people": people,
            "relationships": [
                {
                    "relationship_type": str(row["relationship_type"]),
                    "other_org_slug": _optional_string(row.get("other_org_slug")),
                    "other_display_name": str(row["other_display_name"]),
                    "note": _optional_string(row.get("notes")),
                }
                for row in relationships_by_org.get(org_id, [])
            ],
            "generated_at": generated,
        }
        build["profiles"].append({"organization_id": org_id, "payload": profile})

    for definition in source["metric_definitions"]:
        build["metric_catalog"].append(
            {
                "metric_key": str(definition["metric_key"]),
                "metric_version": int(definition["version"]),
                "payload": {
                    "key": str(definition["metric_key"]),
                    "version": int(definition["version"]),
                    "label": str(definition["label"]),
                    "description": str(definition["description"]),
                    "unit": str(definition["unit"]),
                    "eligibility_rule": _json_value(definition["eligibility_rule"]),
                    "limitation": _optional_string(definition.get("limitation")),
                },
            }
        )
    regatta_build = _assemble_regattas(
        source.get("regatta_results", []),
        source.get("result_people", []),
        source.get("person_suppressions", []),
        organizations=org_by_id,
        generated=generated,
    )
    for key, rows in regatta_build.items():
        build[key].extend(rows)
    build["source_registry"] = [
        {"source_key": key, "payload": payload}
        for key, payload in SOURCE_REGISTRY.items()
    ]
    return build


def _assemble_regattas(
    rows: Iterable[Mapping[str, Any]],
    result_people: Iterable[Mapping[str, Any]],
    suppressions: Iterable[Mapping[str, Any]],
    *,
    organizations: Mapping[str, Mapping[str, Any]],
    generated: str,
) -> dict[str, list[dict[str, Any]]]:
    people_by_entry = _group(
        [dict(person) for person in result_people],
        "entry_id",
    )
    suppression_rows = list(suppressions)
    assembled: dict[str, list[dict[str, Any]]] = {
        "assembly_errors": [],
        "regatta_rows": [],
        "regatta_payloads": [],
        "regatta_crew_contexts": [],
        "regatta_review_findings": [],
        "regatta_suppressed_entries": [],
        "regatta_u13_entries": [],
    }
    payload_entries: list[dict[str, Any]] = []

    for row in rows:
        org_id = str(row["organization_id"])
        entry_id = str(row["entry_id"])
        source = str(row["source"])
        entry_external_key = str(row["entry_external_key"])
        provider_club_id = row.get("provider_club_id")
        if org_id not in organizations:
            assembled["assembly_errors"].append(
                {
                    "message": (
                        f"regatta entry {entry_id} has organization {org_id} "
                        "outside publish scope"
                    )
                }
            )
            continue
        try:
            season = _regatta_season(row)
            provider_url = _result_provider_url(
                source,
                str(row["regatta_external_key"]),
                season,
            )
        except (TypeError, ValueError) as exc:
            assembled["assembly_errors"].append(
                {"message": f"regatta entry {entry_id}: {exc}"}
            )
            continue

        metric_values = (
            ("finish_time", row.get("time_ms"), "seconds"),
            ("adjusted_time", row.get("adjusted_time_ms"), "seconds"),
            ("handicap", row.get("handicap_ms"), "handicap_seconds"),
            ("place", row.get("position"), "rank"),
            ("adjusted_place", row.get("adjusted_position"), "rank"),
            ("margin", row.get("delta_ms"), "margin_seconds"),
        )
        metrics: list[tuple[str, int | float, str]] = []
        for metric_key, raw_value, unit in metric_values:
            if raw_value is None:
                continue
            value = (
                _number(_decimal(raw_value) / Decimal(1000))
                if metric_key in {"finish_time", "adjusted_time", "handicap", "margin"}
                else _number(raw_value)
            )
            if value is not None:
                metrics.append((metric_key, value, unit))
        if not metrics:
            continue

        people = people_by_entry.get(entry_id, [])
        u13 = _is_u13_event(row.get("age_class_raw"), row.get("event_name"))
        crew: list[dict[str, str]] = []
        suppressed_any = False
        if u13:
            assembled["regatta_u13_entries"].append({"entry_id": entry_id})
        else:
            for person in people:
                if _suppression_matches(
                    str(person["person_name"]),
                    source,
                    provider_club_id,
                    suppression_rows,
                ):
                    suppressed_any = True
                    continue
                crew.append(
                    {
                        "role": _published_crew_role(person.get("role")),
                        "name": str(person["person_name"]),
                    }
                )
        if suppressed_any:
            assembled["regatta_suppressed_entries"].append({"entry_id": entry_id})

        status = str(row["status"])
        review_reasons: list[str] = []
        if row.get("time_ms") is not None:
            finish_seconds = _decimal(row["time_ms"]) / Decimal(1000)
            if finish_seconds < Decimal(60) or finish_seconds > Decimal(6 * 60 * 60):
                review_reasons.append(
                    f"finish time {finish_seconds} seconds is outside 60s–6h"
                )
        if (
            row.get("position") is not None or row.get("adjusted_position") is not None
        ) and not _finished_status(status):
            review_reasons.append(
                f"place is present for non-finished status {status!r}"
            )
        quality_state = "under_review" if review_reasons else "verified"
        if review_reasons:
            assembled["regatta_review_findings"].append(
                {
                    "entry_id": entry_id,
                    "details": {
                        "reasons": review_reasons,
                        "source": source,
                        "regatta_external_key": str(row["regatta_external_key"]),
                        "event_external_key": str(row["event_external_key"]),
                    },
                }
            )

        regatta_key = f"{source}:{row['regatta_external_key']}"
        event_key = str(row["event_external_key"])
        crew_label = None if u13 else _optional_string(row.get("crew_label"))
        result_payloads: list[dict[str, Any]] = []
        for metric_key, value, unit in metrics:
            ref = _result_ref(
                value=value,
                unit=unit,
                season=season,
                quality_state=quality_state,
                source_key=source,
                regatta_external_key=str(row["regatta_external_key"]),
                event_external_key=event_key,
                provider_url=provider_url,
                retrieved_at=row["retrieved_at"],
                parser_version=str(row["parser_version"]),
            )
            result_payloads.append({"metric_key": metric_key, "ref": ref})
            assembled["regatta_rows"].append(
                {
                    "organization_id": org_id,
                    "season": season,
                    "regatta_key": regatta_key,
                    "regatta_name": str(row["regatta_name"]),
                    "regatta_date": (
                        _iso_date(row["start_date"])
                        if row.get("start_date") is not None
                        else None
                    ),
                    "venue": _optional_string(row.get("venue")),
                    "source_key": source,
                    "event_key": event_key,
                    "entry_external_key": entry_external_key,
                    "event_name": str(row["event_name"]),
                    "boat_class": _optional_string(row.get("boat_class_raw")),
                    "round": _optional_string(row.get("round")),
                    "crew_label": crew_label,
                    "crew": [dict(member) for member in crew],
                    "metric_key": metric_key,
                    "value": value,
                    "unit": unit,
                    "status": status,
                    "quality_state": quality_state,
                    "source_ref": ref,
                }
            )

        assembled["regatta_crew_contexts"].append(
            {
                "entry_id": entry_id,
                "organization_id": org_id,
                "regatta_key": regatta_key,
                "event_key": event_key,
                "entry_external_key": entry_external_key,
                "source": source,
                "provider_club_id": provider_club_id,
                "crew_label": crew_label,
                "crew": [dict(member) for member in crew],
            }
        )
        payload_entries.append(
            {
                "organization_id": org_id,
                "season": season,
                "regatta_key": regatta_key,
                "regatta_name": str(row["regatta_name"]),
                "regatta_date": (
                    _iso_date(row["start_date"])
                    if row.get("start_date") is not None
                    else None
                ),
                "venue": _optional_string(row.get("venue")),
                "source_key": source,
                "provider_url": provider_url,
                "event_key": event_key,
                "event_name": str(row["event_name"]),
                "boat_class": _optional_string(row.get("boat_class_raw")),
                "round": _optional_string(row.get("round")),
                "entry": {
                    "entry_external_key": entry_external_key,
                    "crew_label": crew_label,
                    "club_display_name": str(row["club_source_name"]),
                    "status": status,
                    "crew": [dict(member) for member in crew],
                    "results": result_payloads,
                },
            }
        )

    by_org = _group(payload_entries, "organization_id")
    for org_id, org_entries in sorted(by_org.items()):
        seasons: list[dict[str, Any]] = []
        by_season: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for entry in org_entries:
            by_season[int(entry["season"])].append(entry)
        for season in sorted(by_season, reverse=True):
            regattas: list[dict[str, Any]] = []
            by_regatta = _group(by_season[season], "regatta_key")
            for regatta_key, regatta_entries in sorted(by_regatta.items()):
                first = regatta_entries[0]
                events: list[dict[str, Any]] = []
                by_event = _group(regatta_entries, "event_key")
                for event_key, event_entries in sorted(by_event.items()):
                    event = event_entries[0]
                    events.append(
                        {
                            "event_key": event_key,
                            "name": event["event_name"],
                            "boat_class": event["boat_class"],
                            "round": event["round"],
                            "entries": [item["entry"] for item in event_entries],
                        }
                    )
                regattas.append(
                    {
                        "regatta_key": regatta_key,
                        "name": first["regatta_name"],
                        "date": first["regatta_date"],
                        "venue": first["venue"],
                        "source_key": first["source_key"],
                        "provider_url": first["provider_url"],
                        "events": events,
                    }
                )
            seasons.append({"season": season, "regattas": regattas})
        organization = organizations[org_id]
        assembled["regatta_payloads"].append(
            {
                "organization_id": org_id,
                "payload": {
                    "payload_schema_version": RESULTS_SCHEMA_VERSION,
                    "org_id": org_id,
                    "slug": str(organization["slug"]),
                    "seasons": seasons,
                    "generated_at": generated,
                },
            }
        )
    return assembled


def _regatta_season(row: Mapping[str, Any]) -> int:
    if row.get("start_date") is not None:
        return _date(row["start_date"]).year
    if str(row.get("source")) == "time_team":
        years = re.findall(
            r"(?:^|/)((?:19|20)\d{2})(?=/|$)",
            str(row.get("regatta_external_key") or ""),
        )
        if years:
            return int(years[-1])
    raise ValueError("has no start_date or Time-Team year in external key")


def _result_provider_url(source: str, external_key: str, season: int) -> str | None:
    if source == "herenow":
        return f"https://legacy.herenow.com/results/#/races/{external_key}/results"
    if source == "time_team":
        slug = external_key.rsplit("/", 1)[0]
        return f"https://usrowing.regatta.time-team.com/{slug}/{season}/races"
    if source == "regattatiming":
        return (
            "https://results.regattatiming.com/backoffice/webpages/results/"
            f"summary.jsp?raceId={external_key}"
        )
    return None


def _result_ref(
    *,
    value: int | float,
    unit: str,
    season: int,
    quality_state: str,
    source_key: str,
    regatta_external_key: str,
    event_external_key: str,
    provider_url: str | None,
    retrieved_at: object,
    parser_version: str,
) -> dict[str, Any]:
    return {
        "value": value,
        "unit": unit,
        "season": season,
        "quality_state": quality_state,
        "source": {
            "source_key": source_key,
            "regatta_external_key": regatta_external_key,
            "event_external_key": event_external_key,
            "provider_url": provider_url,
        },
        "retrieved_at": _iso_datetime(retrieved_at),
        "parser_version": parser_version,
    }


def _is_u13_event(age_class: object, event_name: object) -> bool:
    patterns = (
        r"(?<![A-Za-z0-9])(?:[WMBG])?U[\s-]?(?:10|11|12|13)[A-Za-z]?(?![A-Za-z0-9])",
        r"(?<![A-Za-z0-9])UNDER[\s-]*(?:10|11|12|13)(?!\d)",
        r"(?<!\d)(?:10|11|12|13)[\s-]*U(?![A-Za-z0-9])",
    )
    return any(
        re.search(pattern, str(value), flags=re.IGNORECASE)
        for value in (age_class, event_name)
        if value is not None
        for pattern in patterns
    )


def _finished_status(status: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", "", status.casefold())
    return normalized in {
        "complete",
        "completed",
        "finish",
        "finished",
        "official",
        "ok",
        "valid",
    }


def _published_crew_role(role: object) -> str:
    normalized = re.sub(r"[^a-z]+", "", str(role or "").casefold())
    if "cox" in normalized:
        return "cox"
    if "coach" in normalized:
        return "coach"
    if "stroke" in normalized:
        return "stroke"
    if "bow" in normalized:
        return "bow"
    return "rower"


def _normalize_person_name(value: object) -> str:
    compatible = unicodedata.normalize("NFKC", str(value or ""))
    without_punctuation = re.sub(r"[^\w\s]", "", compatible.casefold())
    return " ".join(sorted(set(without_punctuation.split())))


def _person_name_appears(person_name: object, value: object) -> bool:
    person_tokens = set(_normalize_person_name(person_name).split())
    value_tokens = set(_normalize_person_name(value).split())
    return bool(person_tokens) and person_tokens <= value_tokens


def _suppression_matches(
    person_name: str,
    source: str,
    provider_club_id: object,
    suppressions: Iterable[Mapping[str, Any]],
) -> bool:
    normalized = _normalize_person_name(person_name)
    return any(
        normalized == _normalize_person_name(row.get("person_name_normalized"))
        and (row.get("source") is None or str(row["source"]) == source)
        and (
            row.get("provider_club_id") is None
            or str(row["provider_club_id"]) == str(provider_club_id)
        )
        for row in suppressions
    )


def _string_values(value: object) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for nested in value.values():
            yield from _string_values(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            yield from _string_values(nested)


def _validate_build(build: Mapping[str, list[dict[str, Any]]]) -> list[str]:
    try:
        from jsonschema import Draft202012Validator, FormatChecker
    except ImportError as exc:  # pragma: no cover - production packaging guard
        raise RuntimeError(
            "publish requires jsonschema at runtime to enforce public contracts"
        ) from exc

    profile_schema = _load_contract_schema("org-profile-payload.v1.schema.json")
    source_schema = _load_contract_schema("source-ref.v1.schema.json")
    regatta_schema = _load_contract_schema("org-regatta-payload.v1.schema.json")
    result_ref_schema = _load_contract_schema("result-ref.v1.schema.json")
    profile_validator = Draft202012Validator(
        profile_schema, format_checker=FormatChecker()
    )
    source_validator = Draft202012Validator(
        source_schema, format_checker=FormatChecker()
    )
    regatta_validator = Draft202012Validator(
        regatta_schema, format_checker=FormatChecker()
    )
    result_ref_validator = Draft202012Validator(
        result_ref_schema, format_checker=FormatChecker()
    )
    failures = [str(row["message"]) for row in build.get("assembly_errors", [])]
    series_keys: set[tuple[str, str, int, int]] = set()
    for row in build["series"]:
        key = (
            str(row["organization_id"]),
            str(row["series_key"]),
            int(row["series_version"]),
            int(row["tax_year"]),
        )
        if key in series_keys:
            failures.append(
                f"duplicate financial series key {key[0]} {key[1]} v{key[2]} FY{key[3]}"
            )
        series_keys.add(key)
        errors = sorted(source_validator.iter_errors(row["source_ref"]), key=_error_key)
        failures.extend(
            f"SourceRef {row['organization_id']} {row['series_key']} "
            f"FY{row['tax_year']}: {_validation_message(error)}"
            for error in errors
        )
    for row in build["profiles"]:
        errors = sorted(profile_validator.iter_errors(row["payload"]), key=_error_key)
        failures.extend(
            f"profile {row['organization_id']}: {_validation_message(error)}"
            for error in errors
        )
    for row in build.get("regatta_rows", []):
        errors = sorted(
            result_ref_validator.iter_errors(row["source_ref"]),
            key=_error_key,
        )
        failures.extend(
            f"ResultRef {row['organization_id']} {row['regatta_key']} "
            f"{row['event_key']} {row['metric_key']}: "
            f"{_validation_message(error)}"
            for error in errors
        )
    for row in build.get("regatta_payloads", []):
        errors = sorted(
            regatta_validator.iter_errors(row["payload"]),
            key=_error_key,
        )
        failures.extend(
            f"regatta payload {row['organization_id']}: {_validation_message(error)}"
            for error in errors
        )
    return failures


def _load_contract_schema(filename: str) -> dict[str, Any]:
    path = __file__
    # publish.py is pipeline/src/crewgraphs/jobs/publish.py; parents[4] is repo.
    from pathlib import Path

    repo = Path(path).resolve().parents[4]
    return json.loads(
        (repo / "packages" / "contracts" / "schemas" / filename).read_text(
            encoding="utf-8"
        )
    )


def _insert_build(
    db: DatabaseGateway,
    *,
    snapshot_id: str,
    generated: str,
    build: Mapping[str, list[dict[str, Any]]],
) -> None:
    for row in build["directories"]:
        db.execute(
            """
            INSERT INTO read.org_directory
                (snapshot_id, organization_id, slug, display_name,
                 coverage_state, aliases, search_text, fye_month, created_at)
            VALUES (%s, %s, %s, %s, %s, %s::jsonb,
                    to_tsvector('simple', %s), %s, %s::timestamptz)
            """,
            (
                snapshot_id,
                row["organization_id"],
                row["slug"],
                row["display_name"],
                row["coverage_state"],
                json.dumps(row["aliases"]),
                row["search_document"],
                row["fye_month"],
                generated,
            ),
        )
    for row in build["series"]:
        db.execute(
            """
            INSERT INTO read.org_financial_series
                (snapshot_id, organization_id, series_key, series_version,
                 tax_year, fiscal_year_end, value, quality_state,
                 is_amended, source_ref, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s::jsonb, %s::timestamptz)
            """,
            (
                snapshot_id,
                row["organization_id"],
                row["series_key"],
                row["series_version"],
                row["tax_year"],
                row["fiscal_year_end"],
                row["value"],
                row["quality_state"],
                row["is_amended"],
                json.dumps(row["source_ref"]),
                generated,
            ),
        )
    for row in build["coverage"]:
        db.execute(
            """
            INSERT INTO read.org_filing_coverage
                (snapshot_id, organization_id, tax_year, status, created_at)
            VALUES (%s, %s, %s, %s, %s::timestamptz)
            """,
            (
                snapshot_id,
                row["organization_id"],
                row["tax_year"],
                row["status"],
                generated,
            ),
        )
    for row in build["profiles"]:
        db.execute(
            """
            INSERT INTO read.org_profile
                (snapshot_id, organization_id, payload,
                 payload_schema_version, created_at)
            VALUES (%s, %s, %s::jsonb, %s, %s::timestamptz)
            """,
            (
                snapshot_id,
                row["organization_id"],
                json.dumps(row["payload"]),
                PROFILE_SCHEMA_VERSION,
                generated,
            ),
        )
    for row in build["peers"]:
        db.execute(
            """
            INSERT INTO read.org_peer_cohort
                (snapshot_id, organization_id, cohort_key,
                 reason_labels, created_at)
            VALUES (%s, %s, %s, %s::jsonb, %s::timestamptz)
            """,
            (
                snapshot_id,
                row["organization_id"],
                row["cohort_key"],
                json.dumps(row["reason_labels"]),
                generated,
            ),
        )
    for row in build["metric_catalog"]:
        db.execute(
            """
            INSERT INTO read.metric_catalog
                (snapshot_id, metric_key, metric_version, payload, created_at)
            VALUES (%s, %s, %s, %s::jsonb, %s::timestamptz)
            """,
            (
                snapshot_id,
                row["metric_key"],
                row["metric_version"],
                json.dumps(row["payload"]),
                generated,
            ),
        )
    for row in build["source_registry"]:
        db.execute(
            """
            INSERT INTO read.source_registry_public
                (snapshot_id, source_key, payload, created_at)
            VALUES (%s, %s, %s::jsonb, %s::timestamptz)
            """,
            (
                snapshot_id,
                row["source_key"],
                json.dumps(row["payload"]),
                generated,
            ),
        )
    for row in build["regatta_rows"]:
        db.execute(
            """
            INSERT INTO read.org_regatta_result
                (snapshot_id, organization_id, season, regatta_key,
                 regatta_name, regatta_date, venue, source_key,
                 event_key, entry_external_key, event_name, boat_class, round,
                 crew_label, crew, metric_key, value, unit, status,
                 quality_state, source_ref, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s,
                    %s::jsonb, %s::timestamptz)
            """,
            (
                snapshot_id,
                row["organization_id"],
                row["season"],
                row["regatta_key"],
                row["regatta_name"],
                row["regatta_date"],
                row["venue"],
                row["source_key"],
                row["event_key"],
                row["entry_external_key"],
                row["event_name"],
                row["boat_class"],
                row["round"],
                row["crew_label"],
                json.dumps(row["crew"]),
                row["metric_key"],
                row["value"],
                row["unit"],
                row["status"],
                row["quality_state"],
                json.dumps(row["source_ref"]),
                generated,
            ),
        )
    for row in build["slugs"]:
        db.execute(
            """
            INSERT INTO read.org_slug_history
                (slug, snapshot_id, org_id, is_current, created_at)
            VALUES (%s, %s, %s, true, %s::timestamptz)
            ON CONFLICT (slug) DO NOTHING
            """,
            (row["slug"], snapshot_id, row["org_id"], generated),
        )


def _coverage_state(
    filings: Iterable[Mapping[str, Any]], posts: Iterable[Mapping[str, Any]]
) -> str:
    forms = {str(row["form_type"]) for row in filings}
    if "990" in forms:
        return "990"
    if "990EZ" in forms:
        return "990ez"
    if any(True for _ in posts):
        return "990n_only"
    return "none"


def _coverage_rows(
    organization_id: str,
    filings: list[dict[str, Any]],
    posts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    observed_years = {int(row["tax_year"]) for row in filings}
    observed_years.update(int(row["tax_year"]) for row in posts)
    if not observed_years:
        return []
    filing_by_year: dict[int, dict[str, Any]] = {}
    for filing in filings:
        year = int(filing["tax_year"])
        old = filing_by_year.get(year)
        if old is None or _display_precedence(filing) > _display_precedence(old):
            filing_by_year[year] = filing
    post_by_year = {int(row["tax_year"]): row for row in posts}
    rows: list[dict[str, Any]] = []
    for year in range(min(observed_years), max(observed_years) + 1):
        filing = filing_by_year.get(year)
        post = post_by_year.get(year)
        if filing is not None:
            status = (
                "amended"
                if bool(filing["amended_return"])
                else "990"
                if str(filing["form_type"]) == "990"
                else "990ez"
            )
            fy_end = _iso_date(filing["tax_period_end"])
        elif post is not None:
            status = "990n"
            fy_end = _iso_date(post.get("tax_period_end") or date(year, 12, 31))
        else:
            status = "missing"
            fy_end = None
        rows.append(
            {
                "organization_id": organization_id,
                "tax_year": year,
                "fy_end": fy_end,
                "status": status,
            }
        )
    return rows


def _fact_series(
    fact: Mapping[str, Any], parser_version: str, *, downgraded: bool = False
) -> dict[str, Any]:
    quality_state = "under_review" if downgraded else str(fact["quality_state"])
    return {
        "organization_id": str(fact["organization_id"]),
        "series_key": str(fact["concept"]),
        "series_version": int(fact["normalization_version"]),
        "tax_year": int(fact["tax_year"]),
        "fiscal_year_end": _iso_date(fact["tax_period_end"]),
        "value": _number(fact.get("amount")),
        "quality_state": quality_state,
        "is_amended": bool(fact["amended_return"]),
        "source_ref": _fact_ref(fact, parser_version, downgraded=downgraded),
    }


def _metric_series(
    metric: Mapping[str, Any], parser_version: str, *, downgraded: bool = False
) -> dict[str, Any]:
    if not metric.get("filing_id") or not metric.get("source_path"):
        raise ValueError("has no input financial-fact provenance")
    value = _number(metric.get("value"))
    quality_state = "under_review" if downgraded else str(metric["quality_state"])
    ref = _source_ref(
        value=value,
        # SourceRef v1 has no percent unit. The canonical public fixtures encode
        # fraction-valued percentage metrics as USD; metric_catalog retains the
        # definition's semantically correct ``percent`` display unit.
        unit=str(metric["unit"]) if str(metric["unit"]) in {"USD", "count"} else "USD",
        tax_year=int(metric["tax_year"]),
        period_begin=metric.get("tax_period_begin"),
        period_end=metric["fiscal_year_end"],
        quality_state=quality_state,
        source_key="irs_990_xml",
        form_type=str(metric["form_type"]),
        filing_id=str(metric["filing_id"]),
        source_path=str(metric["source_path"]),
        is_amended=bool(metric["amended_return"]),
        retrieved_at=metric["retrieved_at"],
        parser_version=parser_version,
        metric={"key": str(metric["metric_key"]), "version": int(metric["metric_version"])},
        source_metadata=metric.get("source_metadata"),
        source_external_key=metric.get("source_external_key"),
        single_authoritative_filing=len(
            {str(filing_id) for filing_id in _sequence(metric.get("input_filing_ids"))}
        ) == 1,
    )
    return {
        "organization_id": str(metric["organization_id"]),
        "series_key": str(metric["metric_key"]),
        "series_version": int(metric["metric_version"]),
        "tax_year": int(metric["tax_year"]),
        "fiscal_year_end": _iso_date(metric["fiscal_year_end"]),
        "value": value,
        "quality_state": quality_state,
        "is_amended": bool(metric["amended_return"]),
        "source_ref": ref,
    }


def _fact_ref(
    fact: Mapping[str, Any], parser_version: str, *, downgraded: bool = False
) -> dict[str, Any]:
    return _source_ref(
        value=_number(fact.get("amount")),
        unit=str(fact["unit"]),
        tax_year=int(fact["tax_year"]),
        period_begin=fact.get("tax_period_begin"),
        period_end=fact["tax_period_end"],
        quality_state="under_review" if downgraded else str(fact["quality_state"]),
        source_key="irs_990_xml",
        form_type=str(fact["form_type"]),
        filing_id=str(fact["filing_id"]),
        source_path=str(fact["source_path"]),
        is_amended=bool(fact["amended_return"]),
        retrieved_at=fact["retrieved_at"],
        parser_version=parser_version,
        metric=None,
        source_metadata=fact.get("source_metadata"),
        source_external_key=fact.get("source_external_key"),
    )


def _epostcard_ref(post: Mapping[str, Any], parser_version: str) -> dict[str, Any]:
    period_end = post.get("tax_period_end") or date(int(post["tax_year"]), 12, 31)
    return _source_ref(
        value=1,
        unit="count",
        tax_year=int(post["tax_year"]),
        period_begin=None,
        period_end=period_end,
        quality_state="verified",
        source_key="irs_990n",
        form_type="990N",
        filing_id=str(post["observation_id"]),
        source_path="epostcard_presence",
        is_amended=False,
        retrieved_at=post["retrieved_at"],
        parser_version=parser_version,
        metric=None,
    )


def _people_payloads(
    filings: list[dict[str, Any]],
    people: list[dict[str, Any]],
    *,
    parser_version: str,
) -> list[dict[str, Any]]:
    """One people entry per filed year that reported any officers, newest first.

    Year display precedence mirrors ``_coverage_rows``: an amended return beats
    the original, a later period end beats an earlier one.
    """
    filing_by_year: dict[int, dict[str, Any]] = {}
    for filing in filings:
        year = int(filing["tax_year"])
        old = filing_by_year.get(year)
        if old is None or _display_precedence(filing) > _display_precedence(old):
            filing_by_year[year] = filing
    rows_by_filing = _group(people, "filing_id")
    payloads: list[dict[str, Any]] = []
    for year in sorted(filing_by_year, reverse=True):
        filing = filing_by_year[year]
        entry = _people_year(
            filing,
            rows_by_filing.get(str(filing["filing_id"]), []),
            parser_version=parser_version,
        )
        if entry is not None:
            payloads.append(entry)
    return payloads


def _display_precedence(filing: Mapping[str, Any]) -> tuple[bool, date, str]:
    return (
        bool(filing["amended_return"]),
        _date(filing["tax_period_end"]),
        str(filing["filing_id"]),
    )


def _people_year(
    filing: Mapping[str, Any],
    rows: list[dict[str, Any]],
    *,
    parser_version: str,
) -> dict[str, Any] | None:
    rows = _latest_captures(rows)
    if not rows:
        return None
    filing_id = str(filing["filing_id"])
    compensated: list[dict[str, Any]] = []
    volunteer_count = 0
    source_path = (
        "Form990PartVIISectionAGrp"
        if str(filing["form_type"]) == "990"
        else "OfficerDirectorTrusteeEmplGrp"
    )
    for row in rows:
        total = sum(
            _decimal(row.get(column))
            for column in (
                "reportable_compensation",
                "other_compensation",
                "deferred_compensation",
                "nontaxable_benefits",
                "related_organization_compensation",
            )
        )
        if total <= 0:
            volunteer_count += 1
            continue
        value = _number(total)
        compensated.append(
            {
                "name": str(row["person_name"]),
                "title": _optional_string(row.get("title")),
                "avg_hours_week": _number(row.get("avg_hours_week")),
                "role_flags": [str(flag) for flag in _sequence(row.get("role_flags"))],
                "total_comp": value,
                "ref": _source_ref(
                    value=value,
                    unit="USD",
                    tax_year=int(filing["tax_year"]),
                    period_begin=filing.get("tax_period_begin"),
                    period_end=filing["tax_period_end"],
                    quality_state="verified",
                    source_key="irs_990_xml",
                    form_type=str(filing["form_type"]),
                    filing_id=filing_id,
                    source_path=source_path,
                    is_amended=bool(filing["amended_return"]),
                    retrieved_at=filing["retrieved_at"],
                    parser_version=parser_version,
                    metric=None,
                    source_metadata=filing.get("source_metadata"),
                    source_external_key=filing.get("source_external_key"),
                ),
            }
        )
    group_ref = _source_ref(
        value=volunteer_count,
        unit="count",
        tax_year=int(filing["tax_year"]),
        period_begin=filing.get("tax_period_begin"),
        period_end=filing["tax_period_end"],
        quality_state="verified",
        source_key="irs_990_xml",
        form_type=str(filing["form_type"]),
        filing_id=filing_id,
        source_path=source_path,
        is_amended=bool(filing["amended_return"]),
        retrieved_at=filing["retrieved_at"],
        parser_version=parser_version,
        metric=None,
    )
    return {
        "tax_year": int(filing["tax_year"]),
        "compensated": compensated,
        "volunteer_count": volunteer_count,
        "ref": group_ref,
    }


def _latest_captures(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse superseded person_role rows to the newest capture per person.

    Derive never updates core rows; a richer re-parse inserts a new row for the
    same (filing, person, title) instead. Later captures win here, so published
    profiles show the fullest extraction while old rows stay behind as evidence.
    """

    def order(row: Mapping[str, Any]) -> tuple[str, str]:
        captured_at = row.get("captured_at")
        return (
            _iso_datetime(captured_at) if captured_at is not None else "",
            str(row.get("person_role_id")),
        )

    latest: dict[tuple[str, str | None], dict[str, Any]] = {}
    for row in rows:
        key = (str(row["person_name"]), _optional_string(row.get("title")))
        current = latest.get(key)
        if current is None or order(row) > order(current):
            latest[key] = row
    return [
        row
        for row in rows
        if latest[(str(row["person_name"]), _optional_string(row.get("title")))] is row
    ]


def _source_ref(
    *,
    value: int | float | None,
    unit: str,
    tax_year: int,
    period_begin: object,
    period_end: object,
    quality_state: str,
    source_key: str,
    form_type: str,
    filing_id: str,
    source_path: str,
    is_amended: bool,
    retrieved_at: object,
    parser_version: str,
    metric: dict[str, Any] | None,
    source_metadata: object = None,
    source_external_key: object = None,
    single_authoritative_filing: bool = True,
) -> dict[str, Any]:
    end = _date(period_end)
    return {
        "value": value,
        "unit": unit,
        "period": {
            "tax_year": tax_year,
            "fy_end": end.isoformat(),
            "label": _period_label(tax_year, period_begin, end),
        },
        "quality_state": quality_state,
        "source": {
            "source_key": source_key,
            "form_type": form_type,
            "filing_id": filing_id,
            "source_path": source_path,
            "raw_url": _raw_url(
                source_key,
                source_metadata,
                source_external_key,
                single_authoritative_filing=single_authoritative_filing,
            ),
            "is_amended": is_amended,
        },
        "retrieved_at": _iso_datetime(retrieved_at),
        "parser_version": parser_version,
        "metric": metric,
    }


def _raw_url(
    source_key: str,
    source_metadata: object,
    source_external_key: object,
    *,
    single_authoritative_filing: bool,
) -> str | None:
    if source_key != "irs_990_xml" or not single_authoritative_filing:
        return None

    if isinstance(source_metadata, Mapping):
        candidate = source_metadata.get("url")
        if isinstance(candidate, str):
            candidate = candidate.strip()
            parsed = urlparse(candidate)
            if (
                candidate
                and not any(char.isspace() for char in candidate)
                and parsed.scheme in {"http", "https"}
                and parsed.netloc
            ):
                return candidate

    external_key = _optional_string(source_external_key)
    if not external_key or any(char.isspace() for char in external_key):
        return None
    return GT_LAKE_XML_URL.format(object_id=external_key)


def _period_label(tax_year: int, period_begin: object, period_end: date) -> str:
    if period_begin is None:
        try:
            begin = period_end.replace(year=period_end.year - 1) + timedelta(days=1)
        except ValueError:
            begin = period_end.replace(year=period_end.year - 1, day=28) + timedelta(
                days=1
            )
    else:
        begin = _date(period_begin)
    return (
        f"FY{tax_year} ({begin.strftime('%b')} {begin.year}"
        f"\N{EN DASH}{period_end.strftime('%b')} {period_end.year})"
    )


def _group(rows: Iterable[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row[key])].append(row)
    return grouped


def _mode(values: list[int]) -> int | None:
    if not values:
        return None
    counts = Counter(values)
    return min(counts, key=lambda value: (-counts[value], value))


def _humanize(value: str) -> str:
    return value.replace("_", " ").title()


def _sequence(value: object) -> list[Any]:
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return [value]
        return list(decoded) if isinstance(decoded, list) else [value]
    return list(value) if isinstance(value, (list, tuple, set)) else []


def _json_value(value: object) -> object:
    return json.loads(value) if isinstance(value, str) else value


def _optional_string(value: object) -> str | None:
    return None if value is None else str(value)


def _decimal(value: object) -> Decimal:
    if value is None:
        return Decimal(0)
    return Decimal(str(value))


def _number(value: object) -> int | float | None:
    if value is None:
        return None
    decimal = _decimal(value)
    return int(decimal) if decimal == decimal.to_integral() else float(decimal)


def _date(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _iso_date(value: object) -> str:
    return _date(value).isoformat()


def _iso_datetime(value: object) -> str:
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value)
        parsed = datetime.fromisoformat(
            text[:-1] + "+00:00" if text.endswith("Z") else text
        )
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _error_key(error: Any) -> tuple[str, str]:
    return ("/".join(str(part) for part in error.absolute_path), error.message)


def _validation_message(error: Any) -> str:
    path = "/".join(str(part) for part in error.absolute_path) or "<root>"
    return f"{path}: {error.message}"


_GC_SQL = """
WITH stale AS MATERIALIZED (
    SELECT id
    FROM ops.publish_snapshot
    ORDER BY created_at DESC, id DESC
    OFFSET 3
), preserved_slugs AS (
    UPDATE read.org_slug_history
    SET snapshot_id = %s
    WHERE snapshot_id IN (SELECT id FROM stale)
    RETURNING slug
), directory_deleted AS (
    DELETE FROM read.org_directory WHERE snapshot_id IN (SELECT id FROM stale)
), series_deleted AS (
    DELETE FROM read.org_financial_series WHERE snapshot_id IN (SELECT id FROM stale)
), regatta_results_deleted AS (
    DELETE FROM read.org_regatta_result WHERE snapshot_id IN (SELECT id FROM stale)
), coverage_deleted AS (
    DELETE FROM read.org_filing_coverage WHERE snapshot_id IN (SELECT id FROM stale)
), peers_deleted AS (
    DELETE FROM read.org_peer_cohort WHERE snapshot_id IN (SELECT id FROM stale)
), profiles_deleted AS (
    DELETE FROM read.org_profile WHERE snapshot_id IN (SELECT id FROM stale)
), metrics_deleted AS (
    DELETE FROM read.metric_catalog WHERE snapshot_id IN (SELECT id FROM stale)
), sources_deleted AS (
    DELETE FROM read.source_registry_public WHERE snapshot_id IN (SELECT id FROM stale)
), snapshots_deleted AS (
    DELETE FROM ops.publish_snapshot WHERE id IN (SELECT id FROM stale)
    RETURNING id
)
SELECT count(*)::integer AS deleted_count FROM snapshots_deleted
"""


__all__ = ["PublishInvariantError", "publish"]
