#!/usr/bin/env python3
"""Build output/orgs.csv from cohort.py + saved ProPublica/parsed data.

Columns: org, ein, legal_name, city, state, ntee, form_types_seen,
         xml_years, match_confidence, notes

Run:  uv run python3 spike/build_orgs_csv.py
"""
import csv
import glob
import json
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "output"
import sys
sys.path.insert(0, str(HERE))
from cohort import COHORT

FT = {0: "990", 1: "990EZ", 2: "990PF"}

# per-slot resolution confidence + resolution note (spike judgement)
CONF = {
    1:  ("high",   "unique search hit; EIN confirmed"),
    2:  ("high",   "unique hit; mailing addr Conshohocken (agent), boathouse Philadelphia"),
    3:  ("high",   "unique hit; 501(c)(7) social club (contributions line small, member income = program svc)"),
    4:  ("high",   "first of 44 'community rowing' name collisions; disambiguated by Brighton MA + EIN"),
    5:  ("high",   "unique hit"),
    6:  ("low",    "racing brand 'Saugatuck Rowing' entangled with a FOR-PROFIT club; nonprofit filer OARS "
                   "dormant since 2008 (PDF-only 2003-08, no XML). SUBSTITUTED Marin Rowing (237448092) for extraction"),
    7:  ("medium", "recognizable c4 club is 990-N since ~2016; financial filer is the c3 arm "
                   "'Lincoln Park Boat Club Charitable Outreach' (272334832), also indexed as 'Lincoln Park Boating Community'"),
    8:  ("high",   "unique hit"),
    9:  ("high",   "one of ~35 'Friends of * Crew' boosters; chosen for long 990-EZ history"),
    10: ("medium", "racing identity 'Washington Rowing'/'Husky Crew' != filer; no 'Washington Rowing Foundation' exists; "
                   "real filer 'Husky Rowing Foundation' is 990-N only (no structured data / no XML)"),
}


def org_facts(ein):
    pj = OUT / ein / "propublica.json"
    if not pj.exists():
        return None
    d = json.loads(pj.read_text())
    o = d["organization"]
    fwd = d.get("filings_with_data", [])
    fwo = d.get("filings_without_data", [])
    forms = sorted({FT.get(f["formtype"], str(f["formtype"])) for f in fwd})
    wo_forms = sorted({(x.get("formtype_str") or "").rstrip("ORE") for x in fwo if x.get("formtype_str")})
    # XML tax years actually fetched
    xml_years = sorted({p[:4] for p in
                        (json.loads(x.read_text()).get("tax_period_end") or "" for x in (OUT / ein).glob("*.parsed.json"))
                        if p})
    data_years = sorted({f["tax_prd_yr"] for f in fwd})
    return dict(legal_name=o["name"], city=o["city"], state=o["state"],
                ntee=o.get("ntee_code") or "", sub=o.get("subsection_code"),
                forms=forms, wo_forms=wo_forms, xml_years=xml_years, data_years=data_years,
                wo=len(fwo), latest_obj=o.get("latest_object_id"))


def main():
    rows = []
    for o in COHORT:
        ein = o["ein"]
        f = org_facts(ein)
        conf, note = CONF[o["slot"]]
        if f is None:
            continue
        if f["forms"]:
            forms = ",".join(f["forms"])
        elif f["wo_forms"]:
            forms = ",".join(f["wo_forms"]) + " (PDF-only, no XML)"
        else:
            forms = "990-N only (no data filings)"
        xmly = ",".join(f["xml_years"]) or "NONE"
        full_note = f"c{f['sub']}; {note}"
        rows.append([o["racing_name"], ein, f["legal_name"], f["city"], f["state"], f["ntee"],
                     forms, xmly, conf, full_note])
        # slot 6 substitute row (Marin) right after Saugatuck
        if o["slot"] == 6:
            m = org_facts("237448092")
            if m:
                rows.append(["Marin Rowing Association (slot-6 substitute)", "237448092",
                             m["legal_name"], m["city"], m["state"], m["ntee"],
                             ",".join(m["forms"]), ",".join(m["xml_years"]),
                             "high", f"c{m['sub']}; clean c3 extraction stand-in for the dormant OARS nonprofit"])

    outp = OUT / "orgs.csv"
    with open(outp, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["org", "ein", "legal_name", "city", "state", "ntee",
                    "form_types_seen", "xml_years", "match_confidence", "notes"])
        w.writerows(rows)
    print(f"wrote {outp} ({len(rows)} rows)")
    for r in rows:
        print(f"  {r[0][:34]:34} EIN {r[1]} conf={r[8]:6} forms={r[6]:10} xml={r[7]}")


if __name__ == "__main__":
    main()
