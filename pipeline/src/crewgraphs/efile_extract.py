"""Extract CrewGraphs' 24 financial concepts from IRS 990 e-file XML."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from lxml import etree

from .concept_map import Candidate, ConceptMap


NS = {"e": "http://www.irs.gov/efile"}
Status = Literal["resolved", "absent", "not_on_form"]


@dataclass(frozen=True, slots=True)
class ConceptResult:
    status: Status
    value: int | None
    xpath: str | None


@dataclass(frozen=True, slots=True)
class OfficerRow:
    name: str | None
    title: str | None
    comp: int | None
    avg_hours: str | None
    other_comp: int | None
    related_org_comp: int | None
    role_flags: tuple[str, ...]


# Form 990 Part VII position checkboxes; the 990-EZ officer table has none.
_ROLE_FLAGS_990 = (
    ("IndividualTrusteeOrDirectorInd", "individual_trustee_or_director"),
    ("OfficerInd", "officer"),
    ("KeyEmployeeInd", "key_employee"),
    ("HighestCompensatedEmployeeInd", "highest_compensated_employee"),
    ("FormerOfcrDirectorTrusteeInd", "former_officer_director_trustee"),
)


@dataclass(frozen=True, slots=True)
class FilingExtract:
    ein: str | None
    form_type: str
    return_version: str | None
    tax_period_end: str | None
    tax_period_begin: str | None
    filer_name: str | None
    amended: bool
    return_type: str | None
    fye_month: str
    concepts: dict[str, ConceptResult]
    officer_rows: tuple[OfficerRow, ...]


def _qn(xpath: str) -> str:
    return "/".join(f"e:{part}" for part in xpath.split("/"))


def _as_int(text: str | None) -> int | None:
    try:
        return int(round(float(text)))
    except (TypeError, ValueError):
        return None


def _first(form: etree._Element, xpaths: tuple[str, ...]) -> tuple[int | None, str | None]:
    for xpath in xpaths:
        for element in form.xpath(_qn(xpath), namespaces=NS):
            value = _as_int((element.text or "").strip())
            if value is not None:
                return value, xpath
    return None, None


def _sum_all(form: etree._Element, xpaths: tuple[str, ...]) -> tuple[int | None, str | None]:
    total, used, hits = 0, [], 0
    for xpath in xpaths:
        for element in form.xpath(_qn(xpath), namespaces=NS):
            value = _as_int((element.text or "").strip())
            if value is not None:
                total += value
                hits += 1
                if xpath not in used:
                    used.append(xpath)
    if hits == 0:
        return None, None
    return total, "sum(" + " + ".join(used) + f") over {hits} node(s)"


def _resolve(form: etree._Element, candidates: tuple[Candidate, ...] | None) -> ConceptResult:
    if candidates is None:
        return ConceptResult("not_on_form", None, None)
    candidate = candidates[0] if len(candidates) == 1 else None
    if isinstance(candidate, dict) or hasattr(candidate, "get"):
        if "sum" in candidate:
            value, xpath = _sum_all(form, candidate["sum"])
        else:
            minuend, xpa = _first(form, (candidate["sub"][0],))
            if minuend is None:
                value, xpath = None, None
            else:
                subtrahend, _ = _first(form, (candidate["sub"][1],))
                value = minuend - (subtrahend or 0)
                xpath = f"{candidate['sub'][0]} - {candidate['sub'][1]}"
    else:
        value, xpath = _first(form, candidates)  # type: ignore[arg-type]
    if value is None:
        return ConceptResult("absent", None, None)
    return ConceptResult("resolved", value, xpath)


def _text(root: etree._Element, xpath: str) -> str | None:
    result = root.xpath(xpath, namespaces=NS)
    return (result[0].text or "").strip() if result else None


def _find_form(root: etree._Element) -> tuple[etree._Element, str]:
    for element in root.iter():
        local_name = etree.QName(element).localname
        if local_name in ("IRS990", "IRS990EZ"):
            return element, local_name
    raise ValueError("IRS e-file XML has no IRS990 or IRS990EZ form element")


def _officer_rows(form: etree._Element, form_type: str) -> tuple[OfficerRow, ...]:
    is_990 = form_type == "IRS990"
    if is_990:
        group, name, title, comp, hours = (
            "e:Form990PartVIISectionAGrp",
            "e:PersonNm",
            "e:TitleTxt",
            "e:ReportableCompFromOrgAmt",
            "e:AverageHoursPerWeekRt",
        )
    else:
        group, name, title, comp, hours = (
            "e:OfficerDirectorTrusteeEmplGrp",
            "e:PersonNm",
            "e:TitleTxt",
            "e:CompensationAmt",
            "e:AverageHrsPerWkDevotedToPosRt",
        )

    def group_text(element: etree._Element, xpath: str) -> str | None:
        result = element.xpath(xpath, namespaces=NS)
        return (result[0].text or "").strip() if result else None

    def role_flags(element: etree._Element) -> tuple[str, ...]:
        # A checkbox is checked by presence (fixed "X" value in the IRS schema).
        if not is_990:
            return ()
        return tuple(
            flag
            for tag, flag in _ROLE_FLAGS_990
            if element.xpath(f"e:{tag}", namespaces=NS)
        )

    return tuple(
        OfficerRow(
            name=group_text(element, name) or group_text(element, "e:NamePerson"),
            title=group_text(element, title),
            comp=_as_int(group_text(element, comp)),
            avg_hours=group_text(element, hours),
            other_comp=_as_int(group_text(element, "e:OtherCompensationAmt")) if is_990 else None,
            related_org_comp=(
                _as_int(group_text(element, "e:ReportableCompFromRltdOrgAmt")) if is_990 else None
            ),
            role_flags=role_flags(element),
        )
        for element in form.xpath(group, namespaces=NS)
    )


def extract_filing(xml_bytes: bytes, concept_map: ConceptMap) -> FilingExtract:
    """Parse a single IRS 990/990-EZ XML filing using ``concept_map``."""
    root = etree.fromstring(xml_bytes)
    form, form_type = _find_form(root)
    tax_period_end = _text(root, ".//e:ReturnHeader/e:TaxPeriodEndDt") or _text(
        root, ".//e:ReturnHeader/e:TaxPeriodEndDate"
    )
    tax_period_begin = _text(root, ".//e:ReturnHeader/e:TaxPeriodBeginDt") or _text(
        root, ".//e:ReturnHeader/e:TaxPeriodBeginDate"
    )
    return FilingExtract(
        ein=_text(root, ".//e:ReturnHeader/e:Filer/e:EIN"),
        form_type=form_type,
        return_version=root.get("returnVersion"),
        tax_period_end=tax_period_end,
        tax_period_begin=tax_period_begin,
        filer_name=_text(root, ".//e:ReturnHeader/e:Filer/e:BusinessName/e:BusinessNameLine1Txt")
        or _text(root, ".//e:ReturnHeader/e:Filer/e:Name/e:BusinessNameLine1"),
        amended=bool(root.xpath(".//e:ReturnHeader/e:AmendedReturnInd", namespaces=NS)),
        return_type=_text(root, ".//e:ReturnHeader/e:ReturnTypeCd"),
        fye_month=(tax_period_end or "")[5:7],
        concepts={
            concept: _resolve(form, concept_map.candidates(form_type, concept))
            for concept in concept_map.concepts
        },
        officer_rows=_officer_rows(form, form_type),
    )


__all__ = ["ConceptResult", "FilingExtract", "OfficerRow", "extract_filing"]
