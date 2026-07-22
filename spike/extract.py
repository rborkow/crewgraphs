#!/usr/bin/env python3
"""CrewGraphs concept extractor for IRS 990 / 990-EZ e-file XML.

Pulls 24 financial concepts from every XML under output/{ein}/*.xml, using an
ordered candidate-xpath map per form type. Records, per concept:
  status = resolved | absent | not_on_form
    resolved     -> element found, value captured
    absent       -> xpath valid for this form, but no element in this filing
                    (IRS e-file omits $0 / not-applicable optional lines)
    not_on_form  -> concept does not exist on this form type (990-only lines on EZ)
and the exact xpath (or composite expression) that produced the value.

Also extracts officer / key-employee compensation rows (Part VII / EZ Part IV)
for a data-quality (publishability) check.

Writes output/{ein}/{object_id}.parsed.json and prints a resolution summary
per return_version. Pure httpx/lxml, no network.

Run:  uv run --with lxml spike/extract.py
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

from lxml import etree

HERE = Path(__file__).parent
OUT = HERE / "output"
NS = {"e": "http://www.irs.gov/efile"}

# Per form type: concept -> handler. A handler is one of:
#   [xpath, ...]          first element that resolves wins
#   {"sum": [xpath, ...]} sum ALL matching elements across the listed xpaths
#   {"sub": [a, b]}       value(a) - value(b); absent if a absent
#   "NOT_ON_FORM"         concept does not exist on this form type
MAP_990 = {
    "total_revenue":                 ["CYTotalRevenueAmt"],
    "total_expenses":                ["CYTotalExpensesAmt"],
    "revenue_less_expenses":         ["CYRevenuesLessExpensesAmt"],
    "contributions_grants":          ["CYContributionsGrantsAmt"],
    "program_service_revenue":       ["CYProgramServiceRevenueAmt"],
    "membership_dues":               ["MembershipDuesAmt"],
    "investment_income":             ["CYInvestmentIncomeAmt"],
    "fundraising_events_gross":      ["FundraisingGrossIncomeAmt", "GrossIncomeFundraisingEventsAmt"],
    "fundraising_events_net":        {"sub": ["FundraisingGrossIncomeAmt", "FundraisingDirectExpensesAmt"]},
    "other_revenue":                 ["CYOtherRevenueAmt"],
    "grants_paid":                   ["CYGrantsAndSimilarPaidAmt"],
    "salaries_benefits_total":       ["CYSalariesCompEmpBnftPaidAmt"],
    "officer_compensation":          ["CompCurrentOfcrDirectorsGrp/TotalAmt", "CompCurrentOfcrDirectorsAmt"],
    "professional_fundraising_fees": ["FeesForServicesProfFundraisingGrp/TotalAmt", "FeesForServicesProfFundraising"],
    "occupancy":                     ["OccupancyGrp/TotalAmt"],
    "program_service_expense":       ["TotalFunctionalExpensesGrp/ProgramServicesAmt"],
    "management_general_expense":    ["TotalFunctionalExpensesGrp/ManagementAndGeneralAmt"],
    "fundraising_expense":           ["TotalFunctionalExpensesGrp/FundraisingAmt"],
    "total_assets_eoy":              ["TotalAssetsEOYAmt", "TotalAssetsGrp/EOYAmt"],
    "total_liabilities_eoy":         ["TotalLiabilitiesEOYAmt", "TotalLiabilitiesGrp/EOYAmt"],
    "net_assets_eoy":                ["TotalNetAssetsFundBalanceGrp/EOYAmt", "NetAssetsOrFundBalancesEOYAmt"],
    "cash_savings_eoy":              {"sum": ["CashNonInterestBearingGrp/EOYAmt", "SavingsAndTempCashInvstGrp/EOYAmt"]},
    "land_buildings_equipment_net":  ["LandBldgEquipBasisNetGrp/EOYAmt"],
    "employee_count":                ["TotalEmployeeCnt"],
}
MAP_990EZ = {
    "total_revenue":                 ["TotalRevenueAmt"],
    "total_expenses":                ["TotalExpensesAmt"],
    "revenue_less_expenses":         ["ExcessOrDeficitForYearAmt"],
    "contributions_grants":          ["ContributionsGiftsGrantsEtcAmt"],
    "program_service_revenue":       ["ProgramServiceRevenueAmt"],
    "membership_dues":               ["MembershipDuesAmt"],
    "investment_income":             ["InvestmentIncomeAmt"],
    "fundraising_events_gross":      ["FundraisingGrossIncomeAmt"],
    "fundraising_events_net":        ["SpecialEventsNetIncomeLossAmt"],
    "other_revenue":                 ["OtherRevenueTotalAmt"],
    "grants_paid":                   ["GrantsAndSimilarAmountsPaidAmt"],
    "salaries_benefits_total":       ["SalariesOtherCompEmplBnftAmt"],
    "officer_compensation":          {"sum": ["OfficerDirectorTrusteeEmplGrp/CompensationAmt"]},
    "professional_fundraising_fees": "NOT_ON_FORM",
    "occupancy":                     ["OccupancyRentUtltsAndMaintAmt"],
    "program_service_expense":       ["TotalProgramServiceExpensesAmt"],
    "management_general_expense":    "NOT_ON_FORM",
    "fundraising_expense":           "NOT_ON_FORM",
    "total_assets_eoy":              ["Form990TotalAssetsGrp/EOYAmt"],
    "total_liabilities_eoy":         ["SumOfTotalLiabilitiesGrp/EOYAmt"],
    "net_assets_eoy":                ["NetAssetsOrFundBalancesEOYAmt", "NetAssetsOrFundBalancesGrp/EOYAmt"],
    "cash_savings_eoy":              ["CashSavingsAndInvestmentsGrp/EOYAmt"],
    "land_buildings_equipment_net":  ["LandAndBuildingsGrp/EOYAmt"],
    "employee_count":                "NOT_ON_FORM",
}
CONCEPTS = list(MAP_990.keys())


def qn(xp):  # relative xpath -> namespaced
    return "/".join(f"e:{p}" for p in xp.split("/"))


def as_int(txt):
    try:
        return int(round(float(txt)))
    except (TypeError, ValueError):
        return None


def first(form, xpaths):
    for xp in xpaths:
        els = form.xpath(qn(xp), namespaces=NS)
        for el in els:
            v = as_int((el.text or "").strip())
            if v is not None:
                return v, xp
    return None, None


def sum_all(form, xpaths):
    total, used, hits = 0, [], 0
    for xp in xpaths:
        for el in form.xpath(qn(xp), namespaces=NS):
            v = as_int((el.text or "").strip())
            if v is not None:
                total += v
                hits += 1
                if xp not in used:
                    used.append(xp)
    if hits == 0:
        return None, None
    return total, "sum(" + " + ".join(used) + f") over {hits} node(s)"


def resolve(form, handler):
    if handler == "NOT_ON_FORM":
        return {"status": "not_on_form", "value": None, "xpath": None}
    if isinstance(handler, dict) and "sum" in handler:
        v, xp = sum_all(form, handler["sum"])
    elif isinstance(handler, dict) and "sub" in handler:
        a, xpa = first(form, [handler["sub"][0]])
        if a is None:
            v, xp = None, None
        else:
            b, _ = first(form, [handler["sub"][1]])
            v = a - (b or 0)
            xp = f"{handler['sub'][0]} - {handler['sub'][1]}"
    else:
        v, xp = first(form, handler)
    if v is None:
        return {"status": "absent", "value": None, "xpath": None}
    return {"status": "resolved", "value": v, "xpath": xp}


def officer_rows(form, form_type):
    rows = []
    if form_type == "IRS990":
        grp = "e:Form990PartVIISectionAGrp"
        name, title, comp, hrs = "e:PersonNm", "e:TitleTxt", "e:ReportableCompFromOrgAmt", "e:AverageHoursPerWeekRt"
    else:
        grp = "e:OfficerDirectorTrusteeEmplGrp"
        name, title, comp, hrs = "e:PersonNm", "e:TitleTxt", "e:CompensationAmt", "e:AverageHrsPerWkDevotedToPosRt"
    for g in form.xpath(grp, namespaces=NS):
        def t(x):
            r = g.xpath(x, namespaces=NS)
            return (r[0].text or "").strip() if r else None
        # older schemas used BusinessName/PersonNm variants; try PersonNm then NamePerson
        nm = t(name) or t("e:NamePerson")
        rows.append({"name": nm, "title": t(title),
                     "comp": as_int(t(comp)), "avg_hours": t(hrs)})
    return rows


def header(root):
    def g(path):
        r = root.xpath(path, namespaces=NS)
        return (r[0].text or "").strip() if r else None
    return {
        "return_version": root.get("returnVersion"),
        "tax_period_end": g(".//e:ReturnHeader/e:TaxPeriodEndDt") or g(".//e:ReturnHeader/e:TaxPeriodEndDate"),
        "tax_period_begin": g(".//e:ReturnHeader/e:TaxPeriodBeginDt") or g(".//e:ReturnHeader/e:TaxPeriodBeginDate"),
        "filer_name": g(".//e:ReturnHeader/e:Filer/e:BusinessName/e:BusinessNameLine1Txt")
                      or g(".//e:ReturnHeader/e:Filer/e:Name/e:BusinessNameLine1"),
        "amended": bool(root.xpath(".//e:ReturnHeader/e:AmendedReturnInd", namespaces=NS)),
        "return_type": g(".//e:ReturnHeader/e:ReturnTypeCd"),
    }


def find_form(root):
    for el in root.iter():
        ln = etree.QName(el).localname
        if ln in ("IRS990", "IRS990EZ"):
            return el, ln
    return None, None


def parse_file(path: Path):
    root = etree.parse(str(path)).getroot()
    form, ftype = find_form(root)
    if form is None:
        return None
    hdr = header(root)
    mp = MAP_990 if ftype == "IRS990" else MAP_990EZ
    concepts = {c: resolve(form, mp[c]) for c in CONCEPTS}
    return {
        "ein": path.parent.name,
        "object_id": path.stem,
        "form_type": ftype,
        **hdr,
        "fye_month": (hdr["tax_period_end"] or "")[5:7],
        "concepts": concepts,
        "officer_rows": officer_rows(form, ftype),
    }


def main():
    per_version = defaultdict(lambda: defaultdict(lambda: {"resolved": 0, "absent": 0, "not_on_form": 0}))
    files = sorted(OUT.glob("*/*.xml"))
    n = 0
    for f in files:
        parsed = parse_file(f)
        if parsed is None:
            print(f"  !! no form element: {f}")
            continue
        (f.parent / f"{f.stem}.parsed.json").write_text(json.dumps(parsed, indent=2))
        n += 1
        rv = parsed["return_version"]
        for c, r in parsed["concepts"].items():
            per_version[rv][c][r["status"]] += 1

    # summary
    print(f"parsed {n} filings\n")
    applicable = defaultdict(lambda: {"resolved": 0, "absent": 0, "not_on_form": 0, "filings": 0})
    for rv in sorted(per_version):
        tot = {"resolved": 0, "absent": 0, "not_on_form": 0}
        nfil = max(sum(s.values()) for s in per_version[rv].values()) // 1  # concepts share filing count
        # filings for this version = resolved+absent+not_on_form for any concept
        any_c = next(iter(per_version[rv].values()))
        nfil = sum(any_c.values())
        for c in CONCEPTS:
            s = per_version[rv][c]
            for k in tot:
                tot[k] += s[k]
        appl = tot["resolved"] + tot["absent"]  # concepts that exist on the form(s) in this version bucket
        rate = 100 * tot["resolved"] / appl if appl else 0
        print(f"  {rv:10} filings={nfil:2}  resolved={tot['resolved']:3} absent={tot['absent']:3} "
              f"not_on_form={tot['not_on_form']:3}  resolve-rate(of applicable)={rate:4.0f}%")

    # per-concept resolution across all filings
    print("\n  per-concept status counts (all filings):")
    agg = {c: {"resolved": 0, "absent": 0, "not_on_form": 0} for c in CONCEPTS}
    for rv in per_version:
        for c in CONCEPTS:
            for k in agg[c]:
                agg[c][k] += per_version[rv][c][k]
    for c in CONCEPTS:
        a = agg[c]
        print(f"    {c:30} resolved={a['resolved']:2} absent={a['absent']:2} not_on_form={a['not_on_form']:2}")


if __name__ == "__main__":
    main()
