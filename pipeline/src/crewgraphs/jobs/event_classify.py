"""Classify provider-raw regatta events with the versioned repository map."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Mapping
from typing import Any

import typer

from ..config import Settings
from ..db import DatabaseGateway, PostgresGateway
from ..event_map import EventClassification, EventMap, load_event_map
from ..runlog import IngestRun


UNMAPPED_TASK_TYPE = "event_classification_unmapped"
_PATTERN_FIELDS = ("event_code", "name", "boat_class_raw", "age_class_raw", "gender_raw")


def event_classify(db: DatabaseGateway, *, dry_run: bool = False, event_map: EventMap | None = None) -> str:
    """Insert current-map classifications for the latest revision of each regatta.

    This job never changes a prior classification. A mapping release yields a
    new ``mapping_version`` row, allowing latest-version reads to supersede
    prior normalizations without rewriting their evidence.
    """
    event_map = event_map or load_event_map()
    events = _latest_events(db, event_map.version)
    classified, unmapped = _classify_pending(events, event_map)
    coverage = _coverage(events, classified)
    if dry_run:
        return _summary(
            mapping_version=event_map.version,
            events_seen=len(events),
            events_classified=sum(1 for row in events if row.get("has_classification")) + len(classified),
            events_unmapped=len(unmapped),
            patterns_unmapped=len(_unmapped_patterns(unmapped)),
            coverage=coverage,
            dry_run=True,
        )

    with IngestRun(
        db,
        job_name="event_classify",
        source="results",
        params={"mapping_version": event_map.version},
    ) as run:
        for key, value in (
            ("events_seen", len(events)),
            ("events_classified", sum(1 for row in events if row.get("has_classification")) + len(classified)),
            ("events_unmapped", len(unmapped)),
            ("patterns_unmapped", len(_unmapped_patterns(unmapped))),
        ):
            run.add_stat(key, value)
        for source, percentage in coverage.items():
            run.add_stat(f"coverage_{source}_pct", percentage)

        for row, classification in classified:
            _insert_classification(db, str(row["id"]), event_map.version, classification)
        for (source, _pattern_key), rows in _unmapped_patterns(unmapped).items():
            pattern, first = rows[0]
            details = {
                "source": source,
                "pattern": pattern,
                "example_event_names": sorted({str(row["name"]) for _pattern, row in rows})[:5],
                "occurrence_count": len(rows),
            }
            if not _open_unmapped_task(db, source, pattern):
                _insert_review_task(db, str(first["id"]), details)
    return _summary(
        mapping_version=event_map.version,
        events_seen=len(events),
        events_classified=sum(1 for row in events if row.get("has_classification")) + len(classified),
        events_unmapped=len(unmapped),
        patterns_unmapped=len(_unmapped_patterns(unmapped)),
        coverage=coverage,
    )


def _latest_events(db: DatabaseGateway, mapping_version: str) -> list[dict[str, Any]]:
    """Read only events belonging to latest source/external-key revisions."""
    return db.execute(
        """
        WITH latest_regatta AS (
          SELECT DISTINCT ON (source, external_key) id, source
          FROM core.regatta
          ORDER BY source, external_key, revision DESC
        )
        SELECT event.id, regatta.source::text AS source, event.event_code,
               event.name, event.boat_class_raw, event.age_class_raw,
               event.gender_raw,
               classification.id IS NOT NULL AS has_classification
        FROM latest_regatta AS regatta
        JOIN core.regatta_event AS event ON event.regatta_id = regatta.id
        LEFT JOIN core.event_classification AS classification
          ON classification.event_id = event.id
         AND classification.mapping_version = %s
        ORDER BY regatta.source, event.id
        """,
        (mapping_version,),
    )


def _classify_pending(
    events: list[dict[str, Any]], event_map: EventMap
) -> tuple[list[tuple[dict[str, Any], EventClassification]], list[dict[str, Any]]]:
    classified: list[tuple[dict[str, Any], EventClassification]] = []
    unmapped: list[dict[str, Any]] = []
    for event in events:
        if event.get("has_classification"):
            continue
        classification = event_map.classify(event)
        if classification is None:
            unmapped.append(event)
        else:
            classified.append((event, classification))
    return classified, unmapped


def _insert_classification(
    db: DatabaseGateway, event_id: str, mapping_version: str, classification: EventClassification
) -> None:
    db.execute(
        """
        INSERT INTO core.event_classification
          (event_id, mapping_version, boat_class, age_bracket, gender, mapping_key)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (event_id, mapping_version) DO NOTHING
        """,
        (
            event_id,
            mapping_version,
            classification.boat_class,
            classification.age_bracket,
            classification.gender,
            classification.mapping_key,
        ),
    )


def _pattern(event: Mapping[str, Any]) -> dict[str, str | None]:
    return {field: _optional_text(event.get(field)) for field in _PATTERN_FIELDS}


def _optional_text(value: object) -> str | None:
    return None if value is None else str(value)


def _unmapped_patterns(
    events: list[dict[str, Any]],
) -> dict[tuple[str, str], list[tuple[dict[str, str | None], dict[str, Any]]]]:
    grouped: dict[tuple[str, str], list[tuple[dict[str, str | None], dict[str, Any]]]] = defaultdict(list)
    for event in events:
        source = str(event["source"])
        pattern = _pattern(event)
        grouped[(source, json.dumps(pattern, sort_keys=True))].append((pattern, event))
    return grouped


def _coverage(
    events: list[dict[str, Any]], classified: list[tuple[dict[str, Any], EventClassification]]
) -> dict[str, float]:
    totals: dict[str, int] = defaultdict(int)
    covered: dict[str, int] = defaultdict(int)
    for event in events:
        totals[str(event["source"])] += 1
        if event.get("has_classification"):
            covered[str(event["source"])] += 1
    for event, _classification in classified:
        covered[str(event["source"])] += 1
    return {source: round(100 * covered[source] / total, 2) for source, total in sorted(totals.items())}


def _open_unmapped_task(db: DatabaseGateway, source: str, pattern: Mapping[str, str | None]) -> bool:
    rows = db.execute(
        """
        SELECT 1 FROM core.review_task
        WHERE entity_type = 'regatta_event_pattern'
          AND task_type = %s AND status = 'open'
          AND details->>'source' = %s
          AND details->'pattern' = %s::jsonb
        LIMIT 1
        """,
        (UNMAPPED_TASK_TYPE, source, json.dumps(pattern, sort_keys=True)),
    )
    return bool(rows)


def _insert_review_task(db: DatabaseGateway, event_id: str, details: Mapping[str, object]) -> None:
    db.execute(
        """
        INSERT INTO core.review_task (entity_type, entity_id, task_type, details)
        VALUES ('regatta_event_pattern', %s, %s, %s::jsonb)
        """,
        (event_id, UNMAPPED_TASK_TYPE, json.dumps(details, sort_keys=True)),
    )


def _summary(
    *,
    mapping_version: str,
    events_seen: int,
    events_classified: int,
    events_unmapped: int,
    patterns_unmapped: int,
    coverage: Mapping[str, float],
    dry_run: bool = False,
) -> str:
    lines = [
        f"event-classify{' dry-run' if dry_run else ''}: mapping_version={mapping_version}",
        f"events_seen={events_seen} events_classified={events_classified} "
        f"events_unmapped={events_unmapped} patterns_unmapped={patterns_unmapped}",
        "source coverage:",
    ]
    lines.extend(f"  {source}: {percentage:.2f}%" for source, percentage in coverage.items())
    return "\n".join(lines)


def register(app: typer.Typer) -> None:
    """Attach the db-only canonical event classification command."""

    @app.command(name="event-classify")
    def event_classify_cmd(
        dry_run: bool = typer.Option(False, "--dry-run", help="Print coverage without writing classifications or tasks"),
    ) -> None:
        settings = Settings.from_env()
        gateway = PostgresGateway(settings.database_url)
        try:
            typer.echo(event_classify(gateway, dry_run=dry_run))
        finally:
            gateway.close()


__all__ = ["UNMAPPED_TASK_TYPE", "event_classify", "register"]
