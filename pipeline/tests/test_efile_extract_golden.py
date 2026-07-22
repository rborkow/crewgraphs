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
