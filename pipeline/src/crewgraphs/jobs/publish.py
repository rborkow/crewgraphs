"""Build and atomically activate the public CrewGraphs read model."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from ..concept_map import load_concept_map
from ..db import DatabaseGateway
from ..runlog import IngestRun


PROFILE_SCHEMA_VERSION = 1
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
        validation_failures = _validate_build(build)
        if validation_failures:
            raise PublishInvariantError(
                "publish contract validation failed:\n- "
                + "\n- ".join(validation_failures)
            )

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
    return {
        "organizations": organizations,
        "slug_history": db.execute(
            "SELECT slug, org_id, is_current, snapshot_id FROM read.org_slug_history"
        ),
        "filings": db.execute(
            """
            SELECT f.id AS filing_id, f.organization_id, f.source_record_id,
                   f.form_type, f.tax_period_begin, f.tax_period_end, f.tax_year,
                   f.amended_return, sr.created_at AS retrieved_at
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
                   sr.created_at AS retrieved_at
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
        ("net_assets_eoy", "total_assets_eoy", "total_liabilities_eoy", "balance sheet"),
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
        failures.append("authoritative facts contain an organization outside publish scope")
    return failures, identity_findings


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
        build["slugs"].append(
            {"slug": str(organization["slug"]), "org_id": org_id}
        )

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
                                downgraded=str(fact["filing_id"]) in under_review_filing_ids,
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
        build["profiles"].append(
            {"organization_id": org_id, "payload": profile}
        )

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
    build["source_registry"] = [
        {"source_key": key, "payload": payload}
        for key, payload in SOURCE_REGISTRY.items()
    ]
    return build


def _validate_build(build: Mapping[str, list[dict[str, Any]]]) -> list[str]:
    try:
        from jsonschema import Draft202012Validator, FormatChecker
    except ImportError as exc:  # pragma: no cover - production packaging guard
        raise RuntimeError(
            "publish requires jsonschema at runtime to enforce public contracts"
        ) from exc

    profile_schema = _load_contract_schema("org-profile-payload.v1.schema.json")
    source_schema = _load_contract_schema("source-ref.v1.schema.json")
    profile_validator = Draft202012Validator(
        profile_schema, format_checker=FormatChecker()
    )
    source_validator = Draft202012Validator(
        source_schema, format_checker=FormatChecker()
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
                "duplicate financial series key "
                f"{key[0]} {key[1]} v{key[2]} FY{key[3]}"
            )
        series_keys.add(key)
        errors = sorted(source_validator.iter_errors(row["source_ref"]), key=_error_key)
        failures.extend(
            f"SourceRef {row['organization_id']} {row['series_key']} "
            f"FY{row['tax_year']}: {_validation_message(error)}"
            for error in errors
        )
    for row in build["profiles"]:
        errors = sorted(
            profile_validator.iter_errors(row["payload"]), key=_error_key
        )
        failures.extend(
            f"profile {row['organization_id']}: {_validation_message(error)}"
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
                else "990" if str(filing["form_type"]) == "990" else "990ez"
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
    return [row for row in rows if latest[(str(row["person_name"]), _optional_string(row.get("title")))] is row]


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
            "raw_url": None,
            "is_amended": is_amended,
        },
        "retrieved_at": _iso_datetime(retrieved_at),
        "parser_version": parser_version,
        "metric": metric,
    }


def _period_label(tax_year: int, period_begin: object, period_end: date) -> str:
    if period_begin is None:
        try:
            begin = period_end.replace(year=period_end.year - 1) + timedelta(days=1)
        except ValueError:
            begin = period_end.replace(year=period_end.year - 1, day=28) + timedelta(days=1)
    else:
        begin = _date(period_begin)
    return (
        f"FY{tax_year} ({begin.strftime('%b')} {begin.year}"
        f"\N{EN DASH}{period_end.strftime('%b')} {period_end.year})"
    )


def _group(
    rows: Iterable[dict[str, Any]], key: str
) -> dict[str, list[dict[str, Any]]]:
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
        parsed = datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)
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
