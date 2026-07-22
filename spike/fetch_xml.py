#!/usr/bin/env python3
"""Fetch e-file 990/990-EZ XML from the GivingTuesday 990 data lake.

Source pattern (anonymous):
  https://gt990datalake-rawdata.s3.amazonaws.com/EfileData/XmlFiles/{OBJECT_ID}_public.xml

Candidate object_ids come from two places:
  * cache/index_matches.csv  (IRS yearly indices -> older years)
  * each output/{ein}/propublica.json latest_object_id  (newest filing)

Per EIN we keep 990/990EZ only (drop 990T/990PF), dedupe, and select a spread:
newest filing + up to two older filings from distinct tax years (max 3).

Saves output/{ein}/{object_id}.xml and output/{ein}/filings_index.json.

Run:  uv run --with httpx spike/fetch_xml.py
"""
import csv
import json
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent))
from cohort import COHORT, ALTERNATES

HERE = Path(__file__).parent
OUT = HERE / "output"
CACHE = HERE / "cache"
XML_URL = "https://gt990datalake-rawdata.s3.amazonaws.com/EfileData/XmlFiles/{oid}_public.xml"
KEEP = {"990", "990EZ"}


def load_candidates():
    """ein -> list of dict(object_id, tax_period, return_type, source)."""
    cand = {}
    # from IRS index matches
    mp = CACHE / "index_matches.csv"
    if mp.exists():
        with open(mp) as fh:
            for row in csv.DictReader(fh):
                if row["return_type"] not in KEEP:
                    continue
                ein = str(int(row["ein"])).zfill(9)
                cand.setdefault(ein, []).append(dict(
                    object_id=row["object_id"], tax_period=row["tax_period"],
                    return_type=row["return_type"], source=f"index_{row['year']}"))
    # from ProPublica latest_object_id
    ft = {0: "990", 1: "990EZ", 2: "990PF"}
    for odir in OUT.iterdir():
        pj = odir / "propublica.json"
        if not pj.exists():
            continue
        d = json.loads(pj.read_text())
        o = d.get("organization", {})
        oid = o.get("latest_object_id")
        if not oid:
            continue
        ein = str(o["ein"]).zfill(9)
        fwd = d.get("filings_with_data", [])
        rt, tp = "990", ""
        if fwd:
            latest = max(fwd, key=lambda f: f["tax_prd"])
            rt = ft.get(latest["formtype"], "990")
            tp = str(latest["tax_prd"])
        if rt in KEEP:
            cand.setdefault(ein, []).append(dict(
                object_id=str(oid), tax_period=tp, return_type=rt, source="propublica_latest"))
    return cand


def ordered_candidates(items):
    """distinct-tax-year candidates, newest first (prefer 1 per tax year)."""
    by_oid = {}
    for it in items:
        by_oid.setdefault(it["object_id"], it)
    uniq = list(by_oid.values())
    uniq.sort(key=lambda x: (x["tax_period"] or "0"), reverse=True)
    primary, extra, years = [], [], set()
    for it in uniq:
        y = (it["tax_period"] or "0")[:4]
        (primary if y not in years else extra).append(it)
        years.add(y)
    return primary + extra  # try distinct years first, then extras as backfill


def fetch(oid: str, dest: Path):
    """returns (bytes, cached_bool) or None on 404."""
    if dest.exists() and dest.stat().st_size > 0:
        return dest.stat().st_size, True
    r = httpx.get(XML_URL.format(oid=oid), timeout=60,
                  headers={"User-Agent": "crewgraphs-spike/0 (research; polite)"})
    if r.status_code == 404:
        return None
    r.raise_for_status()
    dest.write_bytes(r.content)
    return len(r.content), False


def main():
    label = {o["ein"]: o["racing_name"] for o in COHORT}
    label.update({a["ein"]: a["legal_name"] for a in ALTERNATES})
    cand = load_candidates()
    total_bytes, total_files, misses = 0, 0, []
    for ein in sorted(cand):
        odir = OUT / ein
        odir.mkdir(exist_ok=True)
        recorded, got = [], 0
        for it in ordered_candidates(cand[ein]):
            if got >= 3:
                break
            dest = odir / f"{it['object_id']}.xml"
            res = fetch(it["object_id"], dest)
            if res is None:
                misses.append((ein, it["object_id"], it["tax_period"], it["source"]))
                print(f"  {ein} {label.get(ein,'?')[:24]:24} taxprd={it['tax_period']:>6} "
                      f"MISS(404 in GT lake) {it['object_id']} [{it['source']}]")
                time.sleep(0.5)
                continue
            n, cached = res
            got += 1
            total_files += 1
            if not cached:
                total_bytes += n
            recorded.append({**it, "file": dest.name, "bytes": n, "gt_lake": "present"})
            print(f"  {ein} {label.get(ein,'?')[:24]:24} taxprd={it['tax_period']:>6} "
                  f"{it['return_type']:>6} {it['source']:>18} {n:>7}B {it['object_id']}"
                  + (" [cached]" if cached else ""))
            if not cached:
                time.sleep(0.7)
        (odir / "filings_index.json").write_text(json.dumps(recorded, indent=2))
    print(f"\nfetched {total_files} XML files, ~{total_bytes/1024:.0f} KB downloaded this run")
    if misses:
        print(f"GT-lake 404 misses ({len(misses)}): newest filings not yet mirrored:")
        for m in misses:
            print(f"    EIN {m[0]} obj {m[1]} taxprd={m[2]} [{m[3]}]")


if __name__ == "__main__":
    main()
