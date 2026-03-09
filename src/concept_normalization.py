"""Deterministic concept name normalization for consolidation."""

from __future__ import annotations

import re

_RE_NON_ALNUM_SPACE = re.compile(r"[^a-z0-9\s]")
_RE_MULTI_SPACE = re.compile(r"\s+")
_RE_LEADING_ARTICLES = re.compile(r"^(?:the|a|an)\s+")


def _singularize_token(token: str) -> str:
    if len(token) <= 3:
        return token
    if token.endswith("houses"):
        return token[:-1]  # houses -> house
    if token.endswith("systems"):
        return token[:-1]  # systems -> system
    if token.endswith("sses"):
        return token
    if token.endswith("s"):
        return token[:-1]
    return token


def _normalize_whole_sign_variants(text: str) -> str:
    # Canonicalize common superficial variants around the same concept cluster.
    if text in {"whole sign house", "whole sign houses", "whole sign system"}:
        return "whole sign house system"
    return text


def _strip_leading_articles(text: str) -> str:
    return _RE_LEADING_ARTICLES.sub("", text).strip()


def _canonicalize_discursive_phrase(text: str) -> str:
    # Collapse common discourse-heavy concept phrasings into stable heads.
    patterns: tuple[tuple[re.Pattern[str], str], ...] = (
        (
            re.compile(r"^classifications?\s+(?:and\s+topics?\s+|and\s+valuation\s+)?of\s+(.+)$"),
            r"\1 classification",
        ),
        (
            re.compile(r"^interpretation\s+of\s+(.+)$"),
            r"\1 interpretation",
        ),
        (
            re.compile(r"^relationship\s+of\s+(.+?)\s+to\s+(.+)$"),
            r"\1 \2 relationship",
        ),
        (
            re.compile(r"^origin(?:\s+and\s+development)?\s+of\s+(.+)$"),
            r"\1 origin",
        ),
        (
            re.compile(r"^topic\s+of\s+(.+)$"),
            r"\1 topic",
        ),
        (
            re.compile(r"^condition\s+of\s+(.+)$"),
            r"\1 condition",
        ),
    )
    normalized = text
    for pattern, replacement in patterns:
        updated = pattern.sub(replacement, normalized)
        if updated != normalized:
            normalized = updated.strip()
            break
    normalized = re.sub(r"\b(?:the|a|an)\b", " ", normalized)
    return _RE_MULTI_SPACE.sub(" ", normalized).strip()


def normalize_concept_name(concept: str) -> str:
    """Normalize a concept string into a deterministic canonical identifier."""
    normalized = concept.lower().replace("-", " ")
    normalized = _RE_NON_ALNUM_SPACE.sub(" ", normalized)
    normalized = _RE_MULTI_SPACE.sub(" ", normalized).strip()
    if not normalized:
        return ""

    normalized = _strip_leading_articles(normalized)
    normalized = _canonicalize_discursive_phrase(normalized)
    tokens = [_singularize_token(token) for token in normalized.split()]
    normalized = " ".join(tokens)
    normalized = _RE_MULTI_SPACE.sub(" ", normalized).strip()
    return _normalize_whole_sign_variants(normalized)


def normalize_concepts(concepts: list[str]) -> list[str]:
    """Normalize and deduplicate concepts preserving first-seen order."""
    out: list[str] = []
    seen: set[str] = set()
    for concept in concepts:
        canonical = normalize_concept_name(concept)
        if not canonical or canonical in seen:
            continue
        seen.add(canonical)
        out.append(canonical)
    return out
