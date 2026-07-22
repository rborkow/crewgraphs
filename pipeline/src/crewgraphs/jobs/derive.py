"""Promote parsed filing extracts into immutable canonical facts and metrics."""

from __future__ import annotations

import json
import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any

from ..concept_map import ConceptMap, load_concept_map
from ..db import DatabaseGateway
from ..runlog import IngestRun


_FACT_INPUTS: dict[str, tuple[str, ...]] = {
    "operating_margin": ("total_revenue", "total_expenses"),
    "contribution_dependency": ("contributions_grants", "total_revenue"),
    "program_service_share": ("program_service_expense", "total_revenue"),
    "compensation_intensity": ("salaries_benefits_total", "total_expenses"),
    "membership_dues_share": ("membership_dues", "total_revenue"),
}


def derive(db: DatabaseGateway) -> str:
    """Create immutable filing facts and their metric read inputs.

    The job intentionally does not update core facts.  That makes a changed
    parser/concept map a new normalization version rather than a rewrite of
    evidence that was previously published.
    """
    concept_map = load_concept_map()
    normalization_version = _normalization_version(concept_map)
    with IngestRun(
        db,
        job_name="derive",
        source="crewgraphs",
        params={"concept_map_version": concept_map.version},
    ) as run:
        for stat in (
            "filings_inserted",
            "facts_inserted",
            "person_roles_inserted",
            "metrics_inserted",
            "suppressed_metrics",
            "skipped_unmapped",
            "amendment_reviews",
        ):
            run.add_stat(stat, 0)

        org_by_ein = _organization_by_ein(db)
        extracts = db.execute(
            """
            SELECT id, source_record_id, ein, irs_object_id, form_type,
                   return_version, tax_period_begin, tax_period_end,
                   amended_return, concepts, people
            FROM staging.filing_extract
            ORDER BY ein, tax_period_end, form_type, irs_object_id
            """
        )
        staged_statuses: dict[str, Mapping[str, Any]] = {}
        grouped: dict[tuple[str, object, str], list[dict[str, Any]]] = defaultdict(list)
        for extract in extracts:
            form = _canonical_form(extract.get("form_type"))
            if form is None or extract.get("tax_period_end") is None:
                continue
            grouped[(str(extract["ein"]), extract["tax_period_end"], form)].append(extract)
            staged_statuses[str(extract["irs_object_id"])] = _concepts(extract.get("concepts"))

        for (ein, period_end, form), group in grouped.items():
            organization_id = org_by_ein.get(ein)
            if organization_id is None:
                run.add_stat("skipped_unmapped", len(group))
                continue
            _derive_filing_group(
                db,
                run,
                group,
                ein=ein,
                organization_id=organization_id,
                period_end=period_end,
                form=form,
                concept_map=concept_map,
                normalization_version=normalization_version,
            )

        definitions = db.execute(
            """
            SELECT metric_key, version, eligibility_rule
            FROM core.metric_definition
            WHERE status = 'active'
            ORDER BY metric_key, version
            """
        )
        _derive_metrics(
            db,
            run,
            definitions,
            normalization_version=normalization_version,
            staged_statuses=staged_statuses,
        )

    return _summary(run.stats)


def _derive_filing_group(
    db: DatabaseGateway,
    run: IngestRun,
    group: list[dict[str, Any]],
    *,
    ein: str,
    organization_id: object,
    period_end: object,
    form: str,
    concept_map: ConceptMap,
    normalization_version: int,
) -> None:
    """Insert one precedence group without ever revising an old filing.

    Amendment policy: an amended return outranks a non-amended return; ties
    use the lexically greatest IRS object id.  If an already-inserted filing
    loses to a newly arriving amended return, insert the newcomer as
    authoritative and open ``amendment_review``.  The old flag is deliberately
    not flipped: only a curator may resolve that temporary dual-authority state.
    """
    existing = db.execute(
        """
        SELECT id, irs_object_id, amended_return, is_authoritative
        FROM core.filing
        WHERE ein = %s AND tax_period_end = %s AND form_type = %s
        """,
        (ein, period_end, form),
    )
    ranked = sorted(group, key=_precedence_key, reverse=True)
    best_staged = ranked[0]
    best_existing = max(existing, key=_precedence_key) if existing else None
    staged_beats_existing = best_existing is None or _precedence_key(best_staged) > _precedence_key(best_existing)

    for extract in group:
        is_winner = str(extract["irs_object_id"]) == str(best_staged["irs_object_id"])
        is_authoritative = bool(is_winner and staged_beats_existing)
        filing_id, inserted = _insert_filing(
            db,
            extract,
            organization_id=organization_id,
            form=form,
            is_authoritative=is_authoritative,
        )
        if inserted:
            run.add_stat("filings_inserted")
            if (
                is_authoritative
                and bool(extract.get("amended_return"))
                and best_existing is not None
                and bool(best_existing.get("is_authoritative"))
            ):
                _insert_amendment_review(db, filing_id, best_existing, extract)
                run.add_stat("amendment_reviews")
        # Facts belong to every filing, including non-authoritative returns.
        _insert_facts(db, run, filing_id, extract, form, concept_map, normalization_version)
        _insert_people(db, run, filing_id, extract.get("people"))


def _organization_by_ein(db: DatabaseGateway) -> dict[str, object]:
    rows = db.execute(
        """
        SELECT value AS ein, organization_id
        FROM core.external_identifier
        WHERE namespace = 'irs_ein'
          AND verification_state = 'verified'
          AND valid_to IS NULL
        """
    )
    return {str(row["ein"]): row["organization_id"] for row in rows}


def _insert_filing(
    db: DatabaseGateway,
    extract: Mapping[str, Any],
    *,
    organization_id: object,
    form: str,
    is_authoritative: bool,
) -> tuple[object, bool]:
    begin = extract.get("tax_period_begin")
    end = extract["tax_period_end"]
    # IRS TaxYr is the year the reporting period *began* for fiscal filers;
    # calendar filings use the period-end year when no begin date is available.
    tax_year = _year(begin if begin is not None else end)
    rows = db.execute(
        """
        INSERT INTO core.filing
            (organization_id, source_record_id, ein, form_type,
             tax_period_begin, tax_period_end, tax_year, return_version,
             irs_object_id, amended_return, is_authoritative)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING
        RETURNING id
        """,
        (
            organization_id,
            extract.get("source_record_id"),
            str(extract["ein"]),
            form,
            begin,
            end,
            tax_year,
            extract.get("return_version"),
            str(extract["irs_object_id"]),
            bool(extract.get("amended_return")),
            is_authoritative,
        ),
    )
    if rows:
        return rows[0]["id"], True
    rows = db.execute(
        "SELECT id FROM core.filing WHERE ein = %s AND irs_object_id = %s",
        (str(extract["ein"]), str(extract["irs_object_id"])),
    )
    if not rows:
        raise RuntimeError("core.filing conflict did not expose its existing row")
    return rows[0]["id"], False


def _insert_amendment_review(
    db: DatabaseGateway,
    new_filing_id: object,
    existing: Mapping[str, Any],
    extract: Mapping[str, Any],
) -> None:
    details = {
        "existing_filing_id": str(existing["id"]),
        "existing_irs_object_id": str(existing["irs_object_id"]),
        "new_irs_object_id": str(extract["irs_object_id"]),
    }
    db.execute(
        """
        INSERT INTO core.review_task (entity_type, entity_id, task_type, details)
        VALUES ('filing', %s, 'amendment_review', %s::jsonb)
        ON CONFLICT DO NOTHING
        """,
        (new_filing_id, json.dumps(details)),
    )


def _insert_facts(
    db: DatabaseGateway,
    run: IngestRun,
    filing_id: object,
    extract: Mapping[str, Any],
    form: str,
    concept_map: ConceptMap,
    normalization_version: int,
) -> None:
    for concept, result in _concepts(extract.get("concepts")).items():
        status = result.get("status")
        if status == "not_on_form":
            continue
        if status == "resolved":
            amount = result.get("value")
            if not _numeric(amount):
                raise ValueError(f"filing_extract {extract.get('id')} has invalid {concept} value")
        elif status == "absent":
            # Mirror cross_check._concept_value: an omitted optional line is zero.
            amount = 0
        else:
            raise ValueError(f"filing_extract {extract.get('id')} has invalid {concept} status {status!r}")
        source_path = result.get("xpath") or _first_candidate_xpath(concept_map, form, concept)
        rows = db.execute(
            """
            INSERT INTO core.financial_fact
                (filing_id, concept, normalization_version, amount, source_path, quality_state)
            VALUES (%s, %s, %s, %s, %s, 'verified')
            ON CONFLICT DO NOTHING
            RETURNING id
            """,
            (filing_id, concept, normalization_version, amount, source_path),
        )
        if rows:
            run.add_stat("facts_inserted")


def _insert_people(db: DatabaseGateway, run: IngestRun, filing_id: object, value: object) -> None:
    # Schema inspection is intentional: current schema has no natural-key
    # unique constraint, so select-first preserves INSERT-only idempotency.
    constraints = db.execute(
        """
        SELECT tc.constraint_name
        FROM information_schema.table_constraints AS tc
        WHERE tc.table_schema = 'core' AND tc.table_name = 'person_role'
          AND tc.constraint_type = 'UNIQUE'
        """
    )
    has_unique = bool(constraints)
    for person in _as_list(value):
        if not isinstance(person, Mapping):
            continue
        name = person.get("person_name", person.get("name"))
        if not isinstance(name, str) or not name:
            continue
        title = person.get("title")
        if title is not None and not isinstance(title, str):
            title = str(title)
        if not has_unique:
            duplicate = db.execute(
                """
                SELECT id FROM core.person_role
                WHERE filing_id = %s AND person_name = %s
                  AND title IS NOT DISTINCT FROM %s
                LIMIT 1
                """,
                (filing_id, name, title),
            )
            if duplicate:
                continue
        rows = db.execute(
            """
            INSERT INTO core.person_role
                (filing_id, person_name, title, reportable_compensation,
                 other_compensation, deferred_compensation, nontaxable_benefits,
                 related_organization_compensation, role_flags)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            RETURNING id
            """,
            (
                filing_id,
                name,
                title,
                person.get("reportable_compensation", person.get("comp")),
                person.get("other_compensation"),
                person.get("deferred_compensation"),
                person.get("nontaxable_benefits"),
                person.get("related_organization_compensation"),
                list(person.get("role_flags", [])),
            ),
        )
        if rows:
            run.add_stat("person_roles_inserted")


def _derive_metrics(
    db: DatabaseGateway,
    run: IngestRun,
    definitions: Sequence[Mapping[str, Any]],
    *,
    normalization_version: int,
    staged_statuses: Mapping[str, Mapping[str, Any]],
) -> None:
    rows = db.execute(
        """
        SELECT f.id AS filing_id, f.organization_id, f.irs_object_id,
               f.tax_year, f.tax_period_end AS fiscal_year_end,
               ff.id AS fact_id, ff.concept, ff.amount, ff.quality_state
        FROM core.filing AS f
        JOIN core.financial_fact AS ff ON ff.filing_id = f.id
        WHERE f.is_authoritative = true
          AND ff.normalization_version = %s
        ORDER BY f.organization_id, f.tax_period_end, ff.concept
        """,
        (normalization_version,),
    )
    facts: dict[tuple[object, object], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows:
        status = _concepts(staged_statuses.get(str(row["irs_object_id"]), {})).get(
            str(row["concept"]), {}
        ).get("status", "unknown")
        facts[(row["organization_id"], row["fiscal_year_end"])][str(row["concept"])] = {
            **row,
            "status": status,
        }

    for definition in definitions:
        key = str(definition["metric_key"])
        rule = _as_mapping(definition.get("eligibility_rule")) or {}
        if key == "revenue_cagr":
            _derive_cagr(db, run, definition, rule, facts)
            continue
        inputs = _FACT_INPUTS.get(key)
        if inputs is None:
            # Definitions are runtime product content; an unknown future formula
            # is never guessed or written by this version of the pipeline.
            continue
        for (organization_id, fiscal_year_end), year_facts in facts.items():
            required = [year_facts.get(concept) for concept in inputs]
            if any(fact is None for fact in required) or not _eligible(year_facts, rule):
                run.add_stat("suppressed_metrics")
                continue
            value = _metric_value(key, year_facts)
            input_ids = [fact["fact_id"] for fact in required if fact is not None]
            _insert_metric(
                db,
                run,
                definition,
                organization_id,
                _year_facts_tax_year(year_facts),
                fiscal_year_end,
                value,
                input_ids,
            )


def _derive_cagr(
    db: DatabaseGateway,
    run: IngestRun,
    definition: Mapping[str, Any],
    rule: Mapping[str, Any],
    facts: Mapping[tuple[object, object], Mapping[str, Mapping[str, Any]]],
) -> None:
    by_org: dict[object, list[tuple[object, Mapping[str, Any], Mapping[str, Mapping[str, Any]]]]] = defaultdict(list)
    for (organization_id, fiscal_year_end), year_facts in facts.items():
        revenue = year_facts.get("total_revenue")
        if revenue is not None:
            by_org[organization_id].append((fiscal_year_end, revenue, year_facts))
    minimum = int(rule.get("min_observations", 1))
    for organization_id, observations in by_org.items():
        observations.sort(key=lambda item: item[0])
        if len(observations) < minimum:
            run.add_stat("suppressed_metrics")
            continue
        earliest_end, earliest, _ = observations[0]
        latest_end, latest, latest_facts = observations[-1]
        years = _year(latest_end) - _year(earliest_end)
        if years <= 0 or _decimal(earliest["amount"]) <= 0 or _decimal(latest["amount"]) <= 0:
            run.add_stat("suppressed_metrics")
            continue
        value = Decimal(str(math.pow(float(_decimal(latest["amount"]) / _decimal(earliest["amount"])), 1 / years) - 1))
        _insert_metric(
            db,
            run,
            definition,
            organization_id,
            _year_facts_tax_year(latest_facts),
            latest_end,
            value,
            [earliest["fact_id"], latest["fact_id"]],
        )


def _eligible(facts: Mapping[str, Mapping[str, Any]], rule: Mapping[str, Any]) -> bool:
    for concept in _as_list(rule.get("requires_positive")):
        fact = facts.get(str(concept))
        if fact is None or _decimal(fact["amount"]) <= 0:
            return False
    for concept in _as_list(rule.get("requires_resolved")):
        fact = facts.get(str(concept))
        if fact is None or fact.get("status") != "resolved":
            return False
    return True


def _metric_value(key: str, facts: Mapping[str, Mapping[str, Any]]) -> Decimal:
    amount = lambda concept: _decimal(facts[concept]["amount"])
    if key == "operating_margin":
        return (amount("total_revenue") - amount("total_expenses")) / amount("total_revenue")
    if key == "contribution_dependency":
        return amount("contributions_grants") / amount("total_revenue")
    if key == "program_service_share":
        return amount("program_service_expense") / amount("total_revenue")
    if key == "compensation_intensity":
        return amount("salaries_benefits_total") / amount("total_expenses")
    if key == "membership_dues_share":
        return amount("membership_dues") / amount("total_revenue")
    raise ValueError(f"unsupported metric {key}")


def _insert_metric(
    db: DatabaseGateway,
    run: IngestRun,
    definition: Mapping[str, Any],
    organization_id: object,
    tax_year: int,
    fiscal_year_end: object,
    value: Decimal,
    input_fact_ids: list[object],
) -> None:
    rows = db.execute(
        """
        INSERT INTO core.metric_value
            (metric_key, metric_version, organization_id, tax_year,
             fiscal_year_end, value, quality_state, input_fact_ids)
        VALUES (%s, %s, %s, %s, %s, %s, 'derived', %s)
        ON CONFLICT DO NOTHING
        RETURNING id
        """,
        (
            definition["metric_key"],
            definition["version"],
            organization_id,
            tax_year,
            fiscal_year_end,
            value,
            input_fact_ids,
        ),
    )
    if rows:
        run.add_stat("metrics_inserted")


def _concepts(value: object) -> Mapping[str, Any]:
    document = _as_mapping(value) or {}
    nested = _as_mapping(document.get("concepts"))
    return nested if nested is not None else document


def _as_mapping(value: object) -> Mapping[str, Any] | None:
    if isinstance(value, Mapping):
        return value
    if isinstance(value, str):
        decoded = json.loads(value)
        return decoded if isinstance(decoded, Mapping) else None
    return None


def _as_list(value: object) -> list[Any]:
    if isinstance(value, str):
        value = json.loads(value)
    return list(value) if isinstance(value, Sequence) and not isinstance(value, str) else []


def _canonical_form(value: object) -> str | None:
    return {"IRS990": "990", "IRS990EZ": "990EZ"}.get(str(value))


def _precedence_key(row: Mapping[str, Any]) -> tuple[bool, str]:
    return bool(row.get("amended_return")), str(row.get("irs_object_id", ""))


def _first_candidate_xpath(concept_map: ConceptMap, form: str, concept: str) -> str:
    candidates = concept_map.candidates(form, concept)
    if not candidates:
        raise ValueError(f"{concept} has no {form} source candidate")
    candidate = candidates[0]
    if isinstance(candidate, str):
        return candidate
    paths = candidate.get("sum") or candidate.get("sub")
    return str(paths[0])


def _normalization_version(concept_map: ConceptMap) -> int:
    # The schema uses an integer while the map identifies itself as cm-YYYY.MM.N.
    # Its trailing revision is the schema-compatible value, derived from (not
    # duplicated alongside) the loaded concept map version.
    try:
        return int(concept_map.version.rsplit(".", 1)[1])
    except (IndexError, ValueError) as exc:
        raise ValueError(f"concept map version is not schema-compatible: {concept_map.version!r}") from exc


def _year(value: object) -> int:
    return int(str(value)[:4])


def _year_facts_tax_year(facts: Mapping[str, Mapping[str, Any]]) -> int:
    return int(next(iter(facts.values()))["tax_year"])


def _numeric(value: object) -> bool:
    return isinstance(value, (int, float, Decimal)) and not isinstance(value, bool)


def _decimal(value: object) -> Decimal:
    return Decimal(str(value))


def _summary(stats: Mapping[str, Any]) -> str:
    return ", ".join(f"{key}={stats.get(key, 0)}" for key in (
        "filings_inserted", "facts_inserted", "person_roles_inserted",
        "metrics_inserted", "suppressed_metrics", "skipped_unmapped", "amendment_reviews",
    ))


__all__ = ["derive"]
