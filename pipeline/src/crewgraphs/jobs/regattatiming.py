"""Acquire and load RegattaTiming's server-rendered collegiate results pages.

The source occasionally blocks non-browser automation.  This module deliberately
uses the shared, honest runtime user agent and treats a 403 as a terminal,
quarantined condition; it never changes identity or retries around a block.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, time as clock_time, timezone
from typing import TYPE_CHECKING, Any, Callable, Iterable

from lxml import html

from crewgraphs.db import DatabaseGateway
from crewgraphs.quarantine import quarantine
from crewgraphs.raw_store import QuarantineableError, RawStore, register_source_record
from crewgraphs.runlog import IngestRun
from crewgraphs.runtime import job_context, split_csv

if TYPE_CHECKING:
    import httpx


SOURCE = "regattatiming"
PARSER_VERSION = "regattatiming-2026.07.1"
BASE_URL = "https://results.regattatiming.com/backoffice/webpages/results"
SUMMARY_URL = BASE_URL + "/summary.jsp?raceId={race_id}"
STATIC_URL = BASE_URL + "/staticRaceResults.jsp?raceId={race_id}"
EVENT_RE = re.compile(r"^Event\s*#\s*(?P<number>\d+)\s+(?P<body>.+?)\s*$", re.I)
ROUND_RE = re.compile(r"\b(?P<round>(?:Heat|Semi(?:final)?|Final|Repechage|Time Trial)\s*\d*|(?:Grand|Petite)\s+Final)\b", re.I)
TIME_RE = re.compile(r"^(?:(?P<minutes>\d+):)?(?P<seconds>\d{1,2})(?:\.(?P<fraction>\d{1,3}))?$")
STATUS_RE = re.compile(r"\b(DNS|DNF|DSQ|EXH|EXHIBITION)\b", re.I)


class ParseShapeError(ValueError):
    """A purported results section changed its table contract."""


class TimeParseError(ValueError):
    """A finish/margin string that should be a time cannot be interpreted."""


@dataclass(frozen=True)
class ResultRow:
    position: int | None
    lane: int | None
    club: str
    provider_external_key: str
    stroke: str | None
    time_ms: int | None
    delta_ms: int | None
    status: str
    raw: dict[str, str]
    person_raw_entry: str | None


@dataclass(frozen=True)
class EventSection:
    event_id: str
    number: str
    name: str
    round: str
    scheduled_time: str | None
    rows: list[ResultRow]
    raw_heading: str


@dataclass(frozen=True)
class ParsedRace:
    title: str
    venue: str | None
    start_date: date | None
    end_date: date | None
    events: list[EventSection]


def parse_race_ids(value: str | Iterable[str]) -> list[int]:
    """Parse inclusive comma-separated ids and ranges, retaining no duplicates."""
    parts = split_csv(value) if isinstance(value, str) else [part for item in value for part in split_csv(item)]
    ids: set[int] = set()
    for part in parts:
        match = re.fullmatch(r"(\d+)(?:\s*-\s*(\d+))?", part)
        if not match:
            raise ValueError(f"invalid race id/range: {part!r}")
        first, last = int(match.group(1)), int(match.group(2) or match.group(1))
        if last < first:
            raise ValueError(f"race id range ends before it starts: {part!r}")
        ids.update(range(first, last + 1))
    return sorted(ids)


def regattatiming_sync(
    db: DatabaseGateway,
    store: RawStore,
    http: "httpx.Client",
    *,
    race_ids: str | Iterable[str],
    probe_forward: int = 0,
    sleep_ms: int = 2000,
    today: date | None = None,
    sleeper: Callable[[float], None] = time.sleep,
) -> str:
    """Fetch summary pages, falling back to static pages for legacy races."""
    requested = parse_race_ids(race_ids)
    if not requested:
        raise ValueError("at least one race id is required")
    stamp = (today or date.today()).isoformat()
    with IngestRun(
        db,
        job_name="regattatiming_sync",
        source=SOURCE,
        params={"race_ids": requested, "probe_forward": probe_forward, "sleep_ms": sleep_ms},
    ) as run:
        for stat in ("pages_fetched", "pages_missing", "pages_probed", "quarantines"):
            run.add_stat(stat, 0)
        for race_id in requested:
            outcome = _sync_one(db, store, http, run, race_id, stamp)
            if outcome == "blocked":
                return run.id or ""
            _sleep(sleeper, sleep_ms)

        misses = 0
        race_id = max(requested) + 1
        while probe_forward and misses < probe_forward:
            run.add_stat("pages_probed")
            outcome = _sync_one(db, store, http, run, race_id, stamp)
            if outcome == "blocked":
                return run.id or ""
            if outcome == "missing":
                misses += 1
            else:
                misses = 0
            race_id += 1
            _sleep(sleeper, sleep_ms)
    return run.id or ""


def _sync_one(
    db: DatabaseGateway, store: RawStore, http: Any, run: IngestRun, race_id: int, stamp: str
) -> str:
    response = http.get(SUMMARY_URL.format(race_id=race_id))
    if _is_blocked_response(response):
        _quarantine_blocked(db, run, race_id, response)
        return "blocked"
    if response.status_code == 404:
        run.add_stat("pages_missing")
        return "missing"
    response.raise_for_status()
    content = response.content
    kind = "summary"
    if _is_placeholder(content) or not _page_has_event_sections(content):
        fallback = http.get(STATIC_URL.format(race_id=race_id))
        if _is_blocked_response(fallback):
            _quarantine_blocked(db, run, race_id, fallback)
            return "blocked"
        if fallback.status_code == 404:
            run.add_stat("pages_missing")
            return "missing"
        fallback.raise_for_status()
        content, kind = fallback.content, "static"
        if _is_placeholder(content) or not _page_has_event_sections(content):
            run.add_stat("pages_missing")
            return "missing"
    try:
        _stage_page(db, store, run.id or "", race_id, kind, content, stamp)
    except QuarantineableError as exc:
        quarantine(db, run.id or "", SOURCE, str(race_id), "regattatiming_checksum_conflict", details={"error": str(exc)})
        run.add_stat("quarantines")
        return "conflict"
    run.add_stat("pages_fetched")
    return "fetched"


def _stage_page(
    db: DatabaseGateway, store: RawStore, run_id: str, race_id: int, kind: str, content: bytes, stamp: str
) -> None:
    key = f"raw/regattatiming/{kind}/{race_id}/{stamp}.html"
    raw = store.put_raw(key, content, "text/html")
    source_record_id = register_source_record(
        db, source=SOURCE, external_key=str(race_id), raw_object=raw,
        metadata={"race_id": race_id, "page_kind": kind},
    )
    title = _page_title(content)
    db.execute(
        """
        INSERT INTO staging.regattatiming_page
            (ingest_run_id, source_record_id, race_id, page_kind, title)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (race_id) DO UPDATE SET
            ingest_run_id = EXCLUDED.ingest_run_id,
            source_record_id = EXCLUDED.source_record_id,
            page_kind = EXCLUDED.page_kind,
            title = EXCLUDED.title,
            retrieved_at = now()
        """,
        (run_id, source_record_id, race_id, kind, title),
    )


def regattatiming_load(
    db: DatabaseGateway,
    store: RawStore,
    *,
    race_ids: str | Iterable[str],
) -> str:
    """Read staged immutable HTML and insert a fresh results tree when changed.

    The loader reads the raw object through its recorded ``core.source_record``
    URI.  Staging intentionally stores only the provenance pointer, not a second
    mutable copy of the page.
    """
    ids = parse_race_ids(race_ids)
    with IngestRun(db, job_name="regattatiming_load", source=SOURCE, params={"race_ids": ids}) as run:
        for stat in ("races_loaded", "races_unchanged", "events_loaded", "entries_loaded", "results_loaded", "persons_loaded", "clubs_observed", "quarantines"):
            run.add_stat(stat, 0)
        for race_id in ids:
            rows = db.execute(
                """
                SELECT p.race_id, p.source_record_id, s.raw_uri
                FROM staging.regattatiming_page p
                JOIN core.source_record s ON s.id = p.source_record_id
                WHERE p.race_id = %s
                """, (race_id,)
            )
            if not rows:
                run.warn(f"race {race_id}: no staged page")
                continue
            page = rows[0]
            raw_uri = str(page["raw_uri"])
            try:
                parsed = parse_page(store.get_raw(_r2_key(raw_uri)))
                _load_race(db, run, int(page["race_id"]), str(page["source_record_id"]), raw_uri, parsed)
            except ParseShapeError as exc:
                quarantine(db, run.id or "", SOURCE, str(race_id), "regattatiming_parse_shape", raw_uri, {"error": str(exc)})
                run.add_stat("quarantines")
            except TimeParseError as exc:
                quarantine(db, run.id or "", SOURCE, str(race_id), "regattatiming_time_parse", raw_uri, {"error": str(exc)})
                run.add_stat("quarantines")
    return run.id or ""


def parse_page(content: bytes) -> ParsedRace:
    document = html.fromstring(content)
    heroes = document.xpath("//div[@id='hero']")
    if len(heroes) != 1:
        raise ParseShapeError("expected exactly one #hero header")
    hero = heroes[0]
    headings = hero.xpath(".//h4")
    paragraphs = hero.xpath(".//p")
    if len(headings) != 1 or len(paragraphs) < 2:
        raise ParseShapeError("#hero must contain one h4 and location/date paragraphs")
    title = _clean_text(headings[0].text_content())
    venue = _clean_text(paragraphs[0].text_content()) or None
    if not title or not venue:
        raise ParseShapeError("#hero name and location must be non-empty")
    start_date, end_date = _parse_hero_dates(_clean_text(paragraphs[1].text_content()))
    events: list[EventSection] = []
    cards = document.xpath(
        "//div[contains(concat(' ', normalize-space(@class), ' '), ' my-2 ')]"
        "[./div[@data-event-cat-id and @data-event-round]]"
    )
    for card in cards:
        headers = card.xpath("./div[@data-event-cat-id and @data-event-round]")
        tables = card.xpath(".//table")
        if len(headers) != 1 or len(tables) != 1:
            raise ParseShapeError("event card must contain one attributed header and one table")
        header = headers[0]
        links = header.xpath("./a[contains(@href, 'eventId=')]")
        if len(links) != 1:
            raise ParseShapeError("event card header must contain exactly one eventId link")
        event_id = _event_id(links[0].get("href", ""))
        heading_text = _clean_text(links[0].text_content())
        match = EVENT_RE.match(heading_text)
        if event_id is None or not match:
            raise ParseShapeError(f"invalid event card header: {heading_text!r}")
        events.append(_parse_section(event_id, match.group("number"), match.group("body"), heading_text, header.get("data-event-round", ""), tables[0]))
    if not events:
        raise ParseShapeError("no event sections")
    return ParsedRace(title, venue, start_date, end_date, events)


def _parse_section(event_id: str, number: str, body: str, heading: str, declared_round: str, table: Any) -> EventSection:
    header_cells = table.xpath("./thead/tr/th")
    field_names = [cell.get("data-mdb-field") for cell in header_cells]
    if len(header_cells) != 6 or field_names != ["place", "lane", "entry", None, "time", "margin"]:
        raise ParseShapeError(f"{heading!r} does not have the expected six-column RegattaTiming table")
    round_match = ROUND_RE.search(body)
    round_name = round_match.group("round") if round_match else declared_round.strip()
    if not round_name:
        raise ParseShapeError(f"{heading!r} has no round/heat")
    name = body[: round_match.start()].strip() if round_match else body
    time_match = re.search(r"\((\d{1,2}:\d{2})\)", body)
    rows: list[ResultRow] = []
    for tr in table.xpath("./tbody/tr"):
        cell_nodes = tr.xpath("./td")
        cells = [_clean_text(cell.text_content()) for cell in cell_nodes]
        if not any(cells):
            continue
        if len(cells) != 6:
            raise ParseShapeError(f"{heading!r} row has {len(cells)} cells")
        if not cell_nodes[0].xpath(".//span[contains(concat(' ', normalize-space(@class), ' '), ' number ')]"):
            raise ParseShapeError(f"{heading!r} place cell lacks span.number")
        entry_links = cell_nodes[2].xpath(".//a")
        penalty_nodes = cell_nodes[3].xpath("./div[contains(concat(' ', normalize-space(@class), ' '), ' blue-table-text ')] | ./div[contains(concat(' ', normalize-space(@class), ' '), ' red-table-text ')]")
        time_nodes = cell_nodes[4].xpath("./div")
        if len(entry_links) != 1 or len(penalty_nodes) != 2 or len(time_nodes) != 1:
            raise ParseShapeError(f"{heading!r} row does not match the entry/penalty/time cell structure")
        place, lane, _entry_cell, _penalty, finish, margin = cells
        # ``data-mdb-value`` on this cell is a provider template defect; only
        # the nested anchor is the published club/stroke label.
        entry = _clean_text(entry_links[0].text_content())
        status_match = STATUS_RE.search(" ".join(cells))
        status = status_match.group(1).upper() if status_match else "finished"
        club, stroke = _split_entry(entry)
        org_id = tr.get("data-org-id") or cell_nodes[2].xpath("string(.//*[@data-org-id][1])")
        provider_external_key = str(org_id).strip() or _normalized_club_key(club)
        time_ms = None if status != "finished" else parse_time_ms(finish, field="time")
        delta_ms = parse_time_ms(margin.lstrip("+"), field="margin", blank_is_none=True)
        rows.append(ResultRow(_int_or_none(place), _int_or_none(lane), club, provider_external_key, stroke, time_ms, delta_ms, status, {
            # Entry-level raw must never carry athlete names.  The provider's
            # complete anchor label is retained only with result_person below.
            "place": place, "lane": lane, "club": club, "penalty": _penalty, "time": finish, "margin": margin, "data_org_id": str(org_id).strip() or "",
        }, entry if stroke else None))
    return EventSection(event_id, number, name, round_name, time_match.group(1) if time_match else None, rows, heading)


def parse_time_ms(value: str, *, field: str, blank_is_none: bool = False) -> int | None:
    text = value.strip().replace("−", "-")
    if not text or text in {"-", "—", "–"}:
        return None if blank_is_none else _raise_time(value, field)
    match = TIME_RE.fullmatch(text)
    if not match:
        return _raise_time(value, field)
    minutes = int(match.group("minutes") or 0)
    seconds = int(match.group("seconds"))
    if seconds >= 60 and match.group("minutes"):
        return _raise_time(value, field)
    fraction = (match.group("fraction") or "").ljust(3, "0")
    return (minutes * 60 + seconds) * 1000 + int(fraction or 0)


def _raise_time(value: str, field: str) -> None:
    raise TimeParseError(f"invalid {field}: {value!r}")


def _load_race(db: DatabaseGateway, run: IngestRun, race_id: int, source_record_id: str, raw_uri: str, race: ParsedRace) -> None:
    checksum = hashlib.sha256(raw_uri.encode()).hexdigest()
    # The source record owns the raw checksum; selecting it makes an unchanged
    # page a no-op without relying on an unstable HTML serialization.
    rows = db.execute("SELECT checksum_sha256 FROM core.source_record WHERE id = %s", (source_record_id,))
    checksum = str(rows[0]["checksum_sha256"]) if rows else checksum
    latest = db.execute(
        "SELECT id, revision, payload_checksum FROM core.regatta WHERE source = %s AND external_key = %s ORDER BY revision DESC LIMIT 1",
        (SOURCE, str(race_id)),
    )
    if latest and latest[0]["payload_checksum"] == checksum:
        run.add_stat("races_unchanged")
        return
    revision = int(latest[0]["revision"]) + 1 if latest else 1
    regatta_rows = db.execute(
        """INSERT INTO core.regatta (source, external_key, revision, name, start_date, end_date, venue, raw, payload_checksum, source_record_id, parser_version)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s) RETURNING id""",
        (SOURCE, str(race_id), revision, race.title, race.start_date, race.end_date, race.venue,
         json.dumps({"raw_uri": raw_uri}), checksum, source_record_id, PARSER_VERSION),
    )
    regatta_id = str(regatta_rows[0]["id"])
    run.add_stat("races_loaded")
    for event in race.events:
        event_key = f"{event.event_id}:{event.round}"
        event_rows = db.execute(
            """INSERT INTO core.regatta_event (regatta_id, external_key, name, event_code, round, scheduled_at, raw)
               VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb) RETURNING id""",
            (regatta_id, event_key, event.name, event.number, event.round, _scheduled_at(race.start_date, event.scheduled_time), json.dumps({"heading": event.raw_heading})),
        )
        event_id = str(event_rows[0]["id"])
        run.add_stat("events_loaded")
        for row_index, row in enumerate(event.rows, start=1):
            club_id, observed = _provider_club(db, row.club, row.provider_external_key, source_record_id)
            run.add_stat("clubs_observed", observed)
            entry_key = _entry_external_key(event_key, row, row_index)
            entry_rows = db.execute(
                """INSERT INTO core.regatta_entry (event_id, external_key, lane, club_source_name, provider_club_id, raw)
                   VALUES (%s,%s,%s,%s,%s,%s::jsonb) RETURNING id""",
                (event_id, entry_key, row.lane, row.club, club_id, json.dumps(row.raw)),
            )
            entry_id = str(entry_rows[0]["id"])
            run.add_stat("entries_loaded")
            db.execute(
                """INSERT INTO core.regatta_result (entry_id, status, position, time_ms, delta_ms)
                   VALUES (%s,%s,%s,%s,%s)""", (entry_id, row.status, row.position, row.time_ms, row.delta_ms)
            )
            run.add_stat("results_loaded")
            if row.stroke:
                db.execute("INSERT INTO core.result_person (entry_id, role, person_name, raw) VALUES (%s, 'stroke', %s, %s::jsonb)", (entry_id, row.stroke, json.dumps({"entry": row.person_raw_entry})))
                run.add_stat("persons_loaded")


def _provider_club(db: DatabaseGateway, name: str, external_key: str, source_record_id: str) -> tuple[str, int]:
    """Observe the provider's stable organization id, falling back only for legacy pages."""
    key = external_key or _normalized_club_key(name)
    inserted = db.execute(
        """INSERT INTO core.provider_club (source, external_key, display_name, source_record_id)
           VALUES (%s,%s,%s,%s) ON CONFLICT (source, external_key) DO NOTHING RETURNING id""",
        (SOURCE, key, name, source_record_id),
    )
    if inserted:
        return str(inserted[0]["id"]), 1
    rows = db.execute("SELECT id FROM core.provider_club WHERE source = %s AND external_key = %s", (SOURCE, key))
    return str(rows[0]["id"]), 0


def _r2_key(uri: str) -> str:
    parts = uri.split("/", 3)
    if len(parts) != 4 or not uri.startswith("r2://"):
        raise ValueError(f"invalid R2 URI: {uri!r}")
    return parts[3]


def _page_has_event_sections(content: bytes) -> bool:
    try:
        document = html.fromstring(content)
    except (ValueError, TypeError):
        return False
    return bool(document.xpath(
        "//div[contains(concat(' ', normalize-space(@class), ' '), ' my-2 ')]"
        "/div[@data-event-cat-id and @data-event-round]/a[contains(@href, 'eventId=')]"
    ))


def _is_placeholder(content: bytes) -> bool:
    text = _clean_text(content.decode("utf-8", "replace")).lower()
    return not text or "page not found" in text or "no results found" in text


def _is_blocked_response(response: Any) -> bool:
    if response.status_code in {403, 429, 503}:
        return True
    headers = response.headers
    if headers.get("cf-mitigated") or headers.get("cf-chl-bypass"):
        return True
    text = response.content.decode("utf-8", "replace").lower()
    return any(marker in text for marker in (
        "just a moment", "enable javascript and cookies", "/cdn-cgi/", "cf-chl-", "cf-mitigated", "challenge-platform",
    ))


def _quarantine_blocked(db: DatabaseGateway, run: IngestRun, race_id: int, response: Any) -> None:
    quarantine(
        db, run.id or "", SOURCE, str(race_id), "regattatiming_blocked",
        details={"url": str(response.url), "status_code": response.status_code},
    )
    run.add_stat("quarantines")


def _page_title(content: bytes) -> str | None:
    try:
        document = html.fromstring(content)
        return _clean_text(document.xpath("string(//div[@id='hero']//h4[1])")) or _clean_text(document.xpath("string(//title)")) or None
    except (ValueError, TypeError):
        return None


def _split_entry(entry: str) -> tuple[str, str | None]:
    match = re.match(r"^(?P<club>.*?)\s*\((?P<stroke>[^(),]+,\s*[^()]+)\)\s*$", entry)
    return (match.group("club").strip(), match.group("stroke").strip()) if match else (entry, None)


def _normalized_club_key(name: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9\s]", "", name.lower()).split())


def _event_id(href: str) -> str | None:
    match = re.search(r"(?:[?&]|^)eventId=(\d+)(?:[&#]|$)", href)
    return match.group(1) if match else None


def _parse_hero_dates(value: str) -> tuple[date | None, date | None]:
    """Parse the real hero convention, e.g. ``May 30 - Jun 1, 2025``."""
    months = r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?"
    ranged = re.fullmatch(rf"(?P<m1>{months})\s+(?P<d1>\d{{1,2}})\s*-\s*(?P<m2>{months})\s+(?P<d2>\d{{1,2}}),\s*(?P<year>\d{{4}})", value, re.I)
    single = re.fullmatch(rf"(?P<m1>{months})\s+(?P<d1>\d{{1,2}}),\s*(?P<year>\d{{4}})", value, re.I)
    match = ranged or single
    if not match:
        raise ParseShapeError(f"unrecognized #hero date range: {value!r}")
    year = int(match.group("year"))
    start_year = year
    if ranged and _month_number(match.group("m1")) > _month_number(match.group("m2")):
        start_year -= 1
    start = _month_day(start_year, match.group("m1"), int(match.group("d1")))
    end = _month_day(year, match.group("m2") if ranged else match.group("m1"), int(match.group("d2")) if ranged else int(match.group("d1")))
    return start, end


def _month_day(year: int, month: str, day: int) -> date:
    for pattern in ("%B", "%b"):
        try:
            return datetime.strptime(f"{month} {day} {year}", f"{pattern} %d %Y").date()
        except ValueError:
            pass
    raise ParseShapeError(f"invalid #hero date: {month} {day}, {year}")


def _month_number(month: str) -> int:
    return _month_day(2000, month, 1).month


def _dates_from_text(text: str) -> tuple[date | None, date | None]:
    matches = re.findall(
        r"\b(?:\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2}|"
        r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
        r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2},\s*\d{4})\b",
        text,
        re.I,
    )
    parsed: list[date] = []
    for value in matches[:2]:
        try:
            if "-" in value:
                parsed.append(datetime.strptime(value, "%Y-%m-%d").date())
            elif "/" in value:
                parsed.append(datetime.strptime(value, "%m/%d/%Y").date())
            else:
                parsed.append(datetime.strptime(value, "%B %d, %Y").date())
        except ValueError:
            try:
                parsed.append(datetime.strptime(value, "%b %d, %Y").date())
            except ValueError:
                continue
    return (parsed[0], parsed[-1]) if parsed else (None, None)


def _label_value(text: str, label: str) -> str | None:
    match = re.search(rf"\b{re.escape(label)}\s*:\s*([^|\n]+)", text, re.I)
    return match.group(1).strip() if match else None


def _scheduled_at(day: date | None, value: str | None) -> datetime | None:
    if day is None or value is None:
        return None
    match = re.fullmatch(r"(\d{1,2}):(\d{2})", value)
    if not match:
        raise ParseShapeError(f"invalid scheduled time: {value!r}")
    try:
        scheduled_time = clock_time(int(match.group(1)), int(match.group(2)))
    except ValueError as exc:
        raise ParseShapeError(f"invalid scheduled time: {value!r}") from exc
    return datetime.combine(day, scheduled_time, tzinfo=timezone.utc)


def _entry_external_key(event_key: str, row: ResultRow, row_index: int) -> str:
    identity = row.position if row.position is not None else row.lane
    return f"{event_key}:{identity if identity is not None else f'row-{row_index}'}"


def _normalized_header(value: str) -> str:
    return re.sub(r"\s+", " ", _clean_text(value)).lower()


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _int_or_none(value: str) -> int | None:
    match = re.search(r"\d+", value)
    return int(match.group()) if match else None


def _sleep(sleeper: Callable[[float], None], sleep_ms: int) -> None:
    if sleep_ms > 0:
        sleeper(sleep_ms / 1000)


def register(app: Any) -> None:
    """Register commands without coupling this adapter to ``__main__``."""
    import typer

    @app.command(name="regattatiming-sync")
    def sync_cmd(
        race_ids: str = typer.Option(..., "--race-ids"),
        probe_forward: int = typer.Option(0, "--probe-forward"),
        sleep_ms: int = typer.Option(2000, "--sleep-ms"),
    ) -> None:
        with job_context() as (db, store, http):
            typer.echo(regattatiming_sync(db, store, http, race_ids=race_ids, probe_forward=probe_forward, sleep_ms=sleep_ms))

    @app.command(name="regattatiming-load")
    def load_cmd(race_ids: str = typer.Option(..., "--race-ids")) -> None:
        with job_context() as (db, store, _http):
            typer.echo(regattatiming_load(db, store, race_ids=race_ids))


__all__ = ["PARSER_VERSION", "SOURCE", "parse_page", "parse_race_ids", "parse_time_ms", "regattatiming_load", "regattatiming_sync", "register"]
