#!/usr/bin/env python3
"""Download IRS yearly e-file index CSVs (to cache/) and extract cohort rows.

The IRS index columns are:
  RETURN_ID,FILING_TYPE,EIN,TAX_PERIOD,SUB_DATE,TAXPAYER_NAME,RETURN_TYPE,DLN,OBJECT_ID
TAXPAYER_NAME is unquoted and may contain commas, so we parse the 5 leading
fields from the left and the 3 trailing fields (RETURN_TYPE, DLN, OBJECT_ID)
from the right; the name is whatever is in between.

Writes cache/index_matches.csv (year,ein,tax_period,return_type,object_id,name)
and prints a summary. Never cats a whole index file.

Run:  uv run --with httpx spike/fetch_indices.py 2020 2022
"""
import csv
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent))
from cohort import EINS, ALTERNATES

HERE = Path(__file__).parent
CACHE = HERE / "cache"
URL = "https://apps.irs.gov/pub/epostcard/990/xml/{y}/index_{y}.csv"

# cohort EINs plus documented alternates, as integers (index stores no leading zeros)
WANT = {int(e) for e in EINS} | {int(a["ein"]) for a in ALTERNATES}


def download(year: int) -> Path:
    dest = CACHE / f"index_{year}.csv"
    if dest.exists() and dest.stat().st_size > 1_000_000:
        return dest
    CACHE.mkdir(exist_ok=True)
    with httpx.stream("GET", URL.format(y=year), timeout=120,
                      headers={"User-Agent": "crewgraphs-spike/0 (research; polite)"}) as r:
        r.raise_for_status()
        with open(dest, "wb") as fh:
            for chunk in r.iter_bytes(1 << 20):
                fh.write(chunk)
    return dest


def scan(year: int, path: Path):
    rows = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        header = fh.readline()  # skip
        for line in fh:
            parts = line.rstrip("\n").split(",")
            if len(parts) < 9:
                continue
            try:
                ein = int(parts[2])
            except ValueError:
                continue
            if ein not in WANT:
                continue
            object_id = parts[-1].strip()
            dln = parts[-2].strip()
            return_type = parts[-3].strip()
            tax_period = parts[3].strip()
            name = ",".join(parts[5:-3]).strip()
            rows.append((year, ein, tax_period, return_type, object_id, name))
    return rows


def main():
    years = [int(a) for a in sys.argv[1:]] or [2020, 2022]
    all_rows = []
    for y in years:
        p = download(y)
        mb = p.stat().st_size / 1048576
        rows = scan(y, p)
        print(f"index_{y}.csv ({mb:.1f} MB): {len(rows)} cohort rows")
        for r in rows:
            print(f"    EIN {r[1]:>10} taxprd={r[2]} {r[3]:>6} obj={r[4]} {r[5][:30]}")
        all_rows.extend(rows)
        time.sleep(1.0)

    out = CACHE / "index_matches.csv"
    # merge with any existing matches from prior years
    existing = []
    if out.exists():
        with open(out) as fh:
            existing = [tuple(row) for row in csv.reader(fh)][1:]
    seen = {(str(r[0]), str(r[1]), r[2], r[3], r[4]) for r in existing}
    with open(out, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["year", "ein", "tax_period", "return_type", "object_id", "name"])
        for r in existing:
            w.writerow(r)
        for r in all_rows:
            key = (str(r[0]), str(r[1]), r[2], r[3], r[4])
            if key not in seen:
                seen.add(key)
                w.writerow(r)
    print(f"-> wrote {out}")


if __name__ == "__main__":
    main()
