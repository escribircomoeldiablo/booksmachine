"""Deterministic promotion of structural taxonomy concepts from non-concept fields."""

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

_ALLOWLIST: tuple[str, ...] = (
    "angular houses",
    "succedent houses",
    "cadent houses",
    "epanaphora",
    "apoklino",
    "benefic houses",
    "malefic houses",
)

_STRUCTURAL_PARENT_SPECS: dict[str, dict[str, object]] = {
    "house angularity": {
        "aliases": ("house angularity", "angularity of house"),
        "concept_markers": ("angularity",),
        "children": ("angular houses", "succedent houses", "cadent houses"),
        "min_children": 3,
    },
    "favorability of house": {
        "aliases": ("favorability of house",),
        "concept_markers": ("favorability",),
        "children": ("benefic houses", "malefic houses"),
        "min_children": 2,
    },
}

_DEFINITION_HEAD_RE = re.compile(r"^\s*([^:]+):\s+.+$")
_PAREN_SUFFIX_RE = re.compile(r"^\s*([^(]+?)\s*\(.+\)\s*$")
_PROMOTED_SENTINEL = "_promoted_subconcept"
_PROMOTED_PARENT_SENTINEL = "_promoted_structural_parent"


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _normalize_text(value: str) -> str:
    return " ".join(value.lower().split()).strip()


def _new_payload(concept: str) -> dict[str, object]:
    return {
        "concept": concept,
        "definitions": [],
        "technical_rules": [],
        "procedures": [],
        "terminology": [],
        "examples": [],
        "relationships": [],
        "source_chunks": [],
        _PROMOTED_SENTINEL: True,
    }


def _new_parent_payload(concept: str, *, reason: str) -> dict[str, object]:
    payload = _new_payload(concept)
    payload.pop(_PROMOTED_SENTINEL, None)
    payload[_PROMOTED_PARENT_SENTINEL] = True
    payload["_promotion_reason"] = reason
    return payload


def _definition_head(value: str) -> str | None:
    match = _DEFINITION_HEAD_RE.match(value)
    if not match:
        return None
    return _normalize_text(match.group(1))


def _terminology_head(value: str) -> str:
    stripped = value.strip()
    paren_match = _PAREN_SUFFIX_RE.match(stripped)
    if paren_match:
        return _normalize_text(paren_match.group(1))
    return _normalize_text(stripped)


def _contains_exact_term(value: str, term: str) -> bool:
    pattern = re.compile(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", re.IGNORECASE)
    return bool(pattern.search(value))


def _relationship_supports_malefic(value: str) -> bool:
    normalized = _normalize_text(value)
    return "benefic houses include" in normalized and "malefic houses include" in normalized


def _collect_promoted_evidence(payload: dict[str, object], promoted: dict[str, dict[str, object]]) -> None:
    source_chunks = list(payload.get("source_chunks", []))

    for definition in payload.get("definitions", []):
        if not isinstance(definition, str):
            continue
        head = _definition_head(definition)
        if head not in _ALLOWLIST:
            continue
        bucket = promoted.setdefault(head, _new_payload(head))
        bucket["definitions"] = _dedupe_preserve_order(list(bucket["definitions"]) + [definition])
        bucket["source_chunks"] = sorted(set(list(bucket["source_chunks"]) + source_chunks))

    for term_value in payload.get("terminology", []):
        if not isinstance(term_value, str):
            continue
        head = _terminology_head(term_value)
        if head not in _ALLOWLIST:
            continue
        bucket = promoted.setdefault(head, _new_payload(head))
        bucket["terminology"] = _dedupe_preserve_order(list(bucket["terminology"]) + [term_value])
        bucket["source_chunks"] = sorted(set(list(bucket["source_chunks"]) + source_chunks))

    for relationship in payload.get("relationships", []):
        if not isinstance(relationship, str):
            continue
        if not _relationship_supports_malefic(relationship):
            continue
        bucket = promoted.setdefault("malefic houses", _new_payload("malefic houses"))
        bucket["relationships"] = _dedupe_preserve_order(list(bucket["relationships"]) + [relationship])
        bucket["source_chunks"] = sorted(set(list(bucket["source_chunks"]) + source_chunks))

    for promoted_name, bucket in promoted.items():
        if not any(chunk in source_chunks for chunk in bucket["source_chunks"]):
            continue
        for field_name in ("technical_rules", "procedures", "examples", "relationships"):
            matches = [
                value
                for value in payload.get(field_name, [])
                if isinstance(value, str) and _contains_exact_term(value, promoted_name)
            ]
            if matches:
                bucket[field_name] = _dedupe_preserve_order(list(bucket[field_name]) + matches)


def _parent_alias_match(head: str, aliases: tuple[str, ...]) -> bool:
    normalized = _normalize_text(head)
    return normalized in {_normalize_text(alias) for alias in aliases}


def _concept_mentions_markers(payload: dict[str, object], markers: tuple[str, ...]) -> bool:
    concept_name = _normalize_text(str(payload.get("concept", "")))
    return all(marker in concept_name for marker in markers)


def _collect_parent_support(
    payload: dict[str, object],
    *,
    parent_name: str,
    child_names: tuple[str, ...],
) -> tuple[dict[str, list[str]], set[str]]:
    collected: dict[str, list[str]] = {field_name: [] for field_name in CONSOLIDATED_FIELDS}
    observed_children: set[str] = set()

    for definition in payload.get("definitions", []):
        if not isinstance(definition, str):
            continue
        head = _definition_head(definition)
        if head == parent_name or head in child_names:
            collected["definitions"] = _dedupe_preserve_order(collected["definitions"] + [definition])
        if head in child_names:
            observed_children.add(head)

    for term_value in payload.get("terminology", []):
        if not isinstance(term_value, str):
            continue
        head = _terminology_head(term_value)
        if head == parent_name or head in child_names:
            collected["terminology"] = _dedupe_preserve_order(collected["terminology"] + [term_value])
        if head in child_names:
            observed_children.add(head)

    for field_name in ("technical_rules", "procedures", "examples", "relationships"):
        matches = [
            value
            for value in payload.get(field_name, [])
            if isinstance(value, str)
            and any(_contains_exact_term(value, name) for name in (parent_name, *child_names))
        ]
        if matches:
            collected[field_name] = _dedupe_preserve_order(collected[field_name] + matches)
            for child_name in child_names:
                if any(_contains_exact_term(value, child_name) for value in matches):
                    observed_children.add(child_name)

    return collected, observed_children


def _collect_promoted_parents(payload: dict[str, object], promoted: dict[str, dict[str, object]]) -> None:
    source_chunks = list(payload.get("source_chunks", []))
    for parent_name, spec in _STRUCTURAL_PARENT_SPECS.items():
        aliases = tuple(str(item) for item in spec["aliases"])
        markers = tuple(str(item) for item in spec["concept_markers"])
        child_names = tuple(str(item) for item in spec["children"])
        min_children = int(spec["min_children"])

        exact_parent_head = False
        for definition in payload.get("definitions", []):
            if not isinstance(definition, str):
                continue
            head = _definition_head(definition)
            if head and _parent_alias_match(head, aliases):
                exact_parent_head = True
                break

        support, observed_children = _collect_parent_support(
            payload,
            parent_name=parent_name,
            child_names=child_names,
        )
        family_supported = (
            _concept_mentions_markers(payload, markers)
            and len(observed_children & set(child_names)) >= min_children
        )
        if not exact_parent_head and not family_supported:
            continue

        reason = "definition_head_parent" if exact_parent_head else "family_child_support_parent"
        bucket = promoted.setdefault(parent_name, _new_parent_payload(parent_name, reason=reason))
        bucket["_promotion_reason"] = reason
        for field_name in CONSOLIDATED_FIELDS:
            bucket[field_name] = _dedupe_preserve_order(list(bucket[field_name]) + support[field_name])
        bucket["source_chunks"] = sorted(set(list(bucket["source_chunks"]) + source_chunks))


def promote_taxonomy_subconcepts(concepts: dict[str, dict[str, object]]) -> dict[str, dict[str, object]]:
    """Promote closed structural parents and taxonomy subconcepts into standalone nodes."""
    promoted = dict(concepts)
    promoted_nodes: dict[str, dict[str, object]] = {}
    promoted_parents: dict[str, dict[str, object]] = {}

    for payload in concepts.values():
        _collect_promoted_evidence(payload, promoted_nodes)
        _collect_promoted_parents(payload, promoted_parents)

    for concept_name, payload in promoted_nodes.items():
        existing = promoted.get(concept_name)
        if existing is None:
            promoted[concept_name] = payload
            continue
        merged = dict(existing)
        merged[_PROMOTED_SENTINEL] = True
        for field_name in CONSOLIDATED_FIELDS:
            merged[field_name] = _dedupe_preserve_order(list(existing.get(field_name, [])) + list(payload[field_name]))
        merged["source_chunks"] = sorted(set(list(existing.get("source_chunks", [])) + list(payload["source_chunks"])))
        promoted[concept_name] = merged

    for concept_name, payload in promoted_parents.items():
        existing = promoted.get(concept_name)
        if existing is None:
            promoted[concept_name] = payload
            continue
        merged = dict(existing)
        merged[_PROMOTED_PARENT_SENTINEL] = True
        merged["_promotion_reason"] = payload.get("_promotion_reason", "family_child_support_parent")
        for field_name in CONSOLIDATED_FIELDS:
            merged[field_name] = _dedupe_preserve_order(list(existing.get(field_name, [])) + list(payload[field_name]))
        merged["source_chunks"] = sorted(set(list(existing.get("source_chunks", [])) + list(payload["source_chunks"])))
        promoted[concept_name] = merged

    return promoted


def restore_promoted_subconcepts(
    filtered: dict[str, dict[str, object]],
    promoted: dict[str, dict[str, object]],
) -> dict[str, dict[str, object]]:
    """Restore promoted structural nodes that filter_valid_concepts may have dropped."""
    restored = dict(filtered)
    for concept_name, payload in promoted.items():
        if not payload.get(_PROMOTED_SENTINEL) and not payload.get(_PROMOTED_PARENT_SENTINEL):
            continue
        restored.setdefault(concept_name, payload)
    return restored
