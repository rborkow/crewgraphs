#!/usr/bin/env python3
"""Fetch ProPublica Nonprofit Explorer org JSON for the cohort.

Saves output/{ein}/propublica.json and prints a per-org coverage summary
(data years, form types, filings-without-data, latest_object_id).

Run:  uv run --with httpx spike/fetch_propublica.py
"""
import json
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent))
from cohort import COHORT

HERE = Path(__file__).parent
OUT = HERE / "output"
API = "https://projects.propublica.org/nonprofits/api/v2/organizations/{ein}.json"
FORMTYPE = {0: "990", 1: "990EZ", 2: "990PF"}


def fetch(ein: str) -> dict:
    r = httpx.get(API.format(ein=int(ein)), timeout=30,
                  headers={"User-Agent": "crewgraphs-spike/0 (research; polite)"})
    r.raise_for_status()
    return r.json()


def main():
    OUT.mkdir(exist_ok=True)
    for o in COHORT:
        ein = o["ein"]
        d = fetch(ein)
        odir = OUT / ein
        odir.mkdir(exist_ok=True)
        (odir / "propublica.json").write_text(json.dumps(d, indent=2))

        org = d.get("organization", {})
        fwd = d.get("filings_with_data", [])
        fwo = d.get("filings_without_data", [])
        yrs = sorted({f["tax_prd_yr"] for f in fwd})
        forms = sorted({FORMTYPE.get(f["formtype"], str(f["formtype"])) for f in fwd})
        wo_forms = sorted({x.get("formtype_str") for x in fwo if x.get("formtype_str")})
        print(f"[{o['slot']:>2}] {org.get('name','?')[:38]:38} EIN {ein} "
              f"sub={org.get('subsection_code')} ntee={org.get('ntee_code')}")
        print(f"       city={org.get('city')},{org.get('state')} "
              f"latest_object_id={org.get('latest_object_id')}")
        print(f"       data_yrs={yrs} forms={forms} | wo_data={len(fwo)} wo_forms={wo_forms}")
        time.sleep(1.1)


if __name__ == "__main__":
    main()
