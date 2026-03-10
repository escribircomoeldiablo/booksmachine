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
PROCEDURAL_FIELDS: tuple[str, ...] = (
    "shared_procedure",
    "decision_rules",
    "preconditions",
    "exceptions",
    "author_variant_overrides",
    "procedure_outputs",
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
    "angularity and favorability of house": "favorability of house",
    "angularity and favorability of houses": "favorability of house",
    "chreniatistiko house": "chrematistikos",
    "chreniatistikos house": "chrematistikos",
    "chrematistiko": "chrematistikos",
    "chrematistikos house": "chrematistikos",
    "fortunate and unfortunate houses": "favorability of house",
    "good houses": "benefic houses",
    "good houses or places": "benefic houses",
    "fortunate houses": "benefic houses",
    "favorable houses": "benefic houses",
    "bad houses": "malefic houses",
    "bad houses or places": "malefic houses",
    "unfortunate houses": "malefic houses",
    "unfavorable houses": "malefic houses",
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
    "predominance of light": "predominator",
    "predominantia de la luz del secto": "predominator",
    "predominator epikratetor": "predominator",
    "predominator epikratetor as the source of the vital life force": "predominator",
    "predominator epikratetor as identification of the most potent life force in the nativity": "predominator",
    "predominator epikratetor as the source of the natives vital life force": "predominator",
    "the predominator as the principal determining planet or point for the life force": "predominator",
    "use of sect lights sun or moon in relation to predominator": "predominator",
    "house system relevance to identifying the predominator": "predominator",
    "oikodespotes as a lord assigned by the predominator that apportions years of life": "oikodespotes",
}

_PRESERVE_CLASSIFICATION_FORMS = {
    "house classification",
    "twelve house classification",
}
_PROCEDURAL_ANCHOR_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"\b(predominator determination|house system in determination of predominator|"
            r"predomination of the sect light|predominance of the lights?|predominance of light|"
            r"predominator\s*\(?epikratetor\)?|"
            r"predominaci[oó]n de luminares|luz predominante|predominating light|"
            r"procedimiento para determinar la luz predominante)\b",
            re.IGNORECASE,
        ),
        "predominator",
    ),
    (
        re.compile(
            r"\b(oikodespotes|master of the nativity|lord assigned by the predominator)\b",
            re.IGNORECASE,
        ),
        "oikodespotes",
    ),
)


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


def _procedural_anchor(text: str) -> str:
    for pattern, target in _PROCEDURAL_ANCHOR_PATTERNS:
        if pattern.search(text):
            return target
    return text


def canonicalize_concept_name(concept: str) -> str:
    """Canonicalize a filtered concept name without changing extraction contracts."""
    canonical = _normalize_surface(concept)
    if not canonical:
        return ""

    canonical = _strip_narrative_prefix(canonical)
    canonical = _RE_LEADING_ARTICLES.sub("", canonical).strip()
    canonical = _DIRECT_CANONICAL_MAP.get(canonical, canonical)
    canonical = _procedural_anchor(canonical)
    canonical = _canonicalize_nominal_pattern(canonical)
    canonical = _RE_MULTI_SPACE.sub(" ", canonical).strip()
    canonical = _RE_LEADING_ARTICLES.sub("", canonical).strip()
    return canonical


def _merge_payload(target: dict[str, object], payload: dict[str, object]) -> None:
    for field_name in CONSOLIDATED_FIELDS:
        target[field_name].extend(payload.get(field_name, []))
        target[field_name] = _dedupe_preserve_order(target[field_name])
    for field_name in PROCEDURAL_FIELDS:
        target[field_name].extend(payload.get(field_name, []))
        deduped: list[object] = []
        for item in target[field_name]:
            if item not in deduped:
                deduped.append(item)
        target[field_name] = deduped
    for field_name in ("concept_evidence", "procedure_evidence"):
        source_map = payload.get(field_name, {})
        target_map = target.get(field_name, {})
        if not isinstance(source_map, dict) or not isinstance(target_map, dict):
            target[field_name] = source_map if source_map else target_map
            continue
        merged_map: dict[str, object] = {key: list(value) if isinstance(value, list) else value for key, value in target_map.items()}
        for key, value in source_map.items():
            if isinstance(value, list):
                existing = merged_map.setdefault(key, [])
                if isinstance(existing, list):
                    for item in value:
                        if item not in existing:
                            existing.append(item)
                else:
                    merged_map[key] = list(value)
            elif key not in merged_map:
                merged_map[key] = value
        target[field_name] = merged_map

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
                "shared_procedure": [],
                "decision_rules": [],
                "preconditions": [],
                "exceptions": [],
                "author_variant_overrides": [],
                "procedure_outputs": [],
                "concept_evidence": {},
                "procedure_evidence": {},
                "source_chunks": [],
            }

        _merge_payload(canonicalized[canonical_name], payload)

    return canonicalized
