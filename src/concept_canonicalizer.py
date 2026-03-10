"""Deterministic post-filter concept canonicalization."""

from __future__ import annotations

import re

CONSOLIDATED_FIELDS: tuple[str, ...] = (
    "definitions",
    "technical_rules",
    "procedures",
    "terminology",
    "examples",
    "relationships",
)

_RE_MULTI_SPACE = re.compile(r"\s+")
_RE_LEADING_ARTICLES = re.compile(r"^(?:the|a|an)\s+")
_RE_LEADING_NARRATIVE_PREFIX = re.compile(
    r"^(?:"
    r"historical\s+usage\s+and\s+debate\s+on|"
    r"historical\s+usage\s+of|"
    r"history\s+of|"
    r"historical|"
    r"debate\s+on|"
    r"usage\s+of|"
    r"study\s+of|"
    r"analysis\s+of|"
    r"discussion\s+of|"
    r"role\s+of|"
    r"symbolism\s+of|"
    r"interpretation\s+of|"
    r"relative"
    r")\s+"
)

_DIRECT_CANONICAL_MAP: dict[str, str] = {
    "advantageou": "chrematistikos",
    "advantageous": "chrematistikos",
    "chreniatistiko house": "chrematistikos",
    "chreniatistikos house": "chrematistikos",
    "chrematistiko": "chrematistikos",
    "chrematistikos house": "chrematistikos",
    "oikodespote": "oikodespotes",
    "phasi": "phasis",
    "profitable house": "chrematistikos",
    "angularity of house": "house angularity",
    "whole sign house": "whole sign house system",
    "porphyry house": "porphyry house system",
    "equal house": "equal house system",
    "derived house": "derived houses",
    "angular house": "angular houses",
    "succedent house": "succedent houses",
    "cadent house": "cadent houses",
}

_PRESERVE_CLASSIFICATION_FORMS = {
    "house classification",
    "twelve house classification",
}


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _normalize_surface(text: str) -> str:
    normalized = text.lower().replace("-", " ")
    normalized = _RE_MULTI_SPACE.sub(" ", normalized).strip()
    return _RE_LEADING_ARTICLES.sub("", normalized).strip()


def _strip_narrative_prefix(text: str) -> str:
    return _RE_LEADING_NARRATIVE_PREFIX.sub("", text).strip()


def _canonicalize_nominal_pattern(text: str) -> str:
    if text in _PRESERVE_CLASSIFICATION_FORMS:
        return text

    if text.endswith(" classification"):
        head = text[: -len(" classification")].strip()
        if head:
            return f"classification of {head}"

    if text.endswith(" relationship"):
        head = text[: -len(" relationship")].strip()
        if head:
            return f"relationship of {head}"

    return text


def canonicalize_concept_name(concept: str) -> str:
    """Canonicalize a filtered concept name without changing extraction contracts."""
    canonical = _normalize_surface(concept)
    if not canonical:
        return ""

    canonical = _strip_narrative_prefix(canonical)
    canonical = _RE_LEADING_ARTICLES.sub("", canonical).strip()
    canonical = _DIRECT_CANONICAL_MAP.get(canonical, canonical)
    canonical = _canonicalize_nominal_pattern(canonical)
    canonical = _RE_MULTI_SPACE.sub(" ", canonical).strip()
    canonical = _RE_LEADING_ARTICLES.sub("", canonical).strip()
    return canonical


def _merge_payload(target: dict[str, object], payload: dict[str, object]) -> None:
    for field_name in CONSOLIDATED_FIELDS:
        target[field_name].extend(payload.get(field_name, []))
        target[field_name] = _dedupe_preserve_order(target[field_name])

    merged_chunks = set(target["source_chunks"])
    merged_chunks.update(payload.get("source_chunks", []))
    target["source_chunks"] = sorted(merged_chunks)


def canonicalize_concepts(concepts: dict) -> dict:
    """Canonicalize filtered concepts and merge entries that collapse together."""
    canonicalized: dict[str, dict[str, object]] = {}

    for concept_name, payload in concepts.items():
        canonical_name = canonicalize_concept_name(concept_name)
        if not canonical_name:
            continue

        if canonical_name not in canonicalized:
            canonicalized[canonical_name] = {
                "concept": canonical_name,
                "definitions": [],
                "technical_rules": [],
                "procedures": [],
                "terminology": [],
                "examples": [],
                "relationships": [],
                "source_chunks": [],
            }

        _merge_payload(canonicalized[canonical_name], payload)

    return canonicalized
