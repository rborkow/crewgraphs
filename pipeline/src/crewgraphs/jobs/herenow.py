"""HereNow Breeze results adapter.

The catalog is ``Races`` (``Id``, ``Name``, ``StartDate``, ``EndDate``,
``Sport``, and publication flags).  ``GetBaseRaceData`` provides the race
metadata used by ``core.regatta`` (notably ``Subtitle``, ``Style`` and
``TimeZoneOffset``).  ``GetScopedRaceFlights`` is an array of flights with
``ID``, ``Ordering``, ``Code``, ``Name``, ``StartTime``, ``Status``,
``TimingStatus``, ``RefereeStatus`` and ``EntryResults``.

An ``EntryResults`` item has ``EntryNumber``, ``Status``,
``HandicapTimespan``, ``StartTime1``--``StartTime4``, ``Split1Time``--
``Split3Time``, ``FinishTime1``--``FinishTime4``, and a nested ``Entry``.
The entry's ``Id``, ``AffiliationName``, and
``AffiliationOrganizationId`` map to an entry and provider club.  The latter
is the provider-club external key when available; otherwise the normalized
affiliation display name is used.  ``Entry.Name`` is presentation-only:
HereNow displays a single as ``person (club)`` and a crew as ``club
(stroke)``.  It is never persisted in entry/event raw JSON.  Explicit
``Competitors`` are preferred for people; when omitted by Breeze, that display
form supplies the single person or stroke as the only recoverable name.

HereNow gives elapsed performance as clock timestamps, rather than a duration:
the first usable ``FinishTimeN - StartTimeN`` is raw time.  A non-null
``HandicapTimespan`` is parsed as a signed duration and added to raw time to
derive adjusted time.  Scratch/DNS rows with no timestamps therefore retain
their raw status and NULL times.  The provider's R2 bytes remain immutable,
but all Postgres JSON is contact-field scrubbed and core raw JSON excludes
person-bearing entry fields.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Iterable, Iterator

import typer

from crewgraphs.runtime import job_context, split_csv

from ..db import DatabaseGateway
from ..quarantine import quarantine
from ..raw_store import QuarantineableError, RawStore, register_source_record
from ..runlog import IngestRun

if TYPE_CHECKING:
    import httpx


SOURCE = "herenow"
PARSER_VERSION = "herenow-2026.07.1"
DEFAULT_BASE_URL = "https://newwebrole2023.azurewebsites.net"
API_PATH = "/breeze/BreezeApi"
CATALOG_SELECT = "Id,Name,StartDate,EndDate,Sport,IsListed,IsPublished,IsTest"
_TIME_RE = re.compile(r"^([+-])?(?:(\d+):)?(?:(\d+):)?(\d+(?:\.\d+)?)$")
_CONTACT_KEY_RE = re.compile(r"(?:e[ -]?mail|phone|contact|address|waiver|registrant)", re.I)
_SINGLE_RE = re.compile(r"1x", re.I)
_PAREN_RE = re.compile(r"^\s*(.*?)\s*\(([^()]*)\)\s*$")
_PERSON_RAW_ALLOWED = {"Role", "Position", "Seat", "SeatNumber", "Bow", "IsCoxswain"}


def herenow_catalog_sync(
    db: DatabaseGateway,
    store: RawStore,
    http: "httpx.Client",
    *,
    base_url: str | None = None,
    retrieved_at: datetime | None = None,
) -> str:
    """Snapshot the OData race catalog and upsert its staging projection."""
    base = _base_url(base_url)
    stamp = (retrieved_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    raw_key = f"raw/{SOURCE}/catalog/{_iso_millis(stamp)}.json"
    with IngestRun(db, job_name="herenow_catalog_sync", source=SOURCE, params={"base_url": base}) as run:
        for stat in ("catalog_rows", "quarantines"):
            run.add_stat(stat, 0)
        previous = _count(db, "SELECT count(*) AS count FROM staging.herenow_catalog_row")
        try:
            rows = _catalog_rows(http, f"{base}{API_PATH}/Races")
            # Catalog paging has no immutable upstream aggregate representation;
            # archive the exact rows acquired in their response order.
            raw = store.put_raw(raw_key, json.dumps(rows, separators=(",", ":"), ensure_ascii=False).encode(), "application/json")
            source_record_id = register_source_record(
                db, source=SOURCE, external_key="catalog", raw_object=raw,
                metadata={"retrieved_at": stamp.isoformat(), "url": f"{base}{API_PATH}/Races"},
            )
            for row in rows:
                race_id = _as_int(_get(row, "Id", "ID", "id"))
                if race_id is None:
                    run.warn("catalog row without a numeric Id skipped")
                    continue
                _upsert_catalog_row(db, run.id or "", source_record_id, race_id, row)
                run.add_stat("catalog_rows")
            if previous and run.stats["catalog_rows"] < previous * 0.95:
                run.warn(f"catalog count fell from {previous} to {run.stats['catalog_rows']}")
        except Exception as exc:
            if not _recoverable_acquisition_error(exc):
                raise
            _quarantine(db, run, "catalog", exc, store, raw_key, {"url": f"{base}{API_PATH}/Races"})
    return run.id or ""


def herenow_race_backfill(
    db: DatabaseGateway,
    store: RawStore,
    http: "httpx.Client",
    *,
    race_ids: Iterable[str | int] | None = None,
    limit: int = 0,
    refetch_window_days: int = 14,
    sleep_ms: int = 750,
    base_url: str | None = None,
    today: date | None = None,
) -> str:
    """Acquire each selected base/flights pair, quarantining failures per race."""
    base = _base_url(base_url)
    requested = _race_id_set(race_ids)
    selected = _select_races(db, requested, refetch_window_days, today or date.today())
    if limit > 0:
        selected = selected[:limit]
    with IngestRun(
        db, job_name="herenow_race_backfill", source=SOURCE,
        params={"race_ids": sorted(requested), "limit": limit, "refetch_window_days": refetch_window_days},
    ) as run:
        for stat in ("races_selected", "races_fetched", "races_skipped", "quarantines"):
            run.add_stat(stat, 0)
        for race in selected:
            run.add_stat("races_selected")
            race_id = _as_int(race.get("race_id"))
            catalog = _as_dict(race.get("raw_row"))
            if race_id is None or race_id <= 0 or bool(_get(catalog, "IsTest", "isTest")):
                run.add_stat("races_skipped")
                continue
            _fetch_race(db, store, http, run, base, race_id, sleep_ms)
    return run.id or ""


def herenow_load(db: DatabaseGateway, *, race_ids: Iterable[str | int] | None = None) -> str:
    """Load changed staged captures using the insert-only regatta supersede model."""
    wanted = _race_id_set(race_ids)
    with IngestRun(db, job_name="herenow_load", source=SOURCE, params={"race_ids": sorted(wanted)}) as run:
        for stat in ("races_selected", "races_unchanged", "events_loaded", "entries_loaded", "results_loaded", "persons_loaded", "clubs_observed", "quarantines"):
            run.add_stat(stat, 0)
        for row in _load_rows(db, wanted):
            race_id = _as_int(row.get("race_id"))
            if race_id is None:
                continue
            run.add_stat("races_selected")
            try:
                _load_race(db, run, race_id, row["base_payload"], row["flights_payload"], row.get("source_record_id"))
            except Exception as exc:
                if not isinstance(exc, (ValueError, TypeError, KeyError, QuarantineableError)):
                    raise
                _quarantine(db, run, str(race_id), exc, None, None, {"phase": "load"})
    return run.id or ""


def parse_results_time(value: object) -> int | None:
    """Return signed milliseconds for HereNow duration values, else ``None``."""
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.upper() in {"-", "--", "DNS", "DNF", "DSQ", "SCRATCH", "N/A", "OFFICIAL", "OK"}:
        return None
    match = _TIME_RE.fullmatch(text)
    if not match:
        return None
    sign, _hours, _minutes, _seconds = match.groups()
    body = text[1:] if sign else text
    parts = body.split(":")
    # The regex accepts one through three components.  Two are M:SS, while
    # three are H:MM:SS; optional capture groups alone cannot distinguish them.
    total = float(parts[-1])
    if len(parts) >= 2:
        total += int(parts[-2]) * 60
    if len(parts) == 3:
        total += int(parts[-3]) * 3600
    millis = int(round(total * 1000))
    return -millis if sign == "-" else millis


def _catalog_rows(http: "httpx.Client", url: str) -> list[dict[str, Any]]:
    top, skip, rows = 5000, 0, []
    while True:
        response = http.get(url, params={"$orderby": "Id", "$select": CATALOG_SELECT, "$top": top, "$skip": skip, "$inlinecount": "allpages"})
        response.raise_for_status()
        payload = _json_payload(response)
        _raise_breeze_error(payload)
        page = _envelope_rows(payload)
        rows.extend(item for item in page if isinstance(item, dict))
        if len(page) < top:
            return rows
        skip += top


def _fetch_race(db: DatabaseGateway, store: RawStore, http: "httpx.Client", run: IngestRun, base_url: str, race_id: int, sleep_ms: int) -> None:
    raw_key: str | None = None
    try:
        delay = max(sleep_ms, 0) / 1000
        time.sleep(delay)
        response = http.get(f"{base_url}{API_PATH}/GetBaseRaceData", params={"raceId": race_id})
        response.raise_for_status()
        base_payload = _json_payload(response)
        _raise_breeze_error(base_payload)
        day = _payload_day(base_payload)
        raw_key = f"raw/{SOURCE}/race/{race_id}/base/{day}.json"
        base_raw = store.put_raw(raw_key, response.content, "application/json")
        base_source_id = register_source_record(db, source=SOURCE, external_key=f"{race_id}/base", raw_object=base_raw, metadata={"url": str(response.url)})
        _upsert_race_payload(db, run.id or "", base_source_id, race_id, "base", base_payload)

        time.sleep(delay)
        scope_start, scope_end = _scope_window(base_payload)
        response = http.get(f"{base_url}{API_PATH}/GetScopedRaceFlights", params={"raceId": race_id, "scopeStartTime": scope_start, "scopeEndTime": scope_end})
        response.raise_for_status()
        flights_payload = _json_payload(response)
        _raise_breeze_error(flights_payload)
        if not isinstance(flights_payload, list):
            raise ValueError("GetScopedRaceFlights response is not a list")
        raw_key = f"raw/{SOURCE}/race/{race_id}/flights/{day}.json"
        flights_raw = store.put_raw(raw_key, response.content, "application/json")
        flights_source_id = register_source_record(db, source=SOURCE, external_key=f"{race_id}/flights", raw_object=flights_raw, metadata={"url": str(response.url), "scope_start": scope_start, "scope_end": scope_end})
        _upsert_race_payload(db, run.id or "", flights_source_id, race_id, "flights", flights_payload)
        run.add_stat("races_fetched")
    except Exception as exc:
        if not _recoverable_acquisition_error(exc):
            raise
        _quarantine(db, run, str(race_id), exc, store, raw_key, {"phase": "acquire"})


def _load_race(db: DatabaseGateway, run: IngestRun, race_id: int, base: object, flights_payload: object, source_record_id: object) -> None:
    checksum = _payload_checksum(base, flights_payload)
    prior = db.execute("""
        SELECT id, revision, payload_checksum FROM core.regatta
        WHERE source = %s AND external_key = %s ORDER BY revision DESC LIMIT 1
        """, (SOURCE, str(race_id)))
    if prior and prior[0].get("payload_checksum") == checksum:
        run.add_stat("races_unchanged")
        return
    base_dict = _as_dict(base)
    revision = int(prior[0]["revision"]) + 1 if prior else 1
    regatta_id = _returning_id(db, """
        INSERT INTO core.regatta
          (source, external_key, revision, name, start_date, end_date, venue, category,
           raw, payload_checksum, source_record_id, parser_version)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s)
        RETURNING id
        """, (SOURCE, str(race_id), revision, _text(_get(base_dict, "Name", "name"), f"HereNow race {race_id}"),
              _date_value(_get(base_dict, "StartDate", "startDate")), _date_value(_get(base_dict, "EndDate", "endDate")),
              _none_text(_get(base_dict, "Subtitle", "subtitle")), _none_text(_get(base_dict, "Style", "style", "Sport", "sport")),
              json.dumps(_base_raw(base_dict)), checksum, source_record_id, PARSER_VERSION))
    index = _reference_index(flights_payload)
    for flight in _flights(flights_payload, index):
        event_id = _insert_event(db, regatta_id, flight)
        run.add_stat("events_loaded")
        for result in _entries(flight, index):
            _insert_entry_tree(db, run, event_id, flight, result, source_record_id, index)


def _insert_event(db: DatabaseGateway, regatta_id: str, flight: dict[str, Any]) -> str:
    key = _text(_get(flight, "ID", "Id", "FlightId", "id"), "unknown")
    name = _text(_get(flight, "Name", "FlightName", "name"), f"Flight {key}")
    event = _as_dict(_get(flight, "Event", "event"))
    return _returning_id(db, """
        INSERT INTO core.regatta_event
          (regatta_id, external_key, name, event_code, boat_class_raw, age_class_raw,
           gender_raw, round, scheduled_at, raw)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::timestamptz, %s::jsonb)
        RETURNING id
        """, (regatta_id, key, name, _none_text(_get(flight, "Code", "code")),
              _none_text(_get(event, "BoatClass", "boatClass")),
              _none_text(_get(event, "AgeClass", "ageClass")),
              _none_text(_get(event, "Gender", "gender")), _round(flight),
              _none_text(_get(flight, "StartTime", "ScheduledAt", "startTime")), json.dumps(_event_raw(flight))))


def _insert_entry_tree(db: DatabaseGateway, run: IngestRun, event_id: str, flight: dict[str, Any], result: dict[str, Any], source_record_id: object, index: dict[str, dict[str, Any]]) -> None:
    entry = _resolve(_as_dict(_get(result, "Entry", "entry")), index)
    club_name = _text(_get(entry, "AffiliationName", "ClubName", "OrganizationName"), "Unknown")
    organization_id = _none_text(_get(entry, "AffiliationOrganizationId"))
    club_key = f"org:{organization_id}" if organization_id else f"name:{_normalized_key(club_name)}"
    club_id = _provider_club(db, club_key, club_name, _club_raw(entry), source_record_id)
    if club_id:
        run.add_stat("clubs_observed")
    key = _text(_get(entry, "Id", "ID", "EntryId"), _text(_get(result, "EntryId", "EntryNumber", "Bow"), "unknown"))
    bib = _none_text(_get(result, "EntryNumber", "Bow", "Bib"))
    entry_id = _returning_id(db, """
        INSERT INTO core.regatta_entry
          (event_id, external_key, bib, lane, club_source_name, provider_club_id, crew_label, raw)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb) RETURNING id
        """, (event_id, key, bib, _as_int(_get(result, "Lane", "LaneNumber")), club_name, club_id,
              _crew_label(entry, flight, club_name), json.dumps(_entry_raw(entry, result))))
    run.add_stat("entries_loaded")
    raw_time = _elapsed_ms(result)
    handicap = parse_results_time(_get(result, "HandicapTimespan", "AgeHandicap", "Handicap"))
    adjusted = raw_time + handicap if raw_time is not None and handicap is not None else raw_time
    db.execute("""
        INSERT INTO core.regatta_result
          (entry_id, status, position, adjusted_position, time_ms, adjusted_time_ms, handicap_ms, delta_ms, splits)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        """, (entry_id, _text(_get(result, "Status", "status"), "Unknown"),
              _as_int(_get(result, "Place", "Position", "FinishPlaceOverride")),
              _as_int(_get(result, "AdjustedPlace", "AdjustedPosition")), raw_time, adjusted, handicap,
              parse_results_time(_get(result, "Delta", "Margin")), json.dumps(_splits(result))))
    run.add_stat("results_loaded")
    for person in _people(entry, flight):
        db.execute("""
            INSERT INTO core.result_person (entry_id, role, seat, person_name, raw)
            VALUES (%s, %s, %s, %s, %s::jsonb)
            """, (entry_id, person["role"], person["seat"], person["name"], json.dumps(person["raw"])))
        run.add_stat("persons_loaded")


def _provider_club(db: DatabaseGateway, external_key: str, display_name: str, raw: dict[str, Any], source_record_id: object) -> str | None:
    if not external_key:
        return None
    rows = db.execute("""
        INSERT INTO core.provider_club (source, external_key, display_name, raw, source_record_id)
        VALUES (%s, %s, %s, %s::jsonb, %s)
        ON CONFLICT (source, external_key) DO NOTHING RETURNING id
        """, (SOURCE, external_key, display_name, json.dumps(raw), source_record_id))
    if rows:
        return str(rows[0]["id"])
    rows = db.execute("SELECT id FROM core.provider_club WHERE source = %s AND external_key = %s", (SOURCE, external_key))
    return str(rows[0]["id"]) if rows else None


def _select_races(db: DatabaseGateway, requested: set[int], window: int, today: date) -> list[dict[str, Any]]:
    if requested:
        return db.execute("SELECT race_id, raw_row FROM staging.herenow_catalog_row WHERE race_id = ANY(%s) ORDER BY race_id", (sorted(requested),))
    return db.execute("""
        SELECT c.race_id, c.raw_row
        FROM staging.herenow_catalog_row c
        LEFT JOIN staging.herenow_race_payload p ON p.race_id = c.race_id AND p.kind = 'flights'
        WHERE p.race_id IS NULL OR NULLIF(c.raw_row ->> 'StartDate', '')::date >= %s::date
        ORDER BY c.race_id
        """, ((today - timedelta(days=window)).isoformat(),))


def _load_rows(db: DatabaseGateway, wanted: set[int]) -> list[dict[str, Any]]:
    params: tuple[Any, ...] = () if not wanted else (sorted(wanted),)
    predicate = "b.kind = 'base'" if not wanted else "b.race_id = ANY(%s) AND b.kind = 'base'"
    return db.execute(f"""
        SELECT b.race_id, b.raw_payload AS base_payload, f.raw_payload AS flights_payload, b.source_record_id
        FROM staging.herenow_race_payload b
        JOIN staging.herenow_race_payload f ON f.race_id = b.race_id AND f.kind = 'flights'
        WHERE {predicate} ORDER BY b.race_id
        """, params)


def _upsert_catalog_row(db: DatabaseGateway, run_id: str, source_record_id: str, race_id: int, row: dict[str, Any]) -> None:
    db.execute("""
        INSERT INTO staging.herenow_catalog_row (ingest_run_id, source_record_id, race_id, raw_row, retrieved_at)
        VALUES (%s, %s, %s, %s::jsonb, NOW())
        ON CONFLICT (race_id) DO UPDATE SET ingest_run_id = EXCLUDED.ingest_run_id,
          source_record_id = EXCLUDED.source_record_id, raw_row = EXCLUDED.raw_row, retrieved_at = NOW()
        """, (run_id, source_record_id, race_id, json.dumps(_strip_contacts(row))))


def _upsert_race_payload(db: DatabaseGateway, run_id: str, source_record_id: str, race_id: int, kind: str, payload: object) -> None:
    db.execute("""
        INSERT INTO staging.herenow_race_payload (ingest_run_id, source_record_id, race_id, kind, raw_payload, retrieved_at)
        VALUES (%s, %s, %s, %s, %s::jsonb, NOW())
        ON CONFLICT (race_id, kind) DO UPDATE SET ingest_run_id = EXCLUDED.ingest_run_id,
          source_record_id = EXCLUDED.source_record_id, raw_payload = EXCLUDED.raw_payload, retrieved_at = NOW()
        """, (run_id, source_record_id, race_id, kind, json.dumps(_strip_contacts(payload))))


def _scope_window(base: object) -> tuple[str, str]:
    payload = _as_dict(base)
    start = _datetime_value(_get(payload, "StartDate", "startDate"))
    end = _datetime_value(_get(payload, "EndDate", "endDate")) or start
    if start is None:
        raise ValueError("base payload has no StartDate")
    # Race dates are local-midnight values.  Interpret with the provider offset;
    # a one-day event at UTC-4 becomes the verified 04:00Z through 03:59:59.999Z window.
    offset = _as_int(_get(payload, "TimeZoneOffset", "timeZoneOffset")) or 0
    local_tz = timezone(timedelta(hours=offset))
    start_local = start.replace(tzinfo=local_tz)
    end_local = end.replace(tzinfo=local_tz)
    return _iso_millis(start_local), _iso_millis(end_local + timedelta(days=1) - timedelta(milliseconds=1))


def _payload_day(payload: object) -> str:
    value = _date_value(_get(_as_dict(payload), "StartDate", "startDate"))
    return value.isoformat() if value else date.today().isoformat()


def _flights(payload: object, index: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = payload if isinstance(payload, list) else _get(_as_dict(payload), "Flights", "Results", "Data")
    return [_resolve(item, index) for item in rows or () if isinstance(item, dict)]


def _entries(flight: dict[str, Any], index: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = _get(flight, "EntryResults", "Entries", "Results", "RaceEntries")
    return [_resolve(item, index) for item in rows or () if isinstance(item, dict)]


def _reference_index(payload: object) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for item in _objects(payload):
        ref_id = _none_text(item.get("$id"))
        if ref_id:
            index[ref_id] = item
    return index


def _objects(value: object) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from _objects(child)


def _resolve(value: dict[str, Any], index: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ref = _none_text(value.get("$ref"))
    if ref and ref in index:
        return {**index[ref], **{key: item for key, item in value.items() if key != "$ref"}}
    return value


def _elapsed_ms(result: dict[str, Any]) -> int | None:
    for number in range(1, 5):
        start = _datetime_value(_get(result, f"StartTime{number}"))
        finish = _datetime_value(_get(result, f"FinishTime{number}"))
        if start is not None and finish is not None:
            elapsed = int(round((finish - start).total_seconds() * 1000))
            if elapsed > 0:
                return elapsed
    fallback = parse_results_time(_get(result, "Time", "RawTime", "ElapsedTime"))
    return fallback if fallback is not None and fallback > 0 else None


def _splits(result: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"number": number, "time_ms": parsed} for number in range(1, 4)
            if (parsed := parse_results_time(_get(result, f"Split{number}Time"))) is not None]


def _people(entry: dict[str, Any], flight: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for value in _get(entry, "Competitors", "People", "Roster", "PersonInfoes") or ():
        person = _as_dict(value)
        nested = _as_dict(_get(person, "Person", "Competitor"))
        name = _none_text(_get(person, "Name", "DisplayName", "PersonName")) or _none_text(_get(nested, "Name", "DisplayName"))
        if name:
            raw = {
                key: item for key, item in person.items()
                if key in _PERSON_RAW_ALLOWED and isinstance(item, (str, int, float, bool))
            }
            rows.append({"name": name, "role": _text(_get(person, "Role", "Position"), "competitor"), "seat": _as_int(_get(person, "Seat", "SeatNumber")), "raw": raw})
    if rows:
        return rows
    display = _none_text(_get(entry, "Name"))
    match = _PAREN_RE.match(display or "")
    if not match:
        return []
    # Singles put the person before the club; crew events put the stroke after club.
    name = match.group(1).strip() if _SINGLE_RE.search(_text(_get(flight, "Name"), "")) else match.group(2).strip()
    return [{"name": name, "role": "competitor" if _SINGLE_RE.search(_text(_get(flight, "Name"), "")) else "stroke", "seat": None, "raw": {"derived_from": "Entry.Name display"}}] if name else []


def _crew_label(entry: dict[str, Any], flight: dict[str, Any], club_name: str) -> str:
    # This column is non-PII; person-bearing HereNow display strings cannot go here.
    display = _none_text(_get(entry, "Name"))
    return display if display and display.casefold() == club_name.casefold() else club_name


def _base_raw(base: dict[str, Any]) -> dict[str, Any]:
    # Base responses contain whole object graphs (including rosters).  Keep
    # only race metadata here so a future Breeze expansion cannot leak PII.
    allowed = {"Id", "ID", "Name", "StartDate", "EndDate", "Subtitle", "Style", "Sport", "TimeZoneOffset", "VenueId", "ExternalRaceId", "IsListed", "IsPublished", "IsTest", "IsRaceClosed", "Status", "LastYearRaceId"}
    return _strip_contacts({key: value for key, value in base.items() if key in allowed})


def _event_raw(flight: dict[str, Any]) -> dict[str, Any]:
    allowed = {"ID", "Id", "Ordering", "Code", "Name", "StartTime", "ActualStartTime", "Status", "TimingStatus", "RefereeStatus", "ProgressionLevel", "ProgressionLevelOrder", "ProgressionDescription", "HasMasterHandicap", "HasMasterCategory", "HasSplits", "IsTimingElapsedOnly", "IsDistance", "IsVirtual", "OfficialNote"}
    return _strip_contacts({key: value for key, value in flight.items() if key in allowed})


def _entry_raw(entry: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    entry_allowed = {"Id", "ID", "EventId", "AffiliationName", "AffiliationOrganizationId", "HandicapAge", "Sex", "ExternalEntryId", "ExternalIdType", "Seed", "SeedInfo", "Status", "SortGroup", "IsComposite", "Gender"}
    result_allowed = {"ID", "Id", "EntryId", "FlightId", "EntryNumber", "Status", "TimingSystem", "HandicapTimespan", "StartTime1", "StartTime2", "StartTime3", "StartTime4", "Split1Time", "Split2Time", "Split3Time", "FinishTime1", "FinishTime2", "FinishTime3", "FinishTime4", "FinishOrderOverride", "FinishPlaceOverride", "Distance", "Points", "DistanceSplit1", "DistanceSplit2", "DistanceSplit3", "DistanceSplit4"}
    safe_entry = {key: value for key, value in entry.items() if key in entry_allowed}
    safe_result = {key: value for key, value in result.items() if key in result_allowed}
    return _strip_contacts({"entry": safe_entry, "result": safe_result})


def _club_raw(entry: dict[str, Any]) -> dict[str, Any]:
    return _strip_contacts({"AffiliationOrganizationId": _get(entry, "AffiliationOrganizationId"), "AffiliationName": _get(entry, "AffiliationName")})


def _strip_contacts(value: object) -> object:
    if isinstance(value, list):
        return [_strip_contacts(item) for item in value]
    if not isinstance(value, dict):
        return value
    return {key: _strip_contacts(item) for key, item in value.items() if not _CONTACT_KEY_RE.search(key)}


def _round(flight: dict[str, Any]) -> str | None:
    """Keep a round only when Breeze supplied a provider field for it."""
    return _none_text(_get(flight, "Round", "ProgressionDescription"))


def _normalized_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _json_payload(response: Any) -> object:
    try:
        return response.json()
    except Exception as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc


def _raise_breeze_error(payload: object) -> None:
    if isinstance(payload, dict) and any(key in payload for key in ("Error", "error", "Errors", "errors", "Message", "ExceptionMessage")):
        raise ValueError(f"Breeze error envelope: {payload}")


def _envelope_rows(payload: object) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("Results"), list):
        return payload["Results"]
    raise ValueError("catalog response is neither an array nor a Results envelope")


def _payload_checksum(base: object, flights: object) -> str:
    payload = {"base": base, "flights": flights}
    canonical = json.dumps(_canonicalize_breeze(payload, _reference_index(payload)), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _canonicalize_breeze(value: object, index: dict[str, dict[str, Any]]) -> object:
    """Turn a Breeze object graph into deterministic nodes without ``$id``.

    A ``$ref`` is resolved through ``index`` and represented by a synthetic
    node allocated in encounter order, never by the upstream serialization ID.
    Defining each graph object once also keeps cyclic flight/entry documents
    compact instead of recursively expanding them for checksumming.
    """
    labels: dict[str, str] = {}
    nodes: dict[str, object] = {}

    def node_for(reference: str, target: dict[str, Any]) -> str:
        if reference in labels:
            return labels[reference]
        label = f"node-{len(labels) + 1}"
        labels[reference] = label
        nodes[label] = {}  # Reserve before walking cycles.
        nodes[label] = walk_fields(target)
        return label

    def walk(value: object) -> object:
        if isinstance(value, list):
            return [walk(item) for item in value]
        if not isinstance(value, dict):
            return value
        reference = _none_text(value.get("$ref"))
        if reference:
            target = index.get(reference)
            if target is None:
                return {"unresolved_reference": True}
            resolved = {"resolved_node": node_for(reference, target)}
            overrides = {key: item for key, item in value.items() if key not in {"$ref", "$id", "$type"}}
            if overrides:
                resolved["overrides"] = walk_fields(overrides)
            return resolved
        identity = _none_text(value.get("$id"))
        if identity:
            return {"resolved_node": node_for(identity, value)}
        return walk_fields(value)

    def walk_fields(mapping: dict[str, Any]) -> dict[str, object]:
        return {key: walk(item) for key, item in mapping.items() if key not in {"$id", "$type"}}

    return {"root": walk(value), "nodes": nodes}


def _recoverable_acquisition_error(exc: Exception) -> bool:
    try:
        import httpx
    except ImportError:
        return isinstance(exc, (QuarantineableError, OSError, UnicodeError, ValueError))
    return isinstance(exc, (httpx.HTTPError, QuarantineableError, OSError, UnicodeError, ValueError))


def _quarantine(db: DatabaseGateway, run: IngestRun, external_key: str, exc: Exception, store: RawStore | None, key: str | None, details: dict[str, Any]) -> None:
    quarantine(db, run.id or "", SOURCE, external_key, str(exc), f"r2://{store.bucket}/{key}" if store and key else None, details)
    run.add_stat("quarantines")
    run.warn(f"{external_key}: {exc}")


def _base_url(value: str | None) -> str:
    return (value or os.environ.get("HERENOW_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")


def _race_id_set(values: Iterable[str | int] | None) -> set[int]:
    return {number for value in values or () if (number := _as_int(value)) is not None}


def _count(db: DatabaseGateway, query: str) -> int:
    rows = db.execute(query)
    return int(rows[0].get("count", 0)) if rows else 0


def _returning_id(db: DatabaseGateway, query: str, params: tuple[Any, ...]) -> str:
    rows = db.execute(query, params)
    if not rows or not rows[0].get("id"):
        raise RuntimeError("insert did not return an id")
    return str(rows[0]["id"])


def _get(value: dict[str, Any], *keys: str) -> object:
    for key in keys:
        if key in value and value[key] is not None:
            return value[key]
    return None


def _as_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text(value: object, fallback: str) -> str:
    return _none_text(value) or fallback


def _none_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _as_int(value: object) -> int | None:
    try:
        return int(str(value)) if value is not None and str(value).strip() else None
    except (TypeError, ValueError):
        return None


def _date_value(value: object) -> date | None:
    parsed = _datetime_value(value)
    return parsed.date() if parsed else None


def _datetime_value(value: object) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def _iso_millis(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def register(app: typer.Typer) -> None:
    """Attach commands; the application root wires this module at integration."""
    @app.command(name="herenow-catalog-sync")
    def catalog_cmd() -> None:
        with job_context() as (db, store, http):
            typer.echo(herenow_catalog_sync(db, store, http))

    @app.command(name="herenow-race-backfill")
    def backfill_cmd(race_ids: str = typer.Option("", help="Comma-separated race ids"), limit: int = 0, refetch_window_days: int = 14, sleep_ms: int = 750) -> None:
        with job_context() as (db, store, http):
            typer.echo(herenow_race_backfill(db, store, http, race_ids=split_csv(race_ids), limit=limit, refetch_window_days=refetch_window_days, sleep_ms=sleep_ms))

    @app.command(name="herenow-load")
    def load_cmd(race_ids: str = typer.Option("", help="Comma-separated race ids")) -> None:
        with job_context() as (db, _store, _http):
            typer.echo(herenow_load(db, race_ids=split_csv(race_ids)))


__all__ = ["SOURCE", "herenow_catalog_sync", "herenow_race_backfill", "herenow_load", "parse_results_time", "register"]
