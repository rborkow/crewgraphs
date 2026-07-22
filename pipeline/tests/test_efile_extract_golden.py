import json
from dataclasses import asdict
from pathlib import Path

import pytest

from crewgraphs.concept_map import load_concept_map
from crewgraphs.efile_extract import extract_filing


FIXTURES = Path(__file__).parent / "fixtures" / "golden"
GOLDEN_JSONS = sorted(FIXTURES.glob("*.parsed.json"))


def _normalise_concept(result: dict[str, object]) -> dict[str, object]:
    """Canonicalize numeric JSON values to the spike extractor's integer output.

    JSON does not distinguish integer and float notation. The spike's ``as_int``
    deliberately rounds source numeric text to an integer, so comparing canonical
    integers avoids a representational (rather than extraction) difference.
    """
    value = result["value"]
    return {
        "status": result["status"],
        "value": None if value is None else int(value),
        "xpath": result["xpath"],
    }


@pytest.mark.parametrize("json_path", GOLDEN_JSONS, ids=lambda path: path.stem)
def test_extract_filing_matches_spike_golden_concepts_and_headers(json_path: Path) -> None:
    expected = json.loads(json_path.read_text(encoding="utf-8"))
    actual = extract_filing(
        json_path.with_suffix("").with_suffix(".xml").read_bytes(), load_concept_map()
    )

    assert actual.ein == expected["ein"]
    assert actual.form_type == expected["form_type"]
    assert actual.return_version == expected["return_version"]
    assert actual.tax_period_end == expected["tax_period_end"]
    assert actual.tax_period_begin == expected["tax_period_begin"]
    assert actual.filer_name == expected["filer_name"]
    assert actual.amended == expected["amended"]
    assert actual.return_type == expected["return_type"]
    assert actual.fye_month == expected["fye_month"]
    assert {
        concept: _normalise_concept(asdict(result))
        for concept, result in actual.concepts.items()
    } == {
        concept: _normalise_concept(result)
        for concept, result in expected["concepts"].items()
    }


def test_extract_filing_captures_990_part_vii_compensation_and_role_flags() -> None:
    extract = extract_filing(
        (FIXTURES / "202031719349300818.xml").read_bytes(), load_concept_map()
    )

    rows = {row.name: row for row in extract.officer_rows}
    officer = rows["SANDY ARMSTRONG"]
    assert officer.title == "Executive Dir."
    assert officer.comp == 140539
    assert officer.other_comp == 20334
    assert officer.related_org_comp == 0
    assert officer.avg_hours == "40.00"
    assert officer.role_flags == ("officer",)
    director = rows["Raoul Wertz"]
    assert director.comp == 0
    assert director.role_flags == ("individual_trustee_or_director",)


def test_extract_filing_990ez_officer_rows_have_no_990_only_fields() -> None:
    extract = extract_filing(
        (FIXTURES / "202133159349200948.xml").read_bytes(), load_concept_map()
    )

    rows = {row.name: row for row in extract.officer_rows}
    compensated = rows["STEVEN GARSIDE"]
    assert compensated.comp == 3850
    assert compensated.avg_hours == "1.00"
    assert compensated.other_comp is None
    assert compensated.related_org_comp is None
    assert compensated.role_flags == ()
