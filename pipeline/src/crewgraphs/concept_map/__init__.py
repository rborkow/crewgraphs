"""Versioned IRS Form 990 concept-map loading and validation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from importlib import resources
from types import MappingProxyType
from typing import Any

import yaml


MAP_FILENAME = "cm-2026.07.1.yaml"
EXPECTED_CONCEPTS = (
    "total_revenue",
    "total_expenses",
    "revenue_less_expenses",
    "contributions_grants",
    "program_service_revenue",
    "membership_dues",
    "investment_income",
    "fundraising_events_gross",
    "fundraising_events_net",
    "other_revenue",
    "grants_paid",
    "salaries_benefits_total",
    "officer_compensation",
    "professional_fundraising_fees",
    "occupancy",
    "program_service_expense",
    "management_general_expense",
    "fundraising_expense",
    "total_assets_eoy",
    "total_liabilities_eoy",
    "net_assets_eoy",
    "cash_savings_eoy",
    "land_buildings_equipment_net",
    "employee_count",
)
EZ_NULL_CONCEPTS = frozenset(
    {
        "professional_fundraising_fees",
        "management_general_expense",
        "fundraising_expense",
        "employee_count",
    }
)
_FORM_ALIASES = {"990": "990", "IRS990": "990", "990EZ": "990EZ", "IRS990EZ": "990EZ"}

Candidate = str | Mapping[str, tuple[str, ...]]


@dataclass(frozen=True, slots=True)
class ConceptMap:
    """An immutable, validated ordered set of extraction candidates."""

    version: str
    concepts: tuple[str, ...]
    _forms: Mapping[str, Mapping[str, tuple[Candidate, ...] | None]]

    def candidates(self, form_type: str, concept: str) -> tuple[Candidate, ...] | None:
        """Return ordered candidates for an IRS form, or ``None`` if unavailable."""
        try:
            form = _FORM_ALIASES[form_type]
        except KeyError as exc:
            raise ValueError(f"unsupported form type: {form_type!r}") from exc
        try:
            return self._forms[concept][form]
        except KeyError as exc:
            raise ValueError(f"unknown concept: {concept!r}") from exc


def _freeze_candidate(candidate: object, *, concept: str, form: str) -> Candidate:
    if isinstance(candidate, str):
        if not candidate:
            raise ValueError(f"{concept}.{form} has an empty xpath")
        return candidate
    if not isinstance(candidate, Mapping) or set(candidate) not in ({"sum"}, {"sub"}):
        raise ValueError(f"{concept}.{form} has an invalid candidate: {candidate!r}")
    operation = next(iter(candidate))
    xpaths = candidate[operation]
    if (
        not isinstance(xpaths, Sequence)
        or isinstance(xpaths, str)
        or not xpaths
        or not all(isinstance(xpath, str) and xpath for xpath in xpaths)
    ):
        raise ValueError(f"{concept}.{form} has invalid {operation} xpaths")
    if operation == "sub" and len(xpaths) != 2:
        raise ValueError(f"{concept}.{form} subtraction requires exactly two xpaths")
    return MappingProxyType({operation: tuple(xpaths)})


def _parse_map(document: object) -> ConceptMap:
    if not isinstance(document, Mapping):
        raise ValueError("concept map must be a mapping")
    metadata = document.get("metadata")
    entries = document.get("concepts")
    if not isinstance(metadata, Mapping) or not isinstance(metadata.get("version"), str):
        raise ValueError("concept map metadata.version is required")
    if not isinstance(entries, list):
        raise ValueError("concept map concepts must be a list")

    concepts: list[str] = []
    forms_by_concept: dict[str, Mapping[str, tuple[Candidate, ...] | None]] = {}
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise ValueError("every concept entry must be a mapping")
        concept = entry.get("concept")
        forms = entry.get("forms")
        if not isinstance(concept, str) or not isinstance(forms, Mapping):
            raise ValueError("every concept needs a name and forms")
        if concept in forms_by_concept:
            raise ValueError(f"duplicate concept: {concept}")
        if "990" not in forms:
            raise ValueError(f"{concept} is missing its 990 entry")
        if "990EZ" not in forms:
            raise ValueError(f"{concept} is missing its 990EZ entry")
        unknown_forms = set(forms) - {"990", "990EZ"}
        if unknown_forms:
            raise ValueError(f"{concept} has unsupported forms: {sorted(unknown_forms)!r}")

        frozen_forms: dict[str, tuple[Candidate, ...] | None] = {}
        for form in ("990", "990EZ"):
            value = forms[form]
            if form == "990" and value is None:
                raise ValueError(f"{concept}.990 cannot be null")
            if value is not None:
                if not isinstance(value, list) or not value:
                    raise ValueError(f"{concept}.{form} must be a non-empty candidate list")
                frozen_forms[form] = tuple(
                    _freeze_candidate(candidate, concept=concept, form=form)
                    for candidate in value
                )
            else:
                frozen_forms[form] = None
        concepts.append(concept)
        forms_by_concept[concept] = MappingProxyType(frozen_forms)

    if tuple(concepts) != EXPECTED_CONCEPTS:
        raise ValueError("concept map must contain exactly the 24 expected concepts in order")
    actual_ez_nulls = {concept for concept in concepts if forms_by_concept[concept]["990EZ"] is None}
    if actual_ez_nulls != EZ_NULL_CONCEPTS:
        raise ValueError(
            "990EZ null concepts must be exactly "
            f"{sorted(EZ_NULL_CONCEPTS)!r}; got {sorted(actual_ez_nulls)!r}"
        )
    return ConceptMap(
        version=metadata["version"],
        concepts=tuple(concepts),
        _forms=MappingProxyType(forms_by_concept),
    )


def load_concept_map() -> ConceptMap:
    """Load the packaged production concept map through ``importlib.resources``."""
    resource = resources.files(__package__).joinpath(MAP_FILENAME)
    return _parse_map(yaml.safe_load(resource.read_text(encoding="utf-8")))


def load_default_concept_map() -> ConceptMap:
    """Compatibility-friendly explicit name for the packaged map loader."""
    return load_concept_map()


__all__ = [
    "Candidate",
    "ConceptMap",
    "EXPECTED_CONCEPTS",
    "EZ_NULL_CONCEPTS",
    "MAP_FILENAME",
    "load_concept_map",
    "load_default_concept_map",
]
