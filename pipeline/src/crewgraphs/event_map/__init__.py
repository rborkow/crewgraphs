"""Versioned, repository-owned canonical regatta event classification map."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from importlib import resources
from types import MappingProxyType
from typing import Any
import re

import yaml


MAP_FILENAME = "em-2026.07.2.yaml"
BOAT_CLASSES = frozenset({"1x", "2x", "2-", "2+", "4x", "4-", "4+", "8+", "other"})
AGE_BRACKETS = frozenset(
    {
        "u13", "u15", "u16", "u17", "u19_youth", "collegiate", "open",
        "masters_a", "masters_b", "masters_c", "masters_d", "masters_e",
        "masters_f", "masters_g", "masters_h", "masters_i", "masters_j",
        "masters_k", "masters_unspecified", "other",
    }
)
GENDERS = frozenset({"men", "women", "mixed", "open", "unspecified"})
_VOCABULARIES = {
    "boat_class": BOAT_CLASSES,
    "age_bracket": AGE_BRACKETS,
    "gender": GENDERS,
}
_GENDER_ALIASES = {
    "m": "men", "man": "men", "men": "men", "mens": "men", "b": "men", "boy": "men", "boys": "men",
    "w": "women", "woman": "women", "women": "women", "womens": "women", "g": "women", "girl": "women", "girls": "women",
    "mixed": "mixed",
}
_FULL_GENDER_RE = re.compile(
    r"\b(?P<gender>men(?:['’]?s)?|man|women(?:['’]?s)?|woman|boys?|girls?|mixed)\b",
    re.IGNORECASE,
)
# M/W/B/G are accepted only as compact event-code prefixes attached to an
# age or boat token. A standalone flight/pool letter is never gender evidence.
_COMPACT_GENDER_RE = re.compile(
    r"(?P<gender>[mwbg])\s*(?=(?:u[ -]?1[35679]|j(?:unior)?[ -]?1[5679]|"
    r"junior\s+1[5679]|y\b|youth|1x|2x|2[-+]|4x|4[-+]|8\+))",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class EventClassification:
    mapping_key: str
    boat_class: str
    age_bracket: str
    gender: str


@dataclass(frozen=True, slots=True)
class _Rule:
    key: str
    match: Mapping[str, re.Pattern[str]]
    emit: Mapping[str, str | Mapping[str, Any]]


@dataclass(frozen=True, slots=True)
class EventMap:
    version: str
    rules: tuple[_Rule, ...]

    def classify(self, event: Mapping[str, object]) -> EventClassification | None:
        """Return the first explicit mapping rule that matches an event.

        Rules intentionally require all of their match expressions.  There is
        no fallback based on a partial event name: unmapped vocabulary must be
        reviewed, not inferred.
        """
        gender = _structural_gender(event)
        if gender is None:
            return None
        values = _event_values(event)
        for rule in self.rules:
            groups: dict[str, str] = {"gender": gender}
            for field, expression in rule.match.items():
                matched = expression.search(values[field])
                if matched is None:
                    break
                groups.update({key: value for key, value in matched.groupdict().items() if value is not None})
            else:
                emitted = {field: _emit_value(value, groups, rule.key, field) for field, value in rule.emit.items()}
                return EventClassification(mapping_key=rule.key, **emitted)  # type: ignore[arg-type]
        return None


def _event_values(event: Mapping[str, object]) -> dict[str, str]:
    fields = ("event_code", "name", "boat_class_raw", "age_class_raw", "gender_raw")
    values = {field: str(event.get(field) or "") for field in fields}
    # ``text`` is deliberately a provider-raw concatenation. Rules can choose
    # one field or corroborate information across the raw event representation.
    values["text"] = "\n".join(values[field] for field in fields)
    return values


def _structural_gender(event: Mapping[str, object]) -> str | None:
    """Resolve gender without treating arbitrary event-code letters as sex.

    Provider gender fields are authoritative when they contain a recognized
    vocabulary value. Otherwise full gender words beat compact M/W/B/G forms;
    a disagreement at either level is deliberately left unmapped for review.
    """
    raw = _gender_alias(event.get("gender_raw"))
    if raw is not None:
        return raw
    values = tuple(str(event.get(field) or "") for field in ("event_code", "name", "boat_class_raw", "age_class_raw"))
    words = _genders_from(_FULL_GENDER_RE, values)
    if len(words) == 1:
        return words.pop()
    if words:
        return None
    compact = _genders_from(_COMPACT_GENDER_RE, values)
    return compact.pop() if len(compact) == 1 else None


def _genders_from(expression: re.Pattern[str], values: tuple[str, ...]) -> set[str]:
    return {
        gender
        for value in values
        for match in expression.finditer(value)
        if (gender := _gender_alias(match.group("gender"))) is not None
    }


def _gender_alias(value: object) -> str | None:
    normalized = str(value or "").casefold().replace("'", "").replace("’", "")
    return _GENDER_ALIASES.get(normalized)


def _emit_value(value: str | Mapping[str, Any], groups: Mapping[str, str], key: str, field: str) -> str:
    if isinstance(value, str):
        result = value
    elif isinstance(value, Mapping) and isinstance(value.get("group"), str):
        group = value["group"]
        if group not in groups:
            raise ValueError(f"event map rule {key!r} emits {field} from missing group {group!r}")
        aliases = value.get("aliases", {})
        if not isinstance(aliases, Mapping):
            raise ValueError(f"event map rule {key!r} has invalid aliases for {field}")
        normalized = groups[group].casefold().replace("'", "").replace("’", "")
        result = str(aliases.get(normalized, _GENDER_ALIASES.get(normalized, normalized)))
    else:
        raise ValueError(f"event map rule {key!r} has invalid {field} emission")
    if result not in _VOCABULARIES[field]:
        raise ValueError(f"event map rule {key!r} emits invalid {field}: {result!r}")
    return result


def _parse_map(document: object) -> EventMap:
    if not isinstance(document, Mapping):
        raise ValueError("event map must be a mapping")
    version, entries = document.get("version"), document.get("rules")
    if not isinstance(version, str) or not version:
        raise ValueError("event map version is required")
    if not isinstance(entries, list) or not entries:
        raise ValueError("event map rules must be a non-empty list")
    rules: list[_Rule] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise ValueError("every event map rule must be a mapping")
        key, matches, emit = entry.get("key"), entry.get("match"), entry.get("emit")
        if not isinstance(key, str) or not key or key in seen:
            raise ValueError(f"invalid or duplicate event map key: {key!r}")
        if not isinstance(matches, Mapping) or not matches:
            raise ValueError(f"event map rule {key!r} needs match expressions")
        if not isinstance(emit, Mapping) or set(emit) != set(_VOCABULARIES):
            raise ValueError(f"event map rule {key!r} must emit all canonical dimensions")
        compiled: dict[str, re.Pattern[str]] = {}
        for field, expression in matches.items():
            if field not in {"event_code", "name", "boat_class_raw", "age_class_raw", "gender_raw", "text"}:
                raise ValueError(f"event map rule {key!r} has unsupported match field {field!r}")
            if not isinstance(expression, str) or not expression:
                raise ValueError(f"event map rule {key!r} has invalid {field} regex")
            compiled[field] = re.compile(expression, re.IGNORECASE)
        rule = _Rule(key=key, match=MappingProxyType(compiled), emit=MappingProxyType(dict(emit)))
        # Validate fixed emissions and any malformed derived expressions while
        # loading, instead of surfacing a mapping typo in a production job.
        for field, value in rule.emit.items():
            if isinstance(value, str) and value not in _VOCABULARIES[field]:
                raise ValueError(f"event map rule {key!r} emits invalid {field}: {value!r}")
        seen.add(key)
        rules.append(rule)
    return EventMap(version=version, rules=tuple(rules))


def load_event_map() -> EventMap:
    """Load the packaged production event map through ``importlib.resources``."""
    resource = resources.files(__package__).joinpath(MAP_FILENAME)
    return _parse_map(yaml.safe_load(resource.read_text(encoding="utf-8")))


def load_default_event_map() -> EventMap:
    return load_event_map()


__all__ = [
    "AGE_BRACKETS", "BOAT_CLASSES", "GENDERS", "EventClassification", "EventMap",
    "MAP_FILENAME", "load_default_event_map", "load_event_map",
]
