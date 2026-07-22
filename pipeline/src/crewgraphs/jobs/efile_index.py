"""Synchronize IRS annual e-file indexes into immutable raw storage and staging."""

from __future__ import annotations

import csv
import json
import os
import tempfile
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..db import DatabaseGateway
from ..raw_store import RawStore, register_source_record
from ..runlog import IngestRun


IRS_INDEX_URL = "https://apps.irs.gov/pub/epostcard/990/xml/{year}/index_{year}.csv"
KEEP_RETURN_TYPES = frozenset({"990", "990EZ"})


def efile_index_sync(
    db: DatabaseGateway,
    store: RawStore,
    http: Any,
    *,
    years: list[int],
    watchlist_eins: Iterable[str | int] | None = None,
) -> dict[str, Any]:
    """Download, preserve, and stage watchlist 990/990-EZ index rows.

    IRS indexes contain unquoted taxpayer names with commas.  Rows are therefore
    reconstructed from five stable leading fields and the stable trailing fields,
    rather than trusting a conventional CSV field count.
    """
    watchlist = (
        {_normalise_ein(ein) for ein in watchlist_eins}
        if watchlist_eins is not None
        else None
    )
    retrieved_date = datetime.now(UTC).date().isoformat()

    with IngestRun(
        db,
        job_name="efile_index_sync",
        source="irs",
        params={"years": years, "watchlist_eins": sorted(watchlist or [])},
    ) as run:
        for year in years:
            url = IRS_INDEX_URL.format(year=year)
            temp_path = _stream_to_tempfile(http, url)
            try:
                content = temp_path.read_bytes()
                key = f"raw/irs/efile-index/{year}/{retrieved_date}_index.csv"
                raw = store.put_raw(key, content, "text/csv")
                source_record_id = register_source_record(
                    db,
                    source="irs_efile_index",
                    external_key=str(year),
                    raw_object=raw,
                    metadata={"retrieved_date": retrieved_date, "url": url},
                )
                for row in _index_rows(temp_path):
                    run.add_stat("rows_seen")
                    ein = _normalise_ein(row.get("EIN", ""))
                    if watchlist is not None and ein not in watchlist:
                        continue
                    return_type = row.get("RETURN_TYPE", "").strip().upper()
                    if return_type == "990T":
                        run.add_stat("dropped_990t")
                        continue
                    if return_type not in KEEP_RETURN_TYPES:
                        continue
                    object_id = row.get("OBJECT_ID", "").strip()
                    if not object_id:
                        continue
                    batch_id = row.get("XML_BATCH_ID", "").strip()
                    row["EIN"] = ein
                    row["RETURN_TYPE"] = return_type
                    row.setdefault("XML_BATCH_ID", batch_id)
                    inserted = db.execute(
                        """
                        INSERT INTO staging.efile_index_row
                            (ingest_run_id, source_record_id, tax_year, ein,
                             irs_object_id, xml_batch_id, raw_row)
                        SELECT %s, %s, %s, %s, %s, %s, %s::jsonb
                        WHERE NOT EXISTS (
                            SELECT 1 FROM staging.efile_index_row AS existing
                            WHERE existing.tax_year = %s
                              AND existing.irs_object_id = %s
                        )
                        ON CONFLICT DO NOTHING
                        RETURNING irs_object_id
                        """,
                        (
                            run.id,
                            source_record_id,
                            year,
                            ein,
                            object_id,
                            batch_id,
                            json.dumps(row),
                            year,
                            object_id,
                        ),
                    )
                    run.add_stat("rows_kept")
                    if inserted:
                        run.add_stat("new_object_ids")
            finally:
                temp_path.unlink(missing_ok=True)
    return run.stats


def _stream_to_tempfile(http: Any, url: str) -> Path:
    """Stream an index to disk so the 50--90 MB response is never buffered."""
    descriptor, filename = tempfile.mkstemp(prefix="crewgraphs-index-", suffix=".csv")
    os.close(descriptor)
    path = Path(filename)
    try:
        with http.stream("GET", url, timeout=120) as response:
            response.raise_for_status()
            with path.open("wb") as output:
                for chunk in response.iter_bytes(1 << 20):
                    output.write(chunk)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return path


def _index_rows(path: Path) -> Iterable[dict[str, str]]:
    """Yield physical IRS index rows, including indexes without XML_BATCH_ID."""
    with path.open(encoding="utf-8-sig", errors="replace", newline="") as source:
        header = next(csv.reader([source.readline()]), [])
        if not header or "TAXPAYER_NAME" not in header:
            raise ValueError("IRS e-file index has no TAXPAYER_NAME header")
        name_position = header.index("TAXPAYER_NAME")
        trailing = header[name_position + 1 :]
        if header[:name_position] != [
            "RETURN_ID",
            "FILING_TYPE",
            "EIN",
            "TAX_PERIOD",
            "SUB_DATE",
        ]:
            raise ValueError("IRS e-file index has an unexpected leading header")
        for line in source:
            parts = next(csv.reader([line]), [])
            if len(parts) < name_position + 1 + len(trailing):
                continue
            row = dict(zip(header[:name_position], parts[:name_position], strict=True))
            tail_start = len(parts) - len(trailing)
            row["TAXPAYER_NAME"] = ",".join(parts[name_position:tail_start]).strip()
            row.update(zip(trailing, parts[tail_start:], strict=True))
            yield row


def _normalise_ein(value: str | int) -> str:
    digits = "".join(character for character in str(value) if character.isdigit())
    return digits.zfill(9) if digits else ""


__all__ = ["IRS_INDEX_URL", "efile_index_sync"]
