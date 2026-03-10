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
PROCEDURAL_FIELDS: tuple[str, ...] = (
    "shared_procedure",
    "decision_rules",
    "preconditions",
    "exceptions",
    "author_variant_overrides",
    "procedure_outputs",
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

_PROMOTABLE_ALIAS_MAP: dict[str, str] = {
    "angular house": "angular houses",
    "angular houses": "angular houses",
    "succedent house": "succedent houses",
    "succedent houses": "succedent houses",
    "cadent house": "cadent houses",
    "cadent houses": "cadent houses",
    "good houses": "benefic houses",
    "good houses or places": "benefic houses",
    "fortunate houses": "benefic houses",
    "favorable houses": "benefic houses",
    "benefic houses": "benefic houses",
    "bad houses": "malefic houses",
    "bad houses or places": "malefic houses",
    "unfortunate houses": "malefic houses",
    "unfavorable houses": "malefic houses",
    "malefic houses": "malefic houses",
}

_STRUCTURAL_PARENT_SPECS: dict[str, dict[str, object]] = {
    "house angularity": {
        "aliases": ("house angularity", "angularity of house"),
        "concept_markers": ("angularity",),
        "children": ("angular houses", "succedent houses", "cadent houses"),
        "min_children": 3,
    },
    "favorability of house": {
        "aliases": (
            "favorability of house",
            "favorability of houses",
            "fortunate and unfortunate houses",
        ),
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
        "shared_procedure": [],
        "decision_rules": [],
        "preconditions": [],
        "exceptions": [],
        "author_variant_overrides": [],
        "procedure_outputs": [],
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


def _canonical_promotable_name(value: str) -> str:
    return _PROMOTABLE_ALIAS_MAP.get(_normalize_text(value), _normalize_text(value))


def _contains_promotable_alias(value: str, canonical_name: str) -> bool:
    normalized = _normalize_text(value)
    aliases = [alias for alias, mapped in _PROMOTABLE_ALIAS_MAP.items() if mapped == canonical_name]
    if not aliases:
        aliases = [canonical_name]
    return any(_contains_exact_term(normalized, alias) for alias in aliases)


def _display_label(value: str) -> str:
    if not value:
        return value
    return value[0].upper() + value[1:]


def _relationship_supports_malefic(value: str) -> bool:
    normalized = _normalize_text(value)
    return "benefic houses include" in normalized and "malefic houses include" in normalized


def _collect_promoted_evidence(payload: dict[str, object], promoted: dict[str, dict[str, object]]) -> None:
    source_chunks = list(payload.get("source_chunks", []))

    for definition in payload.get("definitions", []):
        if not isinstance(definition, str):
            continue
        head = _canonical_promotable_name(_definition_head(definition) or "")
        if head not in _ALLOWLIST:
            continue
        bucket = promoted.setdefault(head, _new_payload(head))
        bucket["definitions"] = _dedupe_preserve_order(list(bucket["definitions"]) + [definition])
        bucket["source_chunks"] = sorted(set(list(bucket["source_chunks"]) + source_chunks))

    for term_value in payload.get("terminology", []):
        if not isinstance(term_value, str):
            continue
        head = _canonical_promotable_name(_terminology_head(term_value))
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
        for field_name in ("technical_rules", "procedures", "examples", "relationships"):
            matches = [
                value
                for value in payload.get(field_name, [])
                if isinstance(value, str) and _contains_promotable_alias(value, promoted_name)
            ]
            if matches:
                bucket[field_name] = _dedupe_preserve_order(list(bucket[field_name]) + matches)
                bucket["source_chunks"] = sorted(set(list(bucket["source_chunks"]) + source_chunks))


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
        head = _canonical_promotable_name(_definition_head(definition) or "")
        if head == parent_name or head in child_names:
            collected["definitions"] = _dedupe_preserve_order(collected["definitions"] + [definition])
        if head in child_names:
            observed_children.add(head)
            collected["terminology"] = _dedupe_preserve_order(collected["terminology"] + [_display_label(head)])

    for term_value in payload.get("terminology", []):
        if not isinstance(term_value, str):
            continue
        head = _canonical_promotable_name(_terminology_head(term_value))
        if head == parent_name or head in child_names:
            collected["terminology"] = _dedupe_preserve_order(
                collected["terminology"] + [_display_label(head) if head in child_names else term_value]
            )
        if head in child_names:
            observed_children.add(head)

        for field_name in ("technical_rules", "procedures", "examples", "relationships"):
            matches = [
                value
                for value in payload.get(field_name, [])
                if isinstance(value, str)
                and (
                _contains_exact_term(value, parent_name)
                or any(_contains_promotable_alias(value, child_name) for child_name in child_names)
            )
        ]
        if matches:
            collected[field_name] = _dedupe_preserve_order(collected[field_name] + matches)
            for child_name in child_names:
                if any(_contains_promotable_alias(value, child_name) for value in matches):
                    observed_children.add(child_name)
                    collected["terminology"] = _dedupe_preserve_order(
                        collected["terminology"] + [_display_label(child_name)]
                    )

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
            (_concept_mentions_markers(payload, markers) or _parent_alias_match(str(payload.get("concept", "")), aliases))
            and len(observed_children & set(child_names)) >= min_children
        )
        if not exact_parent_head and not family_supported:
            continue

        reason = "definition_head_parent" if exact_parent_head else "family_child_support_parent"
        bucket = promoted.setdefault(parent_name, _new_parent_payload(parent_name, reason=reason))
        bucket["_promotion_reason"] = reason
        for field_name in CONSOLIDATED_FIELDS:
            bucket[field_name] = _dedupe_preserve_order(list(bucket[field_name]) + support[field_name])
        for field_name in PROCEDURAL_FIELDS:
            bucket[field_name] = list(bucket.get(field_name, []))
        bucket["source_chunks"] = sorted(set(list(bucket["source_chunks"]) + source_chunks))


def _promote_parents_from_closed_family_chunks(
    concepts: dict[str, dict[str, object]],
    promoted_nodes: dict[str, dict[str, object]],
    promoted_parents: dict[str, dict[str, object]],
) -> None:
    promoted_lookup = {name: set(payload.get("source_chunks", [])) for name, payload in promoted_nodes.items()}

    for payload in concepts.values():
        concept_name = _normalize_text(str(payload.get("concept", "")))
        payload_chunks = set(payload.get("source_chunks", []))
        if not payload_chunks:
            continue

        for parent_name, spec in _STRUCTURAL_PARENT_SPECS.items():
            aliases = tuple(str(item) for item in spec["aliases"])
            if not _parent_alias_match(concept_name, aliases):
                continue

            child_names = tuple(str(item) for item in spec["children"])
            shared_children = [
                child_name
                for child_name in child_names
                if payload_chunks & promoted_lookup.get(child_name, set())
            ]
            if len(shared_children) < int(spec["min_children"]):
                continue

            shared_chunks = sorted(
                set.intersection(*(payload_chunks & promoted_lookup.get(child_name, set()) for child_name in shared_children))
            )
            if not shared_chunks:
                continue

            bucket = promoted_parents.setdefault(
                parent_name,
                _new_parent_payload(parent_name, reason="family_child_support_parent"),
            )
            bucket["_promotion_reason"] = "family_child_support_parent"
            bucket["terminology"] = _dedupe_preserve_order(
                list(bucket["terminology"]) + [_display_label(child_name) for child_name in shared_children]
            )
            bucket["source_chunks"] = sorted(set(list(bucket["source_chunks"]) + shared_chunks))


def promote_taxonomy_subconcepts(concepts: dict[str, dict[str, object]]) -> dict[str, dict[str, object]]:
    """Promote closed structural parents and taxonomy subconcepts into standalone nodes."""
    promoted = dict(concepts)
    promoted_nodes: dict[str, dict[str, object]] = {}
    promoted_parents: dict[str, dict[str, object]] = {}

    for payload in concepts.values():
        _collect_promoted_evidence(payload, promoted_nodes)
        _collect_promoted_parents(payload, promoted_parents)

    for payload in concepts.values():
        _collect_promoted_evidence(payload, promoted_nodes)

    _promote_parents_from_closed_family_chunks(concepts, promoted_nodes, promoted_parents)

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
