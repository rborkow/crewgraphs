from crewgraphs.concept_map import EZ_NULL_CONCEPTS, EXPECTED_CONCEPTS, load_concept_map


def test_packaged_concept_map_has_all_24_expected_concepts() -> None:
    concept_map = load_concept_map()

    assert concept_map.version == "cm-2026.07.1"
    assert concept_map.concepts == EXPECTED_CONCEPTS
    assert len(concept_map.concepts) == 24
    assert all(concept_map.candidates("990", concept) for concept in concept_map.concepts)


def test_ez_null_set_is_exactly_the_four_990_only_concepts() -> None:
    concept_map = load_concept_map()
    ez_nulls = {
        concept
        for concept in concept_map.concepts
        if concept_map.candidates("990EZ", concept) is None
    }

    assert ez_nulls == EZ_NULL_CONCEPTS
    assert concept_map.candidates("990EZ", "program_service_expense") == (
        "TotalProgramServiceExpensesAmt",
    )
