"""Derive strictly gated seasonal program ratings from complete ranked fields.

Ratings live in ``core.program_rating``, not ``core.metric_value``: the latter
cannot represent more than one program dimension per organization and year.
For any future compatibility projection, season maps to ``tax_year = season``
and ``fiscal_year_end = season-12-31``.

Provider-club programs are the model competitors, including clubs with no
organization identity.  Only after fitting do curator-linked provider clubs
attach aggregate ratings to organizations.  No person data is read or stored.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import typer

from ..config import Settings
from ..db import DatabaseGateway, PostgresGateway
from ..runlog import IngestRun
from ..summary import render_summary


METRIC_KEY = "rating_rof"
METRIC_VERSION = 1
DEFAULT_COMPUTATION_VERSION = "pl-mm-2026.07.1"
MM_TOLERANCE = 1e-6
MM_MAX_ITERATIONS = 200
# Gamma(shape=1.1, rate=0.1) MAP prior: +0.1 in each update numerator
# and denominator.  It is intentionally weak but keeps winless/undefeated
# provider programs finite and gives disconnected comparison components a
# common, explicit anchor.
PRIOR_PSEUDOCOUNT = 0.1

_EXCLUDED_STATUS_TOKENS = frozenset(
    {
        "DNS",
        "DIDNOTSTART",
        "DNF",
        "DIDNOTFINISH",
        "DSQ",
        "DQ",
        "DISQUALIFIED",
        "WITHDRAWN",
        "WITHDRAW",
        "WD",
        "SCRATCH",
        "SCRATCHED",
        "EXCLUDED",
    }
)


@dataclass(frozen=True)
class RankedField:
    """One event-level finish order used as a Plackett-Luce observation."""

    event_id: str
    regatta_key: str
    season: int
    boat_class: str
    age_bracket: str
    gender: str
    # Mapping versions are strings like "2026.07.2" (the event-map file
    # version), not integers. NOTE: latest-version selection uses SQL
    # max(text), which orders correctly only while patch numbers stay
    # single-digit — bump to zero-padded patches before a ".10" release.
    mapping_version: str
    mapping_key: str
    ranking: tuple[str, ...]
    used_adjusted_time: bool


@dataclass(frozen=True)
class PlackettLuceFit:
    """Pure-math fit output; strengths are positive but otherwise arbitrary."""

    strengths: dict[str, float]
    iterations: int
    converged: bool


@dataclass(frozen=True)
class _RankEventResult:
    order: tuple[tuple[str, ...], bool] | None
    rows_excluded_ooc: int
    rows_excluded_status: int


@dataclass(frozen=True)
class _RankedFieldsResult:
    fields: tuple[RankedField, ...]
    rows_excluded_ooc: int
    rows_excluded_status: int
    fields_skipped_incomplete_order: int


def fit_plackett_luce(
    rankings: Sequence[Sequence[str]],
    *,
    tolerance: float = MM_TOLERANCE,
    max_iterations: int = MM_MAX_ITERATIONS,
    prior_pseudocount: float = PRIOR_PSEUDOCOUNT,
) -> PlackettLuceFit:
    """Fit full-ranking Plackett-Luce strengths with Hunter-style MM updates.

    At every choice stage, the observed winner contributes one numerator
    count and every program still at risk contributes reciprocal current field
    strength to its denominator.  A Gamma(1.1, 0.1) MAP prior supplies the
    default ``+0.1`` smoothing in both terms.

    Worked two-program example: if A beats B three times and B beats A once,
    their fitted strength ratio is ``(3 + .1) / (1 + .1) = 2.81818``.  The
    display-scale gap is therefore ``400 * log10(2.81818) = 179.98`` points.
    With zero B wins the finite smoothed ratio is 31 rather than infinity.
    """
    if tolerance <= 0:
        raise ValueError("tolerance must be positive")
    if max_iterations < 0:
        raise ValueError("max_iterations cannot be negative")
    if prior_pseudocount <= 0:
        raise ValueError("prior_pseudocount must be positive")

    normalized: list[tuple[str, ...]] = []
    for ranking in rankings:
        ordered = tuple(str(competitor) for competitor in ranking)
        if len(ordered) < 2:
            raise ValueError("every ranked field must contain at least two competitors")
        if len(set(ordered)) != len(ordered):
            raise ValueError("a competitor may appear only once in a ranked field")
        normalized.append(ordered)
    if not normalized:
        return PlackettLuceFit({}, 0, True)

    competitors = sorted(
        {competitor for ranking in normalized for competitor in ranking}
    )
    strengths = {competitor: 1.0 for competitor in competitors}
    wins = {competitor: 0 for competitor in competitors}
    for ranking in normalized:
        for competitor in ranking[:-1]:
            wins[competitor] += 1

    for iteration in range(1, max_iterations + 1):
        exposure = {competitor: prior_pseudocount for competitor in competitors}
        for ranking in normalized:
            suffix_strength = sum(strengths[competitor] for competitor in ranking)
            cumulative_exposure = 0.0
            # The last remaining competitor is chosen with probability one, so
            # the likelihood and MM denominator stop one stage before it.
            for position, competitor in enumerate(ranking):
                if position < len(ranking) - 1:
                    cumulative_exposure += 1.0 / suffix_strength
                exposure[competitor] += cumulative_exposure
                suffix_strength -= strengths[competitor]

        updated = {
            competitor: (wins[competitor] + prior_pseudocount) / exposure[competitor]
            for competitor in competitors
        }
        if any(value <= 0 or not math.isfinite(value) for value in updated.values()):
            return PlackettLuceFit(strengths, iteration, False)
        delta = max(
            abs(math.log(updated[competitor] / strengths[competitor]))
            for competitor in competitors
        )
        strengths = updated
        if delta < tolerance:
            return PlackettLuceFit(strengths, iteration, True)
    return PlackettLuceFit(strengths, max_iterations, False)


def rank_event_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    min_field_size: int,
) -> tuple[tuple[str, ...], bool] | None:
    """Return a deterministic provider-club order and adjusted-time flag.

    OOC rows and known non-finishing statuses (scratch, DNS/DNF/DSQ,
    withdrawn, excluded, disqualified, and variants) are excluded even if a
    provider left a stale place or time.  Time-Team's opaque integer status
    vocabulary is not decoded, so an unknown integer status is retained when
    the row has a usable position or time.  For masters, adjusted time is used
    only when every retained row has it; otherwise only rows with a raw signal
    participate.  Multiple crews from the same provider club collapse to that
    program's best finish in the field.
    """
    return _rank_event_rows(rows, min_field_size=min_field_size).order


def _rank_event_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    min_field_size: int,
) -> _RankEventResult:
    if min_field_size < 2:
        raise ValueError("min_field_size must be at least two")
    provider_rows = [row for row in rows if row.get("provider_club_id") is not None]
    non_ooc = [row for row in provider_rows if not _is_ooc(row)]
    rows_excluded_ooc = len(provider_rows) - len(non_ooc)
    retained = [row for row in non_ooc if not _excluded_status(row.get("status"))]
    rows_excluded_status = len(non_ooc) - len(retained)

    masters = bool(retained) and (
        str(retained[0].get("age_bracket") or "").casefold() == "masters"
    )
    use_adjusted_time = (
        masters
        and len(retained) >= min_field_size
        and all(_positive_number(row.get("adjusted_time_ms")) for row in retained)
    )
    # A partial adjusted-time field must fall all the way back to raw ordering.
    # Adjusted-only rows are omitted rather than receiving an artificial
    # infinity key and an invented last place.
    usable = (
        retained
        if use_adjusted_time
        else [row for row in retained if _has_raw_order_signal(row)]
    )

    def order_key(row: Mapping[str, Any]) -> tuple[object, ...]:
        stable = (
            str(row.get("provider_club_id")),
            str(row.get("entry_id") or row.get("entry_external_key") or ""),
        )
        if use_adjusted_time:
            return (
                _number(row.get("adjusted_time_ms")),
                _number(row.get("adjusted_position"), math.inf),
                *stable,
            )
        position = row.get("position")
        if _positive_number(position):
            return (
                0,
                _number(position),
                _number(row.get("time_ms"), math.inf),
                *stable,
            )
        return (1, _number(row.get("time_ms"), math.inf), math.inf, *stable)

    ordered = sorted(usable, key=order_key)
    ranking: list[str] = []
    seen: set[str] = set()
    for row in ordered:
        provider_club_id = str(row["provider_club_id"])
        if provider_club_id not in seen:
            ranking.append(provider_club_id)
            seen.add(provider_club_id)
    if len(ranking) < min_field_size:
        order = None
    else:
        order = (tuple(ranking), use_adjusted_time)
    return _RankEventResult(
        order=order,
        rows_excluded_ooc=rows_excluded_ooc,
        rows_excluded_status=rows_excluded_status,
    )


def eligibility_met(
    *,
    ranked_fields: int,
    distinct_regattas: int,
    field_sizes: Sequence[int],
    rule: Mapping[str, Any],
) -> bool:
    """Evaluate every published rating-eligibility threshold explicitly."""
    min_ranked_fields = _positive_rule_int(rule, "min_ranked_fields")
    min_distinct_regattas = _positive_rule_int(rule, "min_distinct_regattas")
    min_field_size = _positive_rule_int(rule, "min_field_size")
    return (
        ranked_fields >= min_ranked_fields
        and distinct_regattas >= min_distinct_regattas
        and bool(field_sizes)
        and min(field_sizes) >= min_field_size
    )


def derive_ratings(
    db: DatabaseGateway,
    *,
    season: int | None = None,
    computation_version: str = DEFAULT_COMPUTATION_VERSION,
    dry_run: bool = False,
) -> str:
    """Compute all linked program ratings and persist insert-only outputs."""
    if season is not None and not 1800 <= season <= 9999:
        raise ValueError("season must be between 1800 and 9999")
    if not computation_version.strip():
        raise ValueError("computation_version cannot be blank")

    coverage: list[dict[str, Any]] = []
    with IngestRun(
        db,
        job_name="derive_ratings",
        source="results",
        code_version=computation_version,
        params={
            "season": season,
            "computation_version": computation_version,
            "dry_run": dry_run,
        },
    ) as run:
        for stat in (
            "fields_ranked",
            "fields_skipped_incomplete_order",
            "rows_excluded_ooc",
            "rows_excluded_status",
            "programs_rated",
            "programs_eligible",
            "orgs_linked_rated",
            "convergence_iterations_max",
            "convergence_failures",
        ):
            run.add_stat(stat, 0)

        definition = _rating_definition(db)
        rule = _json_mapping(definition["eligibility_rule"])
        min_field_size = _positive_rule_int(rule, "min_field_size")
        ranked_fields_result = _ranked_fields(
            _result_rows(db, season=season), min_field_size
        )
        fields = ranked_fields_result.fields
        run.add_stat("fields_ranked", len(fields))
        run.add_stat(
            "fields_skipped_incomplete_order",
            ranked_fields_result.fields_skipped_incomplete_order,
        )
        run.add_stat("rows_excluded_ooc", ranked_fields_result.rows_excluded_ooc)
        run.add_stat("rows_excluded_status", ranked_fields_result.rows_excluded_status)
        links = _linked_organizations(db)

        grouped: dict[tuple[int, str, str, str], list[RankedField]] = defaultdict(list)
        for field in fields:
            grouped[
                (field.season, field.boat_class, field.age_bracket, field.gender)
            ].append(field)

        maximum_iterations = 0
        organizations_rated: set[str] = set()
        for dimensions in sorted(grouped):
            dimension_fields = sorted(
                grouped[dimensions], key=lambda field: field.event_id
            )
            fit = fit_plackett_luce(
                [field.ranking for field in dimension_fields],
                tolerance=MM_TOLERANCE,
                max_iterations=MM_MAX_ITERATIONS,
                prior_pseudocount=PRIOR_PSEUDOCOUNT,
            )
            maximum_iterations = max(maximum_iterations, fit.iterations)
            provider_count = len(fit.strengths)
            if not fit.converged:
                run.add_stat("convergence_failures")
                run.warn(
                    "Plackett-Luce MM did not converge for "
                    f"{dimensions[0]}/{dimensions[1]}/{dimensions[2]}/{dimensions[3]}"
                )
                if not dry_run:
                    _open_convergence_review(
                        db,
                        dimensions=dimensions,
                        fields=dimension_fields,
                        computation_version=computation_version,
                        iterations=fit.iterations,
                    )
                coverage.append(
                    _coverage_row(
                        dimensions,
                        dimension_fields,
                        provider_programs=provider_count,
                        linked_programs=0,
                        eligible_programs=0,
                        converged=False,
                    )
                )
                continue

            display_ratings = _display_ratings(fit.strengths)
            program_rows = _organization_program_rows(
                dimensions=dimensions,
                fields=dimension_fields,
                display_ratings=display_ratings,
                links=links,
                rule=rule,
                definition=definition,
                computation_version=computation_version,
                convergence_iterations=fit.iterations,
            )
            eligible_count = sum(bool(row["eligibility_met"]) for row in program_rows)
            coverage.append(
                _coverage_row(
                    dimensions,
                    dimension_fields,
                    provider_programs=provider_count,
                    linked_programs=len(program_rows),
                    eligible_programs=eligible_count,
                    converged=True,
                )
            )
            run.add_stat("programs_rated", len(program_rows))
            run.add_stat("programs_eligible", eligible_count)
            organizations_rated.update(
                str(row["organization_id"]) for row in program_rows
            )
            if not dry_run:
                for row in program_rows:
                    _insert_program_rating(db, row)

        run.add_stat("orgs_linked_rated", len(organizations_rated))
        run.add_stat("convergence_iterations_max", maximum_iterations)

    stats = run.stats
    warnings = stats.pop("warnings", [])
    summary = render_summary(
        job_name="derive_ratings",
        run_id=run.id or "",
        status="succeeded",
        counts=stats,
        warnings=warnings,
    )
    if dry_run:
        summary += _coverage_table(coverage)
    return summary


def _rating_definition(db: DatabaseGateway) -> dict[str, Any]:
    rows = db.execute(
        """
        SELECT metric_key, version, eligibility_rule, status
        FROM core.metric_definition
        WHERE metric_key = %s AND version = %s
        """,
        (METRIC_KEY, METRIC_VERSION),
    )
    if len(rows) != 1:
        raise RuntimeError(
            f"{METRIC_KEY} v{METRIC_VERSION} definition is missing or ambiguous"
        )
    return rows[0]


def _result_rows(
    db: DatabaseGateway,
    *,
    season: int | None,
) -> list[dict[str, Any]]:
    season_filter = (
        "AND EXTRACT(YEAR FROM latest.start_date)::integer = %s"
        if season is not None
        else ""
    )
    return db.execute(
        f"""
        WITH latest_regatta AS MATERIALIZED (
            SELECT DISTINCT ON (regatta.source, regatta.external_key)
                   regatta.id, regatta.source, regatta.external_key,
                   regatta.start_date
            FROM core.regatta AS regatta
            WHERE regatta.start_date IS NOT NULL
            ORDER BY regatta.source, regatta.external_key,
                     regatta.revision DESC, regatta.id
        ), latest_mapping AS MATERIALIZED (
            SELECT max(mapping_version) AS mapping_version
            FROM core.event_classification
        ), current_classification AS MATERIALIZED (
            SELECT classification.event_id, classification.mapping_version,
                   classification.boat_class, classification.age_bracket,
                   classification.gender, classification.mapping_key
            FROM core.event_classification AS classification
            JOIN latest_mapping
              ON latest_mapping.mapping_version = classification.mapping_version
        )
        SELECT event.id AS event_id,
               event.external_key AS event_external_key,
               entry.id AS entry_id,
               entry.external_key AS entry_external_key,
               entry.provider_club_id,
               entry.raw AS entry_raw,
               result.status, result.position, result.adjusted_position,
               result.time_ms, result.adjusted_time_ms,
               latest.source::text AS source,
               latest.external_key AS regatta_external_key,
               EXTRACT(YEAR FROM latest.start_date)::integer AS season,
               classification.mapping_version,
               classification.boat_class,
               classification.age_bracket,
               classification.gender,
               classification.mapping_key
        FROM latest_regatta AS latest
        JOIN core.regatta_event AS event ON event.regatta_id = latest.id
        JOIN current_classification AS classification
          ON classification.event_id = event.id
        JOIN core.regatta_entry AS entry ON entry.event_id = event.id
        JOIN core.regatta_result AS result ON result.entry_id = entry.id
        WHERE entry.provider_club_id IS NOT NULL
          {season_filter}
        ORDER BY latest.source, latest.external_key, event.external_key,
                 entry.external_key, entry.id
        """,
        (season,) if season is not None else (),
    )


def _linked_organizations(db: DatabaseGateway) -> dict[str, str]:
    rows = db.execute(
        """
        WITH link_candidates AS MATERIALIZED (
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
            SELECT provider_club_id
            FROM link_candidates
            GROUP BY provider_club_id
            HAVING count(DISTINCT organization_id) = 1
        )
        SELECT DISTINCT candidate.provider_club_id, candidate.organization_id
        FROM link_candidates AS candidate
        JOIN unambiguous_provider_clubs AS unambiguous
          ON unambiguous.provider_club_id = candidate.provider_club_id
        ORDER BY candidate.provider_club_id, candidate.organization_id
        """
    )
    return {str(row["provider_club_id"]): str(row["organization_id"]) for row in rows}


def _ranked_fields(
    rows: Sequence[Mapping[str, Any]],
    min_field_size: int,
) -> _RankedFieldsResult:
    by_event: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        by_event[str(row["event_id"])].append(row)

    fields: list[RankedField] = []
    rows_excluded_ooc = 0
    rows_excluded_status = 0
    fields_skipped_incomplete_order = 0
    for event_id in sorted(by_event):
        event_rows = by_event[event_id]
        result = _rank_event_rows(event_rows, min_field_size=min_field_size)
        rows_excluded_ooc += result.rows_excluded_ooc
        rows_excluded_status += result.rows_excluded_status
        if result.order is None:
            fields_skipped_incomplete_order += 1
            continue
        ranking, used_adjusted_time = result.order
        first = event_rows[0]
        fields.append(
            RankedField(
                event_id=event_id,
                regatta_key=f"{first['source']}:{first['regatta_external_key']}",
                season=int(first["season"]),
                boat_class=str(first["boat_class"]),
                age_bracket=str(first["age_bracket"]),
                gender=str(first["gender"]),
                mapping_version=str(first["mapping_version"]),
                mapping_key=str(first["mapping_key"]),
                ranking=ranking,
                used_adjusted_time=used_adjusted_time,
            )
        )
    return _RankedFieldsResult(
        fields=tuple(fields),
        rows_excluded_ooc=rows_excluded_ooc,
        rows_excluded_status=rows_excluded_status,
        fields_skipped_incomplete_order=fields_skipped_incomplete_order,
    )


def _display_ratings(strengths: Mapping[str, float]) -> dict[str, float]:
    if not strengths:
        return {}
    geometric_mean = math.exp(
        sum(math.log(strength) for strength in strengths.values()) / len(strengths)
    )
    return {
        competitor: 1500.0 + 400.0 * math.log10(strength / geometric_mean)
        for competitor, strength in strengths.items()
    }


def _organization_program_rows(
    *,
    dimensions: tuple[int, str, str, str],
    fields: Sequence[RankedField],
    display_ratings: Mapping[str, float],
    links: Mapping[str, str],
    rule: Mapping[str, Any],
    definition: Mapping[str, Any],
    computation_version: str,
    convergence_iterations: int,
) -> list[dict[str, Any]]:
    appearances: dict[str, list[RankedField]] = defaultdict(list)
    for field in fields:
        for competitor in field.ranking:
            appearances[competitor].append(field)

    clubs_by_org: dict[str, list[str]] = defaultdict(list)
    for competitor in sorted(display_ratings):
        organization_id = links.get(competitor)
        if organization_id is not None:
            clubs_by_org[organization_id].append(competitor)

    season, boat_class, age_bracket, gender = dimensions
    rows: list[dict[str, Any]] = []
    for organization_id in sorted(clubs_by_org):
        provider_clubs = clubs_by_org[organization_id]
        fields_by_id = {
            field.event_id: field
            for competitor in provider_clubs
            for field in appearances[competitor]
        }
        ordered_fields = [fields_by_id[key] for key in sorted(fields_by_id)]
        field_sizes = sorted(len(field.ranking) for field in ordered_fields)
        ranked_fields = len(ordered_fields)
        distinct_regattas = len({field.regatta_key for field in ordered_fields})
        total_appearances = sum(
            len(appearances[competitor]) for competitor in provider_clubs
        )
        rating = (
            sum(
                display_ratings[competitor] * len(appearances[competitor])
                for competitor in provider_clubs
            )
            / total_appearances
        )
        is_eligible = eligibility_met(
            ranked_fields=ranked_fields,
            distinct_regattas=distinct_regattas,
            field_sizes=field_sizes,
            rule=rule,
        )
        input_summary = {
            "adjusted_time_fields": sum(
                field.used_adjusted_time for field in ordered_fields
            ),
            "comparison_pool_provider_programs": len(display_ratings),
            "convergence_iterations": convergence_iterations,
            "event_ids": [field.event_id for field in ordered_fields],
            "method": "appearance_weighted_mean",
            "mapping_keys": sorted({field.mapping_key for field in ordered_fields}),
            "mapping_versions": sorted(
                {field.mapping_version for field in ordered_fields}
            ),
            "linked_provider_aggregation": (
                "appearance-weighted mean display rating; "
                "coverage counts distinct event ids"
            ),
            "model": "plackett_luce_mm",
            "prior": {"gamma_rate": 0.1, "gamma_shape": 1.1},
            "provider_club_ids": provider_clubs,
            "regatta_keys": sorted({field.regatta_key for field in ordered_fields}),
            "scale": "1500 + 400 * log10(strength / geometric_mean_strength)",
            "self_competition": any(
                sum(competitor in field.ranking for competitor in provider_clubs) > 1
                for field in ordered_fields
            ),
            "max_iterations": MM_MAX_ITERATIONS,
            "tolerance": MM_TOLERANCE,
        }
        rows.append(
            {
                "organization_id": organization_id,
                "season": season,
                "boat_class": boat_class,
                "age_bracket": age_bracket,
                "gender": gender,
                "metric_key": str(definition["metric_key"]),
                "metric_version": int(definition["version"]),
                "rating": _six_places(rating),
                "rating_sigma": _six_places(1.0 / math.sqrt(ranked_fields)),
                "ranked_fields": ranked_fields,
                "distinct_regattas": distinct_regattas,
                "field_sizes": field_sizes,
                "computation_version": computation_version,
                "eligibility_met": is_eligible,
                "input_summary": input_summary,
            }
        )
    return rows


def _insert_program_rating(db: DatabaseGateway, row: Mapping[str, Any]) -> None:
    db.execute(
        """
        INSERT INTO core.program_rating
            (organization_id, season, boat_class, age_bracket, gender,
             metric_key, metric_version, rating, rating_sigma, ranked_fields,
             distinct_regattas, field_sizes, computation_version,
             eligibility_met, input_summary)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s::jsonb, %s, %s, %s::jsonb)
        ON CONFLICT DO NOTHING
        RETURNING id
        """,
        (
            row["organization_id"],
            row["season"],
            row["boat_class"],
            row["age_bracket"],
            row["gender"],
            row["metric_key"],
            row["metric_version"],
            row["rating"],
            row["rating_sigma"],
            row["ranked_fields"],
            row["distinct_regattas"],
            json.dumps(row["field_sizes"], separators=(",", ":")),
            row["computation_version"],
            row["eligibility_met"],
            json.dumps(row["input_summary"], sort_keys=True, separators=(",", ":")),
        ),
    )


def _open_convergence_review(
    db: DatabaseGateway,
    *,
    dimensions: tuple[int, str, str, str],
    fields: Sequence[RankedField],
    computation_version: str,
    iterations: int,
) -> None:
    anchor_event_id = fields[0].event_id
    fingerprint_payload = {
        "age_bracket": dimensions[2],
        "boat_class": dimensions[1],
        "computation_version": computation_version,
        "event_ids": [field.event_id for field in fields],
        "gender": dimensions[3],
        "iterations": iterations,
        "season": dimensions[0],
    }
    fingerprint = hashlib.sha256(
        json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    details = {**fingerprint_payload, "fingerprint": fingerprint}
    encoded = json.dumps(details, sort_keys=True, separators=(",", ":"))
    # review_task has no usable uniqueness constraint.  Keeping the guard in
    # this single INSERT removes the ordinary check/insert window, although two
    # concurrent transactions can still race under PostgreSQL MVCC.
    db.execute(
        """
        INSERT INTO core.review_task
            (entity_type, entity_id, task_type, details)
        SELECT 'regatta_event', %s, 'rating_convergence', %s::jsonb
        WHERE NOT EXISTS (
            SELECT 1
            FROM core.review_task
            WHERE entity_type = 'regatta_event'
              AND entity_id = %s
              AND task_type = 'rating_convergence'
              AND status = 'open'
              AND details ->> 'fingerprint' = %s
        )
        """,
        (anchor_event_id, encoded, anchor_event_id, fingerprint),
    )


def _coverage_row(
    dimensions: tuple[int, str, str, str],
    fields: Sequence[RankedField],
    *,
    provider_programs: int,
    linked_programs: int,
    eligible_programs: int,
    converged: bool,
) -> dict[str, Any]:
    return {
        "season": dimensions[0],
        "boat_class": dimensions[1],
        "age_bracket": dimensions[2],
        "gender": dimensions[3],
        "fields": len(fields),
        "provider_programs": provider_programs,
        "linked_programs": linked_programs,
        "eligible_programs": eligible_programs,
        "converged": converged,
    }


def _coverage_table(rows: Sequence[Mapping[str, Any]]) -> str:
    lines = [
        "\n### Dry-run coverage",
        "",
        "| Season | Boat | Age | Gender | Fields | Provider programs | Linked | Eligible | Converged |",
        "| ---: | :--- | :--- | :--- | ---: | ---: | ---: | ---: | :---: |",
    ]
    lines.extend(
        "| {season} | {boat_class} | {age_bracket} | {gender} | {fields} | "
        "{provider_programs} | {linked_programs} | {eligible_programs} | {converged} |".format(
            **row
        )
        for row in rows
    )
    if not rows:
        lines.append("| — | — | — | — | 0 | 0 | 0 | 0 | yes |")
    return "\n".join(lines) + "\n"


def _excluded_status(value: object) -> bool:
    token = re.sub(r"[^A-Z0-9]+", "", str(value or "").upper())
    return token in _EXCLUDED_STATUS_TOKENS or token.startswith(
        (
            "DNS",
            "DIDNOTSTART",
            "DNF",
            "DIDNOTFINISH",
            "DSQ",
            "DISQUAL",
            "WITHDRAW",
            "WITHDREW",
            "SCRATCH",
            "SCRATCHED",
            "EXCLUS",
        )
    )


def _is_ooc(row: Mapping[str, Any]) -> bool:
    raw = row.get("entry_raw")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return False
    if not isinstance(raw, Mapping):
        return False
    value = raw.get("is_ooc")
    return value is True or (
        isinstance(value, str) and value.strip().casefold() == "true"
    )


def _has_raw_order_signal(row: Mapping[str, Any]) -> bool:
    return _positive_number(row.get("position")) or _positive_number(row.get("time_ms"))


def _positive_number(value: object) -> bool:
    try:
        return float(value) > 0
    except (TypeError, ValueError, OverflowError):
        return False


def _number(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError, OverflowError):
        return default


def _positive_rule_int(rule: Mapping[str, Any], key: str) -> int:
    value = rule.get(key)
    if isinstance(value, bool):
        raise ValueError(
            f"{METRIC_KEY} eligibility rule {key} must be a positive integer"
        )
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ValueError(
            f"{METRIC_KEY} eligibility rule {key} must be a positive integer"
        ) from None
    if parsed <= 0 or parsed != value:
        raise ValueError(
            f"{METRIC_KEY} eligibility rule {key} must be a positive integer"
        )
    return parsed


def _json_mapping(value: object) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if isinstance(value, str):
        parsed = json.loads(value)
        if isinstance(parsed, Mapping):
            return parsed
    raise ValueError(f"{METRIC_KEY} eligibility_rule must be a JSON object")


def _six_places(value: float) -> Decimal:
    return Decimal(f"{value:.6f}")


def register(app: typer.Typer) -> None:
    """Attach the Wave-3b ratings command without changing the CLI root."""

    @app.command(name="derive-ratings")
    def derive_ratings_cmd(
        season: int | None = typer.Option(
            None, "--season", help="Optional calendar season to recompute"
        ),
        computation_version: str = typer.Option(
            DEFAULT_COMPUTATION_VERSION,
            "--computation-version",
            help="Insert-only analytical supersede identifier",
        ),
        dry_run: bool = typer.Option(
            False,
            "--dry-run",
            help="Report dimension coverage without writing program ratings or reviews",
        ),
    ) -> None:
        settings = Settings.from_env()
        gateway = PostgresGateway(settings.database_url)
        try:
            typer.echo(
                derive_ratings(
                    gateway,
                    season=season,
                    computation_version=computation_version,
                    dry_run=dry_run,
                )
            )
        finally:
            gateway.close()


__all__ = [
    "DEFAULT_COMPUTATION_VERSION",
    "PlackettLuceFit",
    "RankedField",
    "derive_ratings",
    "eligibility_met",
    "fit_plackett_luce",
    "rank_event_rows",
    "register",
]
