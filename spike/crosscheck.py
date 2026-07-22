#!/usr/bin/env python3
"""Cross-check 6 anchor concepts from parsed XML against ProPublica normals.

For each output/{ein}/{object_id}.parsed.json we match the filing to a
ProPublica `filings_with_data` row by tax period (YYYYMM) and compare:

  XML concept              ProPublica field
  -----------------------  -----------------
  total_revenue            totrevenue
  total_expenses           totfuncexpns
  total_assets_eoy         totassetsend
  total_liabilities_eoy    totliabend
  contributions_grants     totcntrbgfts
  program_service_revenue  totprgmrevnue

XML "absent" is treated as 0 (IRS e-file omits $0 optional lines).
Writes output/crosscheck.csv and prints mismatches.

Run:  uv run --with lxml spike/crosscheck.py   (no lxml needed, stdlib only)
"""
import csv
import json
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "output"

ANCHORS = {
    "total_revenue": "totrevenue",
    "total_expenses": "totfuncexpns",
    "total_assets_eoy": "totassetsend",
    "total_liabilities_eoy": "totliabend",
    "contributions_grants": "totcntrbgfts",
    "program_service_revenue": "totprgmrevnue",
}


def tax_prd_from_end(end: str) -> str:
    # "2023-12-31" -> "202312"
    return (end or "")[:7].replace("-", "") if end else ""


def main():
    rows = []
    for ein_dir in sorted(OUT.iterdir()):
        if not ein_dir.is_dir():
            continue
        pj = ein_dir / "propublica.json"
        if not pj.exists():
            continue
        fwd = {str(f["tax_prd"]): f for f in json.loads(pj.read_text()).get("filings_with_data", [])}
        for parsed_path in sorted(ein_dir.glob("*.parsed.json")):
            p = json.loads(parsed_path.read_text())
            tp = tax_prd_from_end(p.get("tax_period_end"))
            pp = fwd.get(tp)
            for concept, ppfield in ANCHORS.items():
                c = p["concepts"][concept]
                xml_val = c["value"] if c["status"] == "resolved" else (0 if c["status"] == "absent" else None)
                if pp is None:
                    rows.append([p["ein"], tp, p["return_version"], p["form_type"], concept,
                                 xml_val, "", "no_pp_row", ""])
                    continue
                pp_val = pp.get(ppfield)
                match = (xml_val == pp_val)
                note = "" if match else "MISMATCH"
                if not match and xml_val is not None and pp_val is not None:
                    note = f"MISMATCH diff={xml_val - pp_val}"
                rows.append([p["ein"], tp, p["return_version"], p["form_type"], concept,
                             xml_val, pp_val, "match" if match else "mismatch", note])

    outp = OUT / "crosscheck.csv"
    with open(outp, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["ein", "tax_prd", "return_version", "form_type", "concept",
                    "xml_value", "pp_value", "result", "note"])
        w.writerows(rows)

    total = len(rows)
    matches = sum(1 for r in rows if r[7] == "match")
    mism = [r for r in rows if r[7] == "mismatch"]
    nopp = [r for r in rows if r[7] == "no_pp_row"]
    print(f"anchor comparisons: {total}  match={matches}  mismatch={len(mism)}  no_pp_row={len(nopp)}")
    if mism:
        print("\nMISMATCHES:")
        for r in mism:
            print(f"  EIN {r[0]} tp={r[1]} {r[3]:8} {r[4]:24} xml={r[5]} pp={r[6]}  {r[8]}")
    if nopp:
        print(f"\nno ProPublica row for {len(nopp)} comparisons (tax periods not in FWD):")
        seen = {(r[0], r[1]) for r in nopp}
        for e, tp in sorted(seen):
            print(f"  EIN {e} tp={tp}")
    print(f"\n-> wrote {outp}")


if __name__ == "__main__":
    main()
