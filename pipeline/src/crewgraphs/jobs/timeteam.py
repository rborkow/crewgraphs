"""Acquire, stage, and load USRowing's Time-Team results API.

The provider exposes two useful documents: a regatta schedule and one detail
document per race.  This adapter keeps both documents immutable in R2, then
loads a fresh result tree only when their canonical combined checksum changes.

The live payloads expose only ``entry.stroke_fullname`` (no per-seat roster
array in the verified 1x and 8+ captures). That name is written only to
``core.result_person``. In particular, the ambiguous provider ``entry.string``
is never persisted: it is an athlete name for 1x entries and a crew label for
some larger boats.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING, Any, Iterable, Mapping
from urllib.parse import urlencode
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import typer
from lxml import html

from ..db import DatabaseGateway
from ..quarantine import quarantine
from ..raw_store import QuarantineableError, RawStore, register_source_record
from ..runlog import IngestRun
from crewgraphs.runtime import job_context, split_csv

if TYPE_CHECKING:
    import httpx


SOURCE = "time_team"
PARSER_VERSION = "timeteam-2026.07.1"
INDEX_URL = "https://usrowing.regatta.time-team.com/"
API_BASE_URL = "https://api.usrowing.regatta.time-team.com/api/1"
KNOWN_STATUS_INTS = frozenset(range(0, 13))


def timeteam_regatta_index(
    db: DatabaseGateway,
    store: RawStore,
    http: "httpx.Client",
    *,
    years: Iterable[int],
    slugs: Iterable[str] | None = None,
    retrieved_date: str | None = None,
) -> str:
    """Discover available ``(slug, year)`` pairs from server-rendered cards.

    The index's selector is a ``year`` query parameter.  We snapshot the HTML
    used for each requested selector value even if the server returns a shared
    bootstrap payload containing more than one year.  Discovery deliberately
    reads the cards' hrefs: the real ``__NEXT_DATA__`` payload is not a stable
    regatta-list interface.
    """
    requested_years = sorted(set(int(year) for year in years))
    requested_slugs = set(slugs or ())
    capture_date = retrieved_date or date.today().isoformat()
    with IngestRun(
        db,
        job_name="timeteam_regatta_index",
        source=SOURCE,
        params={"years": requested_years, "slugs": sorted(requested_slugs)},
    ) as run:
        for stat in ("regatta_years_seen", "quarantines"):
            run.add_stat(stat, 0)
        for index, year in enumerate(requested_years):
            if index:
                _sleep(300)
            url = _index_url(year)
            raw_key: str | None = None
            try:
                response = http.get(url)
                response.raise_for_status()
                content = response.content
                raw_key = f"raw/timeteam/usrowing/index/{year}/{capture_date}.html"
                raw_object = store.put_raw(raw_key, content, "text/html")
                source_record_id = register_source_record(
                    db,
                    source=SOURCE,
                    external_key=f"index/{year}",
                    raw_object=raw_object,
                    metadata={"url": url, "retrieved_date": capture_date, "year": year},
                )
                pairs = _regatta_pairs_from_html(content, year)
                if requested_slugs:
                    pairs = [(slug, pair_year) for slug, pair_year in pairs if slug in requested_slugs]
                    # A manual slug is intentionally useful even when the
                    # provider has not rendered a card for a past year.
                    pairs.extend((slug, year) for slug in requested_slugs if (slug, year) not in pairs)
                for slug, pair_year in sorted(set(pairs)):
                    _upsert_staged_regatta(
                        db,
                        run_id=run.id or "",
                        source_record_id=source_record_id,
                        slug=slug,
                        year=pair_year,
                        raw_payload=None,
                    )
                    run.add_stat("regatta_years_seen")
            except Exception as exc:
                if not _recoverable_acquisition_error(exc):
                    raise
                _quarantine(run, db, store, url, _acquisition_reason(exc, "timeteam_index_error"), raw_key, {"year": year, "error": str(exc)})
    return run.id or ""


def timeteam_race_sync(
    db: DatabaseGateway,
    store: RawStore,
    http: "httpx.Client",
    *,
    slug: str | None = None,
    year: int | None = None,
    all_staged: bool = False,
    sleep_ms: int = 300,
    retrieved_date: str | None = None,
) -> str:
    """Acquire each selected schedule plus every detail document it names."""
    targets = _sync_targets(db, slug=slug, year=year, all_staged=all_staged)
    capture_date = retrieved_date or date.today().isoformat()
    with IngestRun(
        db,
        job_name="timeteam_race_sync",
        source=SOURCE,
        params={"targets": targets, "sleep_ms": sleep_ms},
    ) as run:
        for stat in ("races_fetched", "races_unchanged", "quarantines"):
            run.add_stat(stat, 0)
        for target_index, (target_slug, target_year) in enumerate(targets):
            if all_staged and target_index:
                _sleep(sleep_ms)
            schedule_url = _race_url(target_slug, target_year)
            schedule_key: str | None = None
            try:
                response = http.get(schedule_url)
                response.raise_for_status()
                content = response.content
                schedule = _json_document(content)
                prior_schedule = _staged_regatta(db, target_slug, target_year)
                if prior_schedule and _logically_equal(prior_schedule.get("raw_payload"), schedule):
                    source_record_id = prior_schedule.get("source_record_id")
                else:
                    schedule_key = f"raw/timeteam/usrowing/{target_slug}/{target_year}/index/{capture_date}.json"
                    raw_object = store.put_raw(schedule_key, content, "application/json")
                    source_record_id = register_source_record(
                        db,
                        source=SOURCE,
                        external_key=f"{target_slug}/{target_year}/index",
                        raw_object=raw_object,
                        metadata={"url": schedule_url, "retrieved_date": capture_date},
                    )
                    _upsert_staged_regatta(
                        db,
                        run_id=run.id or "",
                        source_record_id=source_record_id,
                        slug=target_slug,
                        year=target_year,
                        raw_payload=schedule,
                    )
            except Exception as exc:
                if not _recoverable_acquisition_error(exc):
                    raise
                _quarantine(run, db, store, f"{target_slug}/{target_year}", _acquisition_reason(exc, "timeteam_schedule_error"), schedule_key, {"url": schedule_url, "error": str(exc)})
                continue

            race_ids = _schedule_race_ids(schedule)
            if not race_ids:
                _quarantine(run, db, store, f"{target_slug}/{target_year}", "timeteam_schedule_races_missing", schedule_key, {"url": schedule_url})
            for race_uuid in race_ids:
                _sleep(sleep_ms)
                race_url = _race_url(target_slug, target_year, race_uuid)
                race_key: str | None = None
                try:
                    response = http.get(race_url)
                    if response.status_code == 404:
                        _quarantine(run, db, store, race_uuid, "timeteam_race_not_found", None, {"url": race_url})
                        continue
                    response.raise_for_status()
                    content = response.content
                    payload = _json_document(content)
                    prior_race = _staged_race(db, race_uuid)
                    if prior_race and _logically_equal(prior_race.get("raw_payload"), payload):
                        changed = False
                    else:
                        race_key = f"raw/timeteam/usrowing/{target_slug}/{target_year}/race/{race_uuid}/{capture_date}.json"
                        raw_object = store.put_raw(race_key, content, "application/json")
                        source_record_id = register_source_record(
                            db,
                            source=SOURCE,
                            external_key=f"{target_slug}/{target_year}/race/{race_uuid}",
                            raw_object=raw_object,
                            metadata={"url": race_url, "retrieved_date": capture_date},
                        )
                        changed = _upsert_staged_race(
                            db,
                            run_id=run.id or "",
                            source_record_id=source_record_id,
                            slug=target_slug,
                            year=target_year,
                            race_uuid=race_uuid,
                            raw_payload=payload,
                        )
                    run.add_stat("races_fetched")
                    if not changed:
                        run.add_stat("races_unchanged")
                except Exception as exc:
                    if not _recoverable_acquisition_error(exc):
                        raise
                    _quarantine(run, db, store, race_uuid, _acquisition_reason(exc, "timeteam_race_error"), race_key, {"url": race_url, "error": str(exc)})
    return run.id or ""


def timeteam_load(
    db: DatabaseGateway,
    *,
    slug: str | None = None,
    year: int | None = None,
    all_staged: bool = False,
) -> str:
    """Load staged schedules/races as immutable revisions of the core tree."""
    targets = _load_targets(db, slug=slug, year=year, all_staged=all_staged)
    with IngestRun(
        db,
        job_name="timeteam_load",
        source=SOURCE,
        params={"targets": targets},
    ) as run:
        for stat in (
            "crews_loaded", "results_loaded", "clubs_observed", "persons_loaded",
            "statuses_unknown", "quarantines",
        ):
            run.add_stat(stat, 0)
        for target_slug, target_year in targets:
            _load_one(db, run, target_slug, target_year)
    return run.id or ""


def _load_one(db: DatabaseGateway, run: IngestRun, slug: str, year: int) -> None:
    staged = db.execute(
        """
        SELECT source_record_id, raw_payload
        FROM staging.time_team_regatta
        WHERE slug = %s AND year = %s AND raw_payload IS NOT NULL
        """,
        (slug, year),
    )
    if not staged:
        _quarantine(run, db, None, f"{slug}/{year}", "timeteam_schedule_not_staged", None, {})
        return
    schedule = _as_mapping(staged[0].get("raw_payload"))
    races = db.execute(
        """
        SELECT race_uuid, raw_payload
        FROM staging.time_team_race
        WHERE slug = %s AND year = %s
        ORDER BY race_uuid
        """,
        (slug, year),
    )
    race_docs = {str(row["race_uuid"]): _as_mapping(row.get("raw_payload")) for row in races}
    scheduled_ids = _schedule_race_ids(schedule)
    missing = sorted(set(scheduled_ids) - set(race_docs))
    if missing:
        for race_uuid in missing:
            _quarantine(run, db, None, race_uuid, "timeteam_schedule_race_missing", None, {"slug": slug, "year": year})
        return
    if not scheduled_ids:
        _quarantine(run, db, None, f"{slug}/{year}", "timeteam_schedule_races_missing", None, {})
        return
    race_objects: dict[str, Mapping[str, Any]] = {}
    for race_uuid in scheduled_ids:
        race = _race_for_id(race_docs[race_uuid], race_uuid) or _race_for_id(schedule, race_uuid)
        if not race:
            _quarantine(run, db, None, race_uuid, "timeteam_race_identity_mismatch", None, {"reason": "race document does not contain scheduled race", "slug": slug, "year": year})
        else:
            race_objects[race_uuid] = race
    # A revision must be a complete child tree.  Do not create a partial
    # regatta when one of the checksum inputs failed its identity check.
    if len(race_objects) != len(scheduled_ids):
        return

    checksum = _payload_checksum(schedule, race_docs, scheduled_ids)
    external_key = f"{slug}/{year}"
    existing = db.execute(
        """
        SELECT revision, payload_checksum
        FROM core.regatta
        WHERE source = %s AND external_key = %s
        ORDER BY revision DESC
        LIMIT 1
        """,
        (SOURCE, external_key),
    )
    if existing and existing[0].get("payload_checksum") == checksum:
        return
    revision = int(existing[0]["revision"]) + 1 if existing else 1
    regatta = _first_value(schedule.get("regatta"))
    if not regatta:
        _quarantine(run, db, None, external_key, "timeteam_regatta_missing", None, {})
        return
    regatta_id = _insert_regatta(
        db,
        source_record_id=staged[0].get("source_record_id"),
        external_key=external_key,
        revision=revision,
        regatta=regatta,
        checksum=checksum,
    )
    tz_name = _regatta_timezone(regatta)
    for race_uuid in scheduled_ids:
        race = race_objects[race_uuid]
        event = _first_value(race_docs[race_uuid].get("event"))
        event_id = _insert_event(db, regatta_id, race_uuid, race, event, tz_name)
        for row in _round_crews(race_docs[race_uuid]):
            entry_id = _insert_entry(db, run, event_id, row, staged[0].get("source_record_id"), race_uuid)
            if entry_id is None:
                continue
            _insert_result(db, run, entry_id, row)


def _insert_regatta(
    db: DatabaseGateway,
    *,
    source_record_id: object,
    external_key: str,
    revision: int,
    regatta: Mapping[str, Any],
    checksum: str,
) -> object:
    start_date, end_date = _regatta_dates(regatta)
    rows = db.execute(
        """
        INSERT INTO core.regatta
            (source, external_key, revision, name, start_date, end_date, venue,
             city, state, category, raw, payload_checksum, source_record_id, parser_version)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s)
        RETURNING id
        """,
        (
            SOURCE, external_key, revision, _text(regatta, "name", "title") or external_key,
            start_date, end_date, _text(regatta, "venue_name", "venue"),
            _text(regatta, "city"), _text(regatta, "state", "region"),
            _text(regatta, "category"), json.dumps(regatta, sort_keys=True), checksum,
            source_record_id, PARSER_VERSION,
        ),
    )
    if not rows:
        raise RuntimeError("core.regatta insert did not return an id")
    return rows[0]["id"]


def _insert_event(
    db: DatabaseGateway,
    regatta_id: object,
    race_uuid: str,
    race: Mapping[str, Any],
    event: Mapping[str, Any],
    timezone_name: str,
) -> object:
    event_name = _text(race, "event_name", "name") or _text(event, "name", "event_name") or race_uuid
    round_name = _text(race, "round_type_name", "round_name") or _text(event, "round_type_name")
    name = event_name if not round_name or round_name.casefold() in event_name.casefold() else f"{event_name} — {round_name}"
    rows = db.execute(
        """
        INSERT INTO core.regatta_event
            (regatta_id, external_key, name, event_code, boat_class_raw, age_class_raw,
             gender_raw, round, scheduled_at, progression, raw)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)
        RETURNING id
        """,
        (
            regatta_id, race_uuid, name, _text(race, "event_code", "code") or _text(event, "code"),
            _text(race, "boat_class", "boat_class_name") or _text(event, "boattype"),
            _text(race, "age_class", "age_class_name") or _text(event, "age_class"),
            _text(race, "gender", "gender_name") or _text(event, "sex"), round_name,
            _scheduled_at(_text(race, "start_datetime", "scheduled_at", "start_time"), timezone_name),
            json.dumps(race.get("rules") or []), json.dumps(race, sort_keys=True),
        ),
    )
    if not rows:
        raise RuntimeError("core.regatta_event insert did not return an id")
    return rows[0]["id"]


def _insert_entry(
    db: DatabaseGateway,
    run: IngestRun,
    event_id: object,
    row: Mapping[str, Any],
    source_record_id: object,
    race_uuid: str,
) -> object | None:
    entry = _as_mapping(row.get("entry"))
    crew_id = _text(row, "crew_id", "race_crew_id", "id")
    if not crew_id:
        _quarantine(run, db, None, race_uuid, "timeteam_crew_missing_uuid", None, {"race_uuid": race_uuid})
        return None
    club = _as_mapping(entry.get("club"))
    provider_club_id: object | None = None
    if club:
        club_key = _text(club, "id", "uuid")
        if not club_key:
            _quarantine(run, db, None, crew_id, "timeteam_club_missing_uuid", None, {"race_uuid": race_uuid, "club": dict(club)})
        else:
            provider_club_id, inserted = _insert_provider_club(db, club_key, club, source_record_id)
            if inserted:
                run.add_stat("clubs_observed")
    entry_name = _text(entry, "name", "shortname") or _text(club, "name") or "Unknown club"
    rows = db.execute(
        """
        INSERT INTO core.regatta_entry
            (event_id, external_key, bib, lane, club_source_name, provider_club_id, crew_label, raw)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        RETURNING id
        """,
        (
            event_id, crew_id, _value_as_text(row.get("bib")), _int_or_none(row.get("lane")),
            entry_name, provider_club_id, _crew_label(entry), json.dumps(_entry_raw(row), sort_keys=True),
        ),
    )
    if not rows:
        raise RuntimeError("core.regatta_entry insert did not return an id")
    run.add_stat("crews_loaded")
    stroke = _text(entry, "stroke_fullname")
    if stroke:
        db.execute(
            """
            INSERT INTO core.result_person (entry_id, role, seat, person_name, raw)
            VALUES (%s, 'stroke', NULL, %s, %s::jsonb)
            """,
            (rows[0]["id"], stroke, json.dumps({"stroke_fullname": stroke})),
        )
        run.add_stat("persons_loaded")
    return rows[0]["id"]


def _insert_provider_club(
    db: DatabaseGateway, club_key: str, club: Mapping[str, Any], source_record_id: object
) -> tuple[object, bool]:
    rows = db.execute(
        """
        INSERT INTO core.provider_club
            (source, external_key, display_name, code, federation, raw, source_record_id)
        VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s)
        ON CONFLICT (source, external_key) DO NOTHING
        RETURNING id
        """,
        (SOURCE, club_key, _text(club, "name", "shortname") or club_key, _text(club, "code"),
         _text(club, "federation"), json.dumps(club, sort_keys=True), source_record_id),
    )
    if rows:
        return rows[0]["id"], True
    rows = db.execute(
        "SELECT id FROM core.provider_club WHERE source = %s AND external_key = %s",
        (SOURCE, club_key),
    )
    if not rows:
        raise RuntimeError("provider club conflict did not expose its existing id")
    return rows[0]["id"], False


def _insert_result(db: DatabaseGateway, run: IngestRun, entry_id: object, row: Mapping[str, Any]) -> None:
    status = row.get("status")
    if isinstance(status, int) and not isinstance(status, bool) and status not in KNOWN_STATUS_INTS:
        run.add_stat("statuses_unknown")
        run.warn(f"unknown Time-Team status {status}")
    times = _as_list(row.get("times"))
    finish = _finish_total(times)
    db.execute(
        """
        INSERT INTO core.regatta_result
            (entry_id, status, position, adjusted_position, time_ms, adjusted_time_ms,
             handicap_ms, delta_ms, penalty, correction, splits)
        VALUES (%s, %s, %s, %s, %s, %s, NULL, %s, %s::jsonb, %s::jsonb, %s::jsonb)
        """,
        (
            entry_id, _value_as_text(status) or "", _int_or_none(finish.get("pos")),
            _int_or_none(row.get("adjusted_pos")), parse_time_ms(finish.get("result")),
            parse_time_ms(row.get("adjusted_result")), parse_time_ms(row.get("adjusted_plus")),
            json.dumps(row.get("penalty")) if row.get("penalty") is not None else None,
            json.dumps(row.get("correction")) if row.get("correction") is not None else None,
            json.dumps(times, sort_keys=True),
        ),
    )
    run.add_stat("results_loaded")


def parse_time_ms(value: object) -> int | None:
    """Parse provider ``MM:SS.hh`` and delta ``+SS.hh`` values to milliseconds."""
    if value is None or value == "":
        return None
    text = str(value).strip()
    if not text or text.upper() in {"DNS", "DNF", "DSQ", "-"}:
        return None
    sign = -1 if text.startswith("-") else 1
    text = text.lstrip("+-")
    try:
        pieces = text.split(":")
        seconds = float(pieces.pop())
        minutes = 0
        multiplier = 60
        for piece in reversed(pieces):
            minutes += int(piece) * multiplier
            multiplier *= 60
        milliseconds = round((minutes + seconds) * 1000)
    except (TypeError, ValueError):
        return None
    return sign * milliseconds if milliseconds > 0 else None


def _index_url(year: int) -> str:
    return f"{INDEX_URL}?{urlencode({'year': year})}"


def _race_url(slug: str, year: int, race_uuid: str | None = None) -> str:
    suffix = f"/{race_uuid}" if race_uuid else ""
    return f"{API_BASE_URL}/{slug}/{year}/race{suffix}"


def _regatta_pairs_from_html(content: bytes, selected_year: int) -> list[tuple[str, int]]:
    tree = html.fromstring(content)
    pairs: set[tuple[str, int]] = set()
    for href in tree.xpath("//a/@href"):
        match = re.fullmatch(r"/([a-z0-9-]+)/(20[0-9]{2})", str(href))
        if match:
            pairs.add((match.group(1), int(match.group(2))))
    return sorted(pair for pair in pairs if pair[1] == selected_year)


def _schedule_race_ids(schedule: Mapping[str, Any]) -> list[str]:
    races = schedule.get("race")
    ids: list[str] = []
    if isinstance(races, Mapping):
        for key, value in races.items():
            if isinstance(value, Mapping):
                ids.append(_text(value, "uuid", "id") or str(key))
    elif isinstance(races, list):
        for value in races:
            if isinstance(value, Mapping) and (race_id := _text(value, "uuid", "id")):
                ids.append(race_id)
    return list(dict.fromkeys(ids))


def _sync_targets(db: DatabaseGateway, *, slug: str | None, year: int | None, all_staged: bool) -> list[tuple[str, int]]:
    if bool(slug) != bool(year is not None):
        raise ValueError("--slug and --year must be supplied together")
    if slug and year is not None:
        return [(slug, year)]
    if not all_staged:
        raise ValueError("supply --slug/--year or --all-staged")
    rows = db.execute("SELECT slug, year FROM staging.time_team_regatta ORDER BY year, slug")
    return [(str(row["slug"]), int(row["year"])) for row in rows]


def _load_targets(db: DatabaseGateway, **kwargs: Any) -> list[tuple[str, int]]:
    return _sync_targets(db, **kwargs)


def _staged_regatta(db: DatabaseGateway, slug: str, year: int) -> Mapping[str, Any] | None:
    rows = db.execute(
        """
        SELECT source_record_id, raw_payload
        FROM staging.time_team_regatta
        WHERE slug = %s AND year = %s
        """,
        (slug, year),
    )
    return rows[0] if rows else None


def _staged_race(db: DatabaseGateway, race_uuid: str) -> Mapping[str, Any] | None:
    rows = db.execute(
        "SELECT source_record_id, raw_payload FROM staging.time_team_race WHERE race_uuid = %s::uuid",
        (race_uuid,),
    )
    return rows[0] if rows else None


def _upsert_staged_regatta(db: DatabaseGateway, *, run_id: str, source_record_id: object, slug: str, year: int, raw_payload: Mapping[str, Any] | None) -> bool:
    existing = _staged_regatta(db, slug, year)
    if raw_payload is not None and existing and _logically_equal(existing.get("raw_payload"), raw_payload):
        return False
    db.execute(
        """
        INSERT INTO staging.time_team_regatta
            (ingest_run_id, source_record_id, slug, year, raw_payload, retrieved_at)
        VALUES (%s, %s, %s, %s, %s::jsonb, NOW())
        ON CONFLICT (slug, year) DO UPDATE
        SET ingest_run_id = EXCLUDED.ingest_run_id,
            source_record_id = EXCLUDED.source_record_id,
            raw_payload = COALESCE(EXCLUDED.raw_payload, staging.time_team_regatta.raw_payload),
            retrieved_at = EXCLUDED.retrieved_at
        """,
        (run_id, source_record_id, slug, year, json.dumps(raw_payload) if raw_payload is not None else None),
    )
    return True


def _upsert_staged_race(db: DatabaseGateway, *, run_id: str, source_record_id: object, slug: str, year: int, race_uuid: str, raw_payload: Mapping[str, Any]) -> bool:
    existing = _staged_race(db, race_uuid)
    if existing and _logically_equal(existing.get("raw_payload"), raw_payload):
        return False
    db.execute(
        """
        INSERT INTO staging.time_team_race
            (ingest_run_id, source_record_id, slug, year, race_uuid, raw_payload, retrieved_at)
        VALUES (%s, %s, %s, %s, %s::uuid, %s::jsonb, NOW())
        ON CONFLICT (race_uuid) DO UPDATE
        SET ingest_run_id = EXCLUDED.ingest_run_id,
            source_record_id = EXCLUDED.source_record_id,
            slug = EXCLUDED.slug,
            year = EXCLUDED.year,
            raw_payload = EXCLUDED.raw_payload,
            retrieved_at = EXCLUDED.retrieved_at
        RETURNING id
        """,
        (run_id, source_record_id, slug, year, race_uuid, json.dumps(raw_payload)),
    )
    return True


def _payload_checksum(schedule: Mapping[str, Any], race_docs: Mapping[str, Mapping[str, Any]], race_ids: Iterable[str]) -> str:
    payload = {
        "schedule": _canonical_document(schedule),
        "races": {race_id: _canonical_document(race_docs[race_id]) for race_id in sorted(race_ids)},
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def _logically_equal(left: object, right: object) -> bool:
    return _canonical_document(left) == _canonical_document(right)


def _canonical_document(value: object) -> object:
    """Remove provider envelope churn before comparing or checksumming JSON.

    Raw R2 objects and staging retain the verbatim first observation.  This
    normalized view is solely the idempotency boundary used by sync and load.
    """
    if isinstance(value, str):
        value = json.loads(value)
    normalized = json.loads(json.dumps(value))
    if not isinstance(normalized, dict):
        return normalized
    for key in ("timestamp", "race_media", "communication", "communication_key"):
        normalized.pop(key, None)
    regattas = normalized.get("regatta")
    if isinstance(regattas, dict):
        regatta_values = regattas.values()
    elif isinstance(regattas, list):
        regatta_values = regattas
    else:
        regatta_values = []
    for regatta in regatta_values:
        if isinstance(regatta, dict):
            regatta.pop("current_regatta_day", None)
    return normalized


def _regatta_dates(regatta: Mapping[str, Any]) -> tuple[str | None, str | None]:
    days = _as_list(regatta.get("regatta_days"))
    values = sorted(
        str(item.get("date") or item.get("day_date") or item.get("start_date"))[:10]
        for item in days
        if isinstance(item, Mapping) and (item.get("date") or item.get("day_date") or item.get("start_date"))
    )
    if not values:
        start = _text(regatta, "start_date", "start")
        end = _text(regatta, "end_date", "end")
        return (start[:10] if start else None, end[:10] if end else start[:10] if start else None)
    return values[0], values[-1]


def _regatta_timezone(regatta: Mapping[str, Any]) -> str:
    config = _as_mapping(regatta.get("config"))
    return _text(regatta, "timezone", "time_zone") or _text(config, "timezone", "time_zone") or "UTC"


def _scheduled_at(value: str | None, timezone_name: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        return parsed
    try:
        return parsed.replace(tzinfo=ZoneInfo(timezone_name))
    except ZoneInfoNotFoundError:
        return parsed.replace(tzinfo=timezone.utc)


def _round_crews(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = payload.get("round_crew")
    race_crews = _keyed_rows(payload.get("race_crew"))
    if isinstance(rows, Mapping):
        output = []
        for key, value in rows.items():
            if isinstance(value, Mapping):
                round_row = {"id": str(key), **value}
                race_crew_id = _text(round_row, "race_crew_id", "crew_id")
                # Detail responses differ slightly across Time-Team vintages:
                # common entry metadata may live on race_crew while timing and
                # position live on round_crew.  Preserve both, with the round
                # observation taking precedence.
                output.append({**race_crews.get(race_crew_id or "", {}), **round_row})
        return output
    output = []
    for row in _as_list(rows):
        if isinstance(row, Mapping):
            race_crew_id = _text(row, "race_crew_id", "crew_id")
            output.append({**race_crews.get(race_crew_id or "", {}), **row})
    return output


def _keyed_rows(value: object) -> dict[str, Mapping[str, Any]]:
    if isinstance(value, Mapping):
        return {
            str(key): {"id": str(key), **row}
            for key, row in value.items()
            if isinstance(row, Mapping)
        }
    return {
        row_id: row
        for row in _as_list(value)
        if isinstance(row, Mapping) and (row_id := _text(row, "id", "uuid", "crew_id"))
    }


def _race_for_id(payload: Mapping[str, Any], race_uuid: str) -> Mapping[str, Any]:
    races = payload.get("race")
    if isinstance(races, Mapping):
        if isinstance(races.get(race_uuid), Mapping):
            return races[race_uuid]
        if _text(races, "uuid", "id") == race_uuid:
            return races
        for value in races.values():
            if isinstance(value, Mapping) and _text(value, "uuid", "id") == race_uuid:
                return value
    elif isinstance(races, list):
        for value in races:
            if isinstance(value, Mapping) and _text(value, "uuid", "id") == race_uuid:
                return value
    return {}


def _finish_total(times: list[Any]) -> Mapping[str, Any]:
    points = [(point, _as_mapping(point.get("total"))) for point in times if isinstance(point, Mapping)]
    points = [(point, total) for point, total in points if total]
    if not points:
        return {}
    finish_names = {"finish", "total", "finishline"}
    named_finish = [
        (point, total)
        for point, total in points
        if re.sub(r"[^a-z]", "", str(point.get("location_name", "")).casefold()) in finish_names
    ]
    if named_finish:
        return named_finish[-1][1]
    distance_points: list[tuple[float, Mapping[str, Any]]] = []
    for point, total in points:
        distance = point.get("distance")
        if distance is None:
            match = re.search(r"(\d+(?:\.\d+)?)\s*m$", str(point.get("location_name", "")).casefold())
            distance = match.group(1) if match else None
        try:
            distance_points.append((float(distance), total))
        except (TypeError, ValueError):
            pass
    if distance_points:
        return max(distance_points, key=lambda item: item[0])[1]
    return points[-1][1]


def _crew_label(entry: Mapping[str, Any]) -> str | None:
    name = _text(entry, "name") or ""
    # ``entry.string`` is a person name in the real API capture.  Derive a
    # label only from an explicit suffix on the club/entry name, never from a
    # provider display string that could duplicate a person name outside the
    # isolated result_person table.
    club = _as_mapping(entry.get("club"))
    for base in (_text(club, "name"), _text(club, "shortname")):
        if base:
            for candidate in (name, _text(entry, "shortname") or ""):
                if candidate.startswith(base):
                    suffix = candidate[len(base):].strip(" -–—()")
                    if suffix:
                        return suffix
    if " - " in name:
        return name.rsplit(" - ", 1)[1] or None
    return None


def _entry_raw(row: Mapping[str, Any]) -> dict[str, Any]:
    """Return an entry audit payload without duplicating the person-name field.

    Private acquisition/staging documents retain the provider response verbatim,
    but the core result tree stores person names in exactly one table.
    """
    raw = json.loads(json.dumps(row))
    entry = raw.get("entry")
    if isinstance(entry, dict):
        entry.pop("stroke_fullname", None)
        entry.pop("string", None)
    return raw


def _json_document(content: bytes) -> Mapping[str, Any]:
    value = json.loads(content)
    if not isinstance(value, Mapping):
        raise ValueError("Time-Team response is not a JSON object")
    return value


def _first_value(value: object) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        if any(key in value for key in ("name", "uuid", "id")):
            return value
        for nested in value.values():
            if isinstance(nested, Mapping):
                return nested
    if isinstance(value, list):
        for nested in value:
            if isinstance(nested, Mapping):
                return nested
    return {}


def _as_mapping(value: object) -> Mapping[str, Any]:
    if isinstance(value, str):
        value = json.loads(value)
    return value if isinstance(value, Mapping) else {}


def _as_list(value: object) -> list[Any]:
    return value if isinstance(value, list) else list(value.values()) if isinstance(value, Mapping) else []


def _text(mapping: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = mapping.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _value_as_text(value: object) -> str | None:
    return str(value) if value is not None else None


def _int_or_none(value: object) -> int | None:
    try:
        return int(str(value)) if value is not None and str(value) != "" else None
    except (TypeError, ValueError):
        return None


def _sleep(sleep_ms: int) -> None:
    if sleep_ms > 0:
        time.sleep(sleep_ms / 1000)


def _recoverable_acquisition_error(exc: Exception) -> bool:
    try:
        import httpx
    except ImportError:
        return isinstance(exc, (QuarantineableError, OSError, UnicodeError, ValueError, json.JSONDecodeError))
    return isinstance(exc, (httpx.HTTPError, QuarantineableError, OSError, UnicodeError, ValueError, json.JSONDecodeError))


def _acquisition_reason(exc: Exception, fallback: str) -> str:
    if isinstance(exc, QuarantineableError):
        return "timeteam_checksum_conflict"
    if isinstance(exc, json.JSONDecodeError):
        return "timeteam_json_decode_error"
    return fallback


def _quarantine(run: IngestRun, db: DatabaseGateway, store: RawStore | None, external_key: str, reason: str, raw_key: str | None, details: Mapping[str, Any]) -> None:
    raw_uri = f"r2://{store.bucket}/{raw_key}" if store is not None and raw_key else None
    quarantine(db, run.id or "", SOURCE, external_key, reason, raw_uri, details)
    run.add_stat("quarantines")
    run.warn(f"{external_key}: {reason}")


__all__ = ["SOURCE", "parse_time_ms", "register", "timeteam_load", "timeteam_race_sync", "timeteam_regatta_index"]


def register(app: typer.Typer) -> None:
    """Attach Time-Team commands; the Wave-1 integration owner calls this."""

    @app.command(name="timeteam-regatta-index")
    def timeteam_regatta_index_cmd(
        years: str = typer.Option("2020,2021,2022,2023,2024,2025,2026", help="Comma-separated regatta years"),
        slugs: str = typer.Option("", help="Optional comma-separated slug override"),
    ) -> None:
        with job_context() as (db, store, http):
            typer.echo(timeteam_regatta_index(db, store, http, years=[int(item) for item in split_csv(years)], slugs=split_csv(slugs) or None))

    @app.command(name="timeteam-race-sync")
    def timeteam_race_sync_cmd(
        slug: str = typer.Option("", help="One regatta slug"),
        year: int | None = typer.Option(None, help="Year paired with --slug"),
        all_staged: bool = typer.Option(False, "--all-staged", help="Sync every discovered regatta"),
        sleep_ms: int = typer.Option(300, help="Delay between API calls"),
    ) -> None:
        with job_context() as (db, store, http):
            typer.echo(timeteam_race_sync(db, store, http, slug=slug or None, year=year, all_staged=all_staged, sleep_ms=sleep_ms))

    @app.command(name="timeteam-load")
    def timeteam_load_cmd(
        slug: str = typer.Option("", help="One regatta slug"),
        year: int | None = typer.Option(None, help="Year paired with --slug"),
        all_staged: bool = typer.Option(False, "--all-staged", help="Load every staged regatta"),
    ) -> None:
        with job_context() as (db, _store, _http):
            typer.echo(timeteam_load(db, slug=slug or None, year=year, all_staged=all_staged))
