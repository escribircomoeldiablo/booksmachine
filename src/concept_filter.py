"""Deterministic filtering for concept-level knowledge artifacts."""

from __future__ import annotations

import re


_NON_NOMINAL_PREFIXES: tuple[str, ...] = (
    "interpret",
    "explain",
    "describe",
    "analyze",
    "evaluate",
    "determine",
    "assess",
)
_NARRATIVE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^relationship between\b"),
    re.compile(r"^template for\b"),
    re.compile(r"^inclusion of\b"),
    re.compile(r"^planet in house\b"),
    re.compile(r"\bcalculation procedure\b"),
    re.compile(r"\brelevance in\b"),
    re.compile(r"\bin traditional astrology\b"),
)
_AS_NARRATIVE_SPLIT_RE = re.compile(r"^(?P<head>.+?)\s+as\s+.+$")
_LEADING_ARTICLE_RE = re.compile(r"\b(?:the|a|an)\b")


def _normalize_anchor_text(value: str) -> str:
    normalized = " ".join(value.lower().split())
    normalized = _LEADING_ARTICLE_RE.sub(" ", normalized)
    return " ".join(normalized.split())


def _has_real_core_content(payload: dict[str, object]) -> bool:
    if payload.get("_promoted_structural_parent"):
        return bool(payload.get("source_chunks")) and any(
            payload.get(field_name) for field_name in ("definitions", "terminology", "relationships")
        )
    if any(payload.get(field_name) for field_name in ("definitions", "technical_rules", "procedures")):
        return True

    concept_name = _normalize_anchor_text(str(payload.get("concept", "")))
    terminology = payload.get("terminology", [])
    if concept_name and isinstance(terminology, list):
        normalized_terms = {_normalize_anchor_text(str(value)) for value in terminology if isinstance(value, str)}
        if concept_name in normalized_terms:
            return True

    return False


def _nominal_candidate(name: str) -> str:
    normalized = " ".join(name.lower().split())
    match = _AS_NARRATIVE_SPLIT_RE.match(normalized)
    if match:
        head = " ".join(match.group("head").split()).strip()
        if " of " not in head:
            return head
    return normalized


def _is_valid_concept_name(name: str) -> bool:
    normalized = _nominal_candidate(name)
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
    if any(pattern.search(normalized) for pattern in _NARRATIVE_PATTERNS):
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
