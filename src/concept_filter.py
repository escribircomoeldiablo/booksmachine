"""Deterministic filtering for concept-level knowledge artifacts."""

from __future__ import annotations


_NON_NOMINAL_PREFIXES: tuple[str, ...] = (
    "interpret",
    "explain",
    "describe",
    "analyze",
    "evaluate",
    "determine",
    "assess",
)


def _has_real_core_content(payload: dict[str, object]) -> bool:
    return any(payload.get(field_name) for field_name in ("definitions", "technical_rules", "procedures"))


def _is_valid_concept_name(name: str) -> bool:
    normalized = " ".join(name.lower().split())
    if not normalized:
        return False
    word_count = len(normalized.split())
    if word_count > 6:
        return False
    if " as " in normalized:
        return False
    if normalized.count(" of ") > 1:
        return False
    if normalized.endswith(" relationship") and word_count > 4:
        return False
    if any(normalized.startswith(prefix) for prefix in _NON_NOMINAL_PREFIXES):
        return False
    return True


def filter_valid_concepts(concepts: dict) -> dict:
    """Return a filtered concept dictionary using deterministic validity rules."""
    filtered: dict = {}
    for concept_name, payload in concepts.items():
        if not _is_valid_concept_name(str(concept_name)):
            continue
        if not _has_real_core_content(payload):
            continue
        filtered[concept_name] = payload
    return filtered
