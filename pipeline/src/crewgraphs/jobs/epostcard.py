"""Acquire and stage the IRS Form 990-N (e-Postcard) bulk download."""

from __future__ import annotations

import csv
import json
import mmap
import tempfile
import zipfile
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Iterator

from ..db import DatabaseGateway
from ..quarantine import quarantine
from ..raw_store import QuarantineableError, RawStore, register_source_record
from ..runlog import IngestRun
from . import is_discovery_name, normalized_ein, verified_irs_eins
from .bmf import _recoverable_acquisition_error

if TYPE_CHECKING:
    import httpx


SOURCE = "irs_990n"
URL = "https://apps.irs.gov/pub/epostcard/data-download-epostcard.zip"

# IRS's 990-N data dictionary has no filing-date column.  The observation uses
# positions 0 (EIN), 1 (tax year), 2 (organization name), 5 (period begin), and
# 6 (period end), retaining the rest in raw_payload.  Accordingly filing_date
# is NULL rather than inferred from the retrieval date.
FIELD_NAMES = (
    "EIN", "TAX_YEAR", "ORGANIZATION_NAME", "GROSS_RECEIPTS_NOT_GREATER_THAN",
    "ORGANIZATION_HAS_TERMINATED", "TAX_PERIOD_BEGIN_DATE", "TAX_PERIOD_END_DATE",
    "WEBSITE_URL", "PRINCIPAL_OFFICER_NAME", "PRINCIPAL_OFFICER_ADDRESS_LINE_1",
    "PRINCIPAL_OFFICER_ADDRESS_LINE_2", "PRINCIPAL_OFFICER_CITY",
    "PRINCIPAL_OFFICER_PROVINCE", "PRINCIPAL_OFFICER_STATE",
    "PRINCIPAL_OFFICER_ZIP_CODE", "PRINCIPAL_OFFICER_COUNTRY",
    "MAILING_ADDRESS_LINE_1", "MAILING_ADDRESS_LINE_2", "MAILING_CITY",
    "MAILING_PROVINCE", "MAILING_STATE", "MAILING_ZIP_CODE", "MAILING_COUNTRY",
    "DBA_NAME_1", "DBA_NAME_2", "DBA_NAME_3",
)


def epostcard_sync(
    db: DatabaseGateway,
    store: RawStore,
    http: "httpx.Client",
    *,
    watchlist_eins: set[str] | None = None,
    retrieved_date: date | str | None = None,
) -> str:
    """Fetch, write-once-store, and stage the 990-N bulk ZIP.

    The HTTP body is copied chunk-by-chunk into a temporary file.  A read-only
    mmap lets ``RawStore.put_raw`` hash/upload the ZIP without materializing the
    roughly 90 MB archive as a Python bytes object.  Acquisition failures are
    quarantined and reported as a successful run with warnings.
    """
    watchlist = (
        {ein for value in watchlist_eins if (ein := normalized_ein(value))}
        if watchlist_eins is not None
        else verified_irs_eins(db)
    )
    retrieval = _as_date(retrieved_date)
    raw_key = f"raw/irs/990n/{retrieval.isoformat()}/data-download-epostcard.zip"
    with IngestRun(
        db,
        job_name="epostcard_sync",
        source=SOURCE,
        params={"retrieved_date": retrieval.isoformat()},
    ) as run:
        for stat in (
            "files_fetched",
            "rows_seen",
            "rows_kept",
            "observations_inserted",
            "quarantines",
        ):
            run.add_stat(stat, 0)
        try:
            with tempfile.NamedTemporaryFile(suffix=".zip") as temporary:
                _download_to_file(http, temporary)
                temporary.flush()
                temporary.seek(0)
                # Do not close this mmap explicitly: a real S3 client consumes
                # it synchronously, while simple dict-backed test clients retain
                # their Body object.  In the former case it is released when the
                # local reference drops; in the latter the fake owns its copy of
                # the handle just as it owns a bytes Body.
                archive = mmap.mmap(temporary.fileno(), 0, access=mmap.ACCESS_READ)
                raw_object = store.put_raw(
                    raw_key, archive, "application/zip"  # type: ignore[arg-type]
                )
                source_record_id = register_source_record(
                    db,
                    source=SOURCE,
                    external_key=URL,
                    raw_object=raw_object,
                    metadata={"retrieved_date": retrieval.isoformat()},
                )
                run.add_stat("files_fetched")
                _stage_archive(
                    db,
                    run=run,
                    source_record_id=source_record_id,
                    archive_path=Path(temporary.name),
                    watchlist=watchlist,
                )
        except Exception as exc:
            if not _recoverable_acquisition_error(exc) and not isinstance(exc, zipfile.BadZipFile):
                raise
            quarantine(
                db, run.id or "", SOURCE, URL, str(exc),
                f"r2://{store.bucket}/{raw_key}",
            )
            run.add_stat("quarantines")
            run.warn(str(exc))
    return run.id or ""


def _download_to_file(http: "httpx.Client", destination: object) -> None:
    with http.stream("GET", URL) as response:
        response.raise_for_status()
        for chunk in response.iter_bytes():
            destination.write(chunk)  # type: ignore[attr-defined]


def _stage_archive(
    db: DatabaseGateway,
    *,
    run: IngestRun,
    source_record_id: str,
    archive_path: Path,
    watchlist: set[str],
) -> None:
    db.execute(
        "DELETE FROM staging.epostcard_row WHERE ingest_run_id = %s AND source_record_id = %s",
        (run.id, source_record_id),
    )
    with zipfile.ZipFile(archive_path) as archive:
        for fields in _postcard_rows(archive):
            run.add_stat("rows_seen")
            raw_row = dict(zip(FIELD_NAMES, fields, strict=False))
            raw_row["_extra_fields"] = fields[len(FIELD_NAMES):]
            ein = normalized_ein(raw_row.get("EIN"))
            name = raw_row.get("ORGANIZATION_NAME", "")
            if ein not in watchlist and not is_discovery_name(name):
                continue
            tax_year = _as_tax_year(raw_row.get("TAX_YEAR"))
            if ein is None or tax_year is None:
                run.warn("skipped kept 990-N row with invalid EIN or tax year")
                continue
            run.add_stat("rows_kept")
            payload = json.dumps(raw_row)
            db.execute(
                """
                INSERT INTO staging.epostcard_row
                    (ingest_run_id, source_record_id, ein, raw_row)
                VALUES (%s, %s, %s, %s::jsonb)
                """,
                (run.id, source_record_id, ein, payload),
            )
            inserted = db.execute(
                """
                INSERT INTO core.epostcard_observation
                    (source_record_id, ein, tax_year, tax_period_end, filing_date, raw_payload)
                VALUES (%s, %s, %s, %s, NULL, %s::jsonb)
                ON CONFLICT (ein, tax_year, source_record_id) DO NOTHING
                RETURNING id
                """,
                (
                    source_record_id, ein, tax_year,
                    _as_irs_date(raw_row.get("TAX_PERIOD_END_DATE")), payload,
                ),
            )
            if inserted:
                run.add_stat("observations_inserted")


def _postcard_rows(archive: zipfile.ZipFile) -> Iterator[list[str]]:
    for info in archive.infolist():
        if info.is_dir():
            continue
        with archive.open(info) as binary_file:
            lines = (line.decode("utf-8-sig").rstrip("\r\n") for line in binary_file)
            yield from csv.reader(lines, delimiter="|")


def _as_date(value: date | str | None) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        return date.fromisoformat(value)
    return date.today()


def _as_tax_year(value: object) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _as_irs_date(value: object) -> date | None:
    try:
        month, day, year = str(value).split("-")
        return date.fromisoformat(f"{year}-{month}-{day}")
    except (TypeError, ValueError):
        return None
