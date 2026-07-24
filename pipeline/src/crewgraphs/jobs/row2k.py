"""row2k results-directory discovery registry (facts and links only)."""

from __future__ import annotations

import re
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING, TextIO
from urllib.parse import parse_qs, urljoin, urlparse

from lxml import html

from crewgraphs.runtime import job_context, split_csv

from ..config import Settings
from ..db import DatabaseGateway, PostgresGateway
from ..quarantine import quarantine
from ..raw_store import RawStore, register_source_record
from ..runlog import IngestRun

if TYPE_CHECKING:
    import httpx


SOURCE = "row2k"
RESULTS_URL = "https://www.row2k.com/results/"
_DATE_FORMATS = ("%B %d, %Y", "%b %d, %Y")
_DATE_RE = re.compile(
    r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)?\s*,?\s*"
    r"([A-Za-z]+\s+\d{1,2})(?:\s*(?:-|–|—|to)\s*"
    r"(?:(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s*,?\s*)?"
    r"(?:[A-Za-z]+\s+)?\d{1,2})?"
    r"\s*,\s*(\d{4})",
    re.IGNORECASE,
)
_CATEGORY_MARKERS = (
    "JUNIOR",
    "MASTERS",
    "COLLEGIATE",
    "HIGH SCHOOL",
    "SCHOLASTIC",
    "OPEN",
    "ADAPTIVE",
)
_HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}


@dataclass(frozen=True, slots=True)
class RegistryLink:
    """A row2k directory observation, deliberately excluding result content."""

    regatta_name: str
    event_date: date | None
    category: str | None
    location: str | None
    outbound_url: str
    outbound_host: str
    provider: str | None


def parse_years(value: str) -> list[int]:
    """Expand a comma-separated set of years and inclusive year ranges."""
    years: set[int] = set()
    for item in split_csv(value):
        match = re.fullmatch(r"(\d{4})\s*-\s*(\d{4})", item)
        if match:
            start, end = (int(part) for part in match.groups())
            if end < start:
                raise ValueError(f"invalid descending year range: {item}")
            years.update(range(start, end + 1))
            continue
        if not re.fullmatch(r"\d{4}", item):
            raise ValueError(f"invalid year: {item}")
        years.add(int(item))
    if not years:
        raise ValueError("at least one year is required")
    return sorted(years)


def row2k_index_sync(
    db: DatabaseGateway,
    store: RawStore,
    http: "httpx.Client",
    *,
    years: Iterable[int],
    sleep_ms: int = 3000,
    retrieved_date: date | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> str:
    """Fetch row2k directories and write only discovery facts and links.

    The current directory is fetched first because it advertises the archive URL
    shape. A 403 is an intentional, clean stop: it is recorded as a quarantine
    and the job never retries or changes the user agent.
    """
    requested = sorted(set(years))
    if not requested:
        raise ValueError("at least one year is required")
    if sleep_ms < 0:
        raise ValueError("sleep_ms must be non-negative")
    current_year = (retrieved_date or date.today()).year
    capture_date = retrieved_date or date.today()
    fetched_urls: set[str] = set()

    with IngestRun(
        db,
        job_name="row2k_index_sync",
        source=SOURCE,
        params={"years": requested, "sleep_ms": sleep_ms},
    ) as run:
        for stat in ("pages_fetched", "links_seen", "links_inserted", "quarantines"):
            run.add_stat(stat, 0)

        current = _get_directory(http, RESULTS_URL)
        if current.status_code == 403:
            _record_blocked(db, run, RESULTS_URL)
            run.add_stat("quarantines")
            run.warn("row2k returned HTTP 403; stopped without retrying")
            return run.id or ""
        current.raise_for_status()
        fetched_urls.add(RESULTS_URL)
        archive_urls = discover_archive_urls(current.content, RESULTS_URL)

        # The current directory is also the archive-discovery page. Record it
        # even for a historical-only request: every fetched index page gets an
        # immutable raw/source pointer and exactly one staging row.
        _record_page(
            db,
            store,
            run,
            year=current_year,
            page_url=RESULTS_URL,
            content=current.content,
            capture_date=capture_date,
        )

        for year in requested:
            if year == current_year:
                continue
            page_url = archive_urls.get(year)
            if page_url is None:
                run.warn(f"row2k archive link for {year} was absent from {RESULTS_URL}")
                continue
            if page_url in fetched_urls:
                continue
            sleep(sleep_ms / 1000)
            response = _get_directory(http, page_url)
            if response.status_code == 403:
                _record_blocked(db, run, page_url)
                run.add_stat("quarantines")
                run.warn("row2k returned HTTP 403; stopped without retrying")
                return run.id or ""
            response.raise_for_status()
            fetched_urls.add(page_url)
            _record_page(
                db,
                store,
                run,
                year=year,
                page_url=page_url,
                content=response.content,
                capture_date=capture_date,
            )
    return run.id or ""


def _get_directory(http: "httpx.Client", url: str):
    """Keep request mechanics isolated for small offline HTTP fakes."""
    return http.get(url)


def _record_blocked(db: DatabaseGateway, run: IngestRun, url: str) -> None:
    quarantine(
        db,
        run.id or "",
        SOURCE,
        url,
        "row2k_blocked",
        details={"url": url},
    )


def _record_page(
    db: DatabaseGateway,
    store: RawStore,
    run: IngestRun,
    *,
    year: int,
    page_url: str,
    content: bytes,
    capture_date: date,
) -> None:
    raw_key = f"raw/row2k/results-index/{year}/{capture_date.isoformat()}.html"
    raw_object = store.put_raw(raw_key, content, "text/html")
    source_record_id = register_source_record(
        db,
        source=SOURCE,
        external_key=page_url,
        raw_object=raw_object,
        metadata={"year": year, "url": page_url},
    )
    retrieved_at = datetime.now(timezone.utc)
    db.execute(
        """
        INSERT INTO staging.row2k_index_page
            (ingest_run_id, source_record_id, year, category, retrieved_at)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (run.id, source_record_id, year, None, retrieved_at),
    )
    run.add_stat("pages_fetched")
    for link in parse_directory(content, page_url):
        run.add_stat("links_seen")
        inserted = db.execute(
            """
            INSERT INTO core.regatta_source_link
                (regatta_name, event_date, category, location, outbound_url,
                 outbound_host, provider, credit_url, source_record_id, retrieved_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT ON CONSTRAINT regatta_source_link_event_date_outbound_url_uniq DO NOTHING
            RETURNING id
            """,
            (
                link.regatta_name,
                link.event_date,
                link.category,
                link.location,
                link.outbound_url,
                link.outbound_host,
                link.provider,
                page_url,
                source_record_id,
                retrieved_at,
            ),
        )
        if inserted:
            run.add_stat("links_inserted")


def discover_archive_urls(content: bytes | str, page_url: str = RESULTS_URL) -> dict[int, str]:
    """Read row2k's past-results year selector (with old anchor fallback)."""
    document = _html_document(content)
    page_host = (urlparse(page_url).hostname or "").lower()
    found: dict[int, str] = {}

    # row2k's real archive navigation is a <select name="site">, not a set of
    # anchors. Keep only same-host results-directory options so unrelated form
    # controls cannot become crawl targets.
    for option in document.xpath("//select[translate(@name, 'SITE', 'site') = 'site']//option[@value]"):
        archive_url = urljoin(page_url, str(option.get("value")))
        parsed = urlparse(archive_url)
        year = (parse_qs(parsed.query).get("year") or [None])[0]
        if (
            (parsed.hostname or "").lower() == page_host
            and parsed.path in {"/results/", "/results/index.cfm"}
            and year is not None
            and re.fullmatch(r"(?:19|20)\d{2}", year)
        ):
            found[int(year)] = archive_url

    # Historical fixtures used visible archive anchors. This fallback preserves
    # those variants while production follows the select menu above.
    for anchor in document.xpath("//a[@href]"):
        text = _clean_text(anchor.text_content())
        href = str(anchor.get("href"))
        match = re.fullmatch(r"(?:results\s+)?(19\d{2}|20\d{2})", text, re.IGNORECASE)
        if not match and (urlparse(urljoin(page_url, href)).hostname or "").lower() == page_host:
            # Some archive navigation renders no text around a year but retains
            # it in the query string or pathname.
            match = re.search(r"(?:year=|/)(19\d{2}|20\d{2})(?:\D|$)", href)
        if match:
            found[int(match.group(1))] = urljoin(page_url, href)
    return found


def parse_directory(content: bytes | str, credit_url: str) -> list[RegistryLink]:
    """Extract a row2k directory into registry rows, never result payloads."""
    document = _html_document(content)
    links: list[RegistryLink] = []
    seen: set[tuple[date | None, str]] = set()
    current_date: date | None = None
    current_category: str | None = None

    # The live directory encodes dates as yellow table rows and categories as
    # newscat2 spans. Iterate the DOM in source order so all later listing links
    # inherit the current date/category exactly as readers see the page.
    for element in document.iter():
        if not isinstance(element.tag, str):
            continue
        tag = element.tag.lower()
        if tag == "tr" and str(element.get("bgcolor", "")).lower().lstrip("#") == "ffcc00":
            current_date = parse_heading_date(_clean_text(element.text_content()))
            current_category = None
            continue
        if tag in _HEADING_TAGS:
            heading = _clean_text(element.text_content())
            if heading_date := parse_heading_date(heading):
                current_date = heading_date
                current_category = None
            elif _is_category_heading(heading):
                current_category = heading
            continue
        if tag == "span" and "newscat2" in str(element.get("class", "")).lower().split():
            current_category = _clean_text(element.text_content()) or None
            continue
        if tag != "a" or not element.get("href"):
            continue

        href = urljoin(credit_url, str(element.get("href")))
        if not _is_result_link(
            element,
            href,
            is_listing=current_date is not None and _listing_container(element).tag == "li",
        ):
            continue
        regatta_name, location = _listing_fields(element)
        if not regatta_name:
            continue
        outbound_host = (urlparse(href).hostname or "").lower()
        marker = (current_date, href)
        if marker in seen:
            continue
        seen.add(marker)
        links.append(
            RegistryLink(
                regatta_name=regatta_name,
                event_date=current_date,
                category=current_category,
                location=location,
                outbound_url=href,
                outbound_host=outbound_host,
                provider=provider_from_host(outbound_host),
            )
        )
    return links


def _is_result_link(anchor, href: str, *, is_listing: bool) -> bool:
    parsed = urlparse(href)
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.hostname or "").lower()
    label = _clean_text(anchor.text_content()).lower()
    if "video" in label:
        return False
    if host in {"row2k.com", "www.row2k.com"}:
        return "resultspage.cfm" in parsed.path.lower()
    # Provider-domain links can be titled with the regatta name rather than the
    # words "Live Results", while the latter catches row2k's long tail.
    return provider_from_host(host) is not None or "result" in label or is_listing


def parse_heading_date(value: str) -> date | None:
    """Return the first date of a single- or multi-day directory heading."""
    match = _DATE_RE.search(_clean_text(value))
    if not match:
        return None
    month_day, year = match.groups()
    for form in _DATE_FORMATS:
        try:
            return datetime.strptime(f"{month_day}, {year}", form).date()
        except ValueError:
            pass
    return None


def _is_category_heading(value: str) -> bool:
    upper = value.upper()
    return any(marker in upper for marker in _CATEGORY_MARKERS) and len(value) <= 80


def _listing_fields(anchor) -> tuple[str, str | None]:
    anchor_name = _strip_result_label(_clean_text(anchor.text_content()))
    tail_location = _location_from_tail(_listing_tail(anchor))
    if anchor_name and tail_location:
        return anchor_name, tail_location

    container = _listing_container(anchor)
    text = _clean_text(container.text_content())
    # Remove action labels while preserving ordinary event-name anchors.
    text = re.sub(r"\b(?:live\s+)?results?\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\blive\s+video(?:\s+feed)?\b", "", text, flags=re.IGNORECASE)
    text = _clean_text(re.sub(r"\s*\|\s*", " | ", text).strip(" |–—-"))
    location_match = re.search(r"\b(?:location|venue)\s*:\s*([^|]+)", text, re.IGNORECASE)
    if location_match:
        location = _clean_text(location_match.group(1).strip(" -–—"))
        name = _clean_text(text[: location_match.start()].strip(" |–—-"))
        return name, location or None

    parts = [
        _clean_text(part.strip())
        for part in re.split(r"\s*(?:\||\s+[–—]\s+)\s*", text)
        if _clean_text(part.strip())
    ]
    if len(parts) >= 2 and _looks_like_location(parts[-1]):
        return " — ".join(parts[:-1]), parts[-1]
    return text, None


def _strip_result_label(value: str) -> str:
    return _clean_text(
        re.sub(r"\s*(?:[-|]\s*)?(?:live\s+)?results?\s*$", "", value, flags=re.IGNORECASE)
    )


def _location_from_tail(value: str) -> str | None:
    location = _clean_text(value).strip(" ,|–—-")
    return location if _looks_like_location(location) else None


def _listing_tail(anchor) -> str:
    """Return the text following a result link, including a video-link tail.

    row2k commonly writes ``result link | Live Video Feed - City, ST``. The
    location belongs to the result listing, even though it follows the video
    anchor rather than the results anchor itself.
    """
    tail = anchor.tail or ""
    for sibling in anchor.xpath("following-sibling::a"):
        if "video" in _clean_text(sibling.text_content()).lower():
            tail += sibling.tail or ""
            break
    return tail


def _listing_container(anchor):
    current = anchor
    for _ in range(5):
        current = current.getparent()
        if current is None:
            break
        if current.tag in {"li", "tr", "p"}:
            return current
        class_name = str(current.get("class", "")).lower()
        if any(marker in class_name for marker in ("listing", "result", "event", "regatta")):
            return current
    parent = anchor.getparent()
    return parent if parent is not None else anchor


def _looks_like_location(value: str) -> bool:
    return bool(
        re.search(r",\s*(?:[A-Z]{2}|[A-Za-z .'-]+)$", value)
        or re.search(r"\b[A-Z]{2}$", value)
        or re.search(r"\b(?:USA|Canada|UK)\b", value, re.IGNORECASE)
    )


def _clean_text(value: str) -> str:
    return " ".join(value.split())


def _html_document(content: bytes | str):
    # row2k pages are HTML; decoding bytes ourselves avoids lxml's Latin-1
    # fallback turning an em dash in a location tail into mojibake.
    if isinstance(content, bytes):
        content = content.decode("utf-8", errors="replace")
    return html.fromstring(content)


def provider_from_host(host: str) -> str | None:
    """Map directory hosts to the source types used by provider adapters."""
    normalized = host.lower().removeprefix("www.")
    if normalized in {"usrowing.regatta.time-team.com", "regatta.time-team.nl"} or normalized.endswith(".time-team.com"):
        return "time_team"
    if normalized in {"legacy.herenow.com", "herenow.com", "bigresults.herenow.com"}:
        return "herenow"
    if normalized == "crewtimer.com":
        return "crewtimer"
    if normalized == "results.regattatiming.com":
        return "regattatiming"
    return None


def provider_key(outbound_url: str, provider: str | None = None) -> str | None:
    """Parse the provider-native regatta key represented by a registry URL."""
    parsed = urlparse(outbound_url)
    source = provider or provider_from_host(parsed.hostname or "")
    if source == "herenow":
        match = re.search(r"(?:^|/)races/(\d+)(?:/|$)", parsed.fragment)
        return match.group(1) if match else None
    if source == "time_team":
        match = re.search(r"^/([^/]+)/((?:19|20)\d{2})(?:/|$)", parsed.path)
        return f"{match.group(1)}/{match.group(2)}" if match else None
    if source == "crewtimer":
        match = re.search(r"/regatta/(r\d+)(?:/|$)", parsed.path, re.IGNORECASE)
        return match.group(1).lower() if match else None
    if source == "regattatiming":
        values = parse_qs(parsed.query).get("raceId") or parse_qs(parsed.query).get("raceid")
        return values[0] if values else None
    return None


def results_gap_report(db: DatabaseGateway, *, stdout: TextIO | None = None) -> str:
    """Print row2k registry coverage by provider and event year."""
    output = stdout
    with IngestRun(db, job_name="results_gap_report", source=SOURCE) as run:
        rows = db.execute(GAP_REPORT_SQL)
        run.add_stat("covered", 0)
        run.add_stat("uncovered", 0)
        run.add_stat("provider_year_rows", len(rows))
        lines = ["provider\tyear\tcovered\tuncovered"]
        for row in rows:
            covered = int(row["covered"])
            uncovered = int(row["uncovered"])
            run.add_stat("covered", covered)
            run.add_stat("uncovered", uncovered)
            lines.append(f"{row['provider']}\t{row['year']}\t{covered}\t{uncovered}")
        report = "\n".join(lines)
        if output is not None:
            output.write(report + "\n")
    return report


# Keep these URL regexes semantically aligned with provider_key(): HereNow's
# fragment race ID; Time-Team's slug/year path; CrewTimer's r-id; and
# RegattaTiming's raceId query parameter. The DISTINCT relation prevents a
# historical regatta revision from multiplying a coverage count.
GAP_REPORT_SQL = """
            WITH registry AS (
              SELECT
                provider::text AS provider,
                EXTRACT(YEAR FROM event_date)::integer AS year,
                outbound_url,
                CASE
                  WHEN provider = 'herenow' THEN
                    substring(outbound_url FROM '#/races/([0-9]+)')
                  WHEN provider = 'time_team' THEN
                    substring(outbound_url FROM 'https?://[^/]+/([^/]+/(?:19|20)[0-9]{2})(?:/|$)')
                  WHEN provider = 'crewtimer' THEN
                    lower(substring(outbound_url FROM '/regatta/(r[0-9]+)(?:/|$)'))
                  WHEN provider = 'regattatiming' THEN
                    substring(outbound_url FROM '[?&]raceId=([^&]+)')
                END AS external_key
              FROM core.regatta_source_link
              WHERE provider IS NOT NULL AND event_date IS NOT NULL
            )
            SELECT
              registry.provider,
              registry.year,
              count(*) FILTER (WHERE registry.external_key IS NOT NULL AND existing_regatta.external_key IS NOT NULL)::integer AS covered,
              count(*) FILTER (WHERE registry.external_key IS NULL OR existing_regatta.external_key IS NULL)::integer AS uncovered
            FROM registry
            LEFT JOIN (
              SELECT DISTINCT source, external_key
              FROM core.regatta
            ) AS existing_regatta
              ON existing_regatta.source::text = registry.provider
             AND existing_regatta.external_key = registry.external_key
            GROUP BY registry.provider, registry.year
            ORDER BY registry.provider, registry.year
            """


def register(app) -> None:
    """Attach row2k commands without coupling this adapter to ``__main__``."""
    import typer

    @app.command(name="row2k-index-sync")
    def row2k_index_sync_cmd(
        years: str = typer.Option("1997-2026", help="Years/ranges, e.g. 1997-2026 or 2024,2026"),
        sleep_ms: int = typer.Option(3000, help="Polite delay between directory requests"),
        user_agent: str = typer.Option("", help="Explicit operator user-agent override"),
    ) -> None:
        """Register row2k directory facts and outbound timing-provider links."""
        with job_context() as (db, store, http):
            if user_agent:
                http.headers["User-Agent"] = user_agent
            row2k_index_sync(
                db,
                store,
                http,
                years=parse_years(years),
                sleep_ms=sleep_ms,
            )

    @app.command(name="results-gap-report")
    def results_gap_report_cmd() -> None:
        """Show provider/year registry links that do or do not have a core regatta."""
        import sys

        settings = Settings.from_env()
        db = PostgresGateway(settings.database_url)
        try:
            results_gap_report(db, stdout=sys.stdout)
        finally:
            db.close()


__all__ = [
    "RegistryLink",
    "GAP_REPORT_SQL",
    "SOURCE",
    "discover_archive_urls",
    "parse_directory",
    "parse_heading_date",
    "parse_years",
    "provider_from_host",
    "provider_key",
    "register",
    "results_gap_report",
    "row2k_index_sync",
]
