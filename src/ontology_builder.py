"""Deterministic ontology building on top of consolidated concepts."""

from __future__ import annotations

import json
from pathlib import Path

CONSOLIDATED_FIELDS: tuple[str, ...] = (
    "definitions",
    "technical_rules",
    "procedures",
    "terminology",
    "examples",
    "relationships",
)

ONTOLOGY_FIELDS: tuple[str, ...] = (
    "aliases",
    "definitions",
    "technical_rules",
    "procedures",
    "terminology",
    "examples",
    "relationships",
    "parent_concepts",
    "child_concepts",
    "related_concepts",
)

_EQUIVALENCE_FAMILIES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "house angularity",
        (
            "house angularity",
            "angularity of house",
        ),
    ),
    (
        "whole sign house system",
        (
            "whole sign house system",
            "whole sign houses",
            "whole-sign houses",
        ),
    ),
)

_HOUSE_ANGULARITY_CHILDREN: tuple[str, ...] = (
    "angular houses",
    "succedent houses",
    "cadent houses",
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


def _dedupe_ints_sorted(items: list[int]) -> list[int]:
    return sorted(set(items))


def _new_ontology_node(concept: str) -> dict[str, object]:
    return {
        "concept": concept,
        "aliases": [],
        "definitions": [],
        "technical_rules": [],
        "procedures": [],
        "terminology": [],
        "examples": [],
        "relationships": [],
        "source_chunks": [],
        "parent_concepts": [],
        "child_concepts": [],
        "related_concepts": [],
        "node_kind": "topic",
    }


def _copy_to_ontology_node(payload: dict[str, object], *, concept: str) -> dict[str, object]:
    node = _new_ontology_node(concept)
    for field_name in CONSOLIDATED_FIELDS:
        node[field_name] = list(payload.get(field_name, []))
    node["source_chunks"] = list(payload.get("source_chunks", []))
    return node


def _merge_concept_payload(target: dict[str, object], source: dict[str, object]) -> None:
    for field_name in CONSOLIDATED_FIELDS:
        target[field_name] = _dedupe_preserve_order(list(target[field_name]) + list(source.get(field_name, [])))

    target["source_chunks"] = _dedupe_ints_sorted(
        list(target["source_chunks"]) + list(source.get("source_chunks", []))
    )


def _append_relation(node: dict[str, object], field_name: str, value: str) -> None:
    if not value:
        return
    node[field_name] = _dedupe_preserve_order(list(node[field_name]) + [value])


def _canonical_family_for_concept(concept: str) -> str:
    for canonical, members in _EQUIVALENCE_FAMILIES:
        if concept in members:
            return canonical
    return concept


def resolve_equivalence_families(concepts: dict[str, dict[str, object]]) -> tuple[dict[str, dict[str, object]], dict[str, str]]:
    """Merge exact equivalence families into stable ontology nodes."""
    merged: dict[str, dict[str, object]] = {}
    canonical_map: dict[str, str] = {}

    for concept_name, payload in concepts.items():
        canonical_name = _canonical_family_for_concept(concept_name)
        canonical_map[concept_name] = canonical_name

        if canonical_name not in merged:
            merged[canonical_name] = _copy_to_ontology_node(payload, concept=canonical_name)
        else:
            _merge_concept_payload(merged[canonical_name], payload)

        if concept_name != canonical_name:
            merged[canonical_name]["aliases"] = _dedupe_preserve_order(
                list(merged[canonical_name]["aliases"]) + [concept_name]
            )

    return merged, canonical_map


def apply_taxonomy_links(
    concepts: dict[str, dict[str, object]],
    canonical_map: dict[str, str],
    taxonomy_links: list[dict[str, object]] | None = None,
    *,
    enable_legacy_fallback: bool = True,
) -> dict[str, dict[str, object]]:
    """Link taxonomy relationships without merging distinct nodes."""
    linked: dict[str, dict[str, object]] = {}
    for concept_name, payload in concepts.items():
        node = _new_ontology_node(concept_name)
        for field_name in ONTOLOGY_FIELDS:
            if field_name in payload:
                node[field_name] = list(payload[field_name])
        node["source_chunks"] = list(payload.get("source_chunks", []))
        node["node_kind"] = str(payload.get("node_kind", "topic"))
        linked[concept_name] = node

    def _apply_parent_child(parent_name: str, child_name: str, *, create_parent: bool = False) -> None:
        if not parent_name or not child_name or parent_name == child_name:
            return
        if create_parent:
            linked.setdefault(parent_name, _new_ontology_node(parent_name))
        if parent_name not in linked or child_name not in linked:
            return
        parent = linked[parent_name]
        child = linked[child_name]
        child["node_kind"] = "subconcept"
        _append_relation(child, "parent_concepts", parent_name)
        _append_relation(parent, "child_concepts", child_name)
        parent["source_chunks"] = _dedupe_ints_sorted(
            list(parent["source_chunks"]) + list(child.get("source_chunks", []))
        )
        if parent["child_concepts"]:
            parent["node_kind"] = "classification"

    remapped_links: list[tuple[str, str]] = []
    if taxonomy_links:
        seen_pairs: set[tuple[str, str]] = set()
        for link in taxonomy_links:
            parent_name = canonical_map.get(str(link.get("parent", "")), str(link.get("parent", "")))
            child_name = canonical_map.get(str(link.get("child", "")), str(link.get("child", "")))
            pair = (parent_name, child_name)
            if not parent_name or not child_name or parent_name == child_name or pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            remapped_links.append(pair)

        child_order = {name: index for index, name in enumerate(_HOUSE_ANGULARITY_CHILDREN)}
        remapped_links.sort(key=lambda pair: (pair[0], child_order.get(pair[1], len(child_order)), pair[1]))
        for parent_name, child_name in remapped_links:
            _apply_parent_child(parent_name, child_name)

    present_children = [name for name in _HOUSE_ANGULARITY_CHILDREN if name in linked]
    if enable_legacy_fallback and present_children:
        for child_name in present_children:
            if ("house angularity", child_name) in remapped_links:
                continue
            _apply_parent_child("house angularity", child_name, create_parent=True)

        if "house angularity" in linked and "chrematistikos" in linked:
            _append_relation(linked["house angularity"], "related_concepts", "chrematistikos")
            _append_relation(linked["chrematistikos"], "related_concepts", "house angularity")

    return linked


def build_ontology(
    concepts: dict[str, dict[str, object]],
    taxonomy_links: list[dict[str, object]] | None = None,
    *,
    enable_legacy_fallback: bool = True,
) -> dict[str, dict[str, object]]:
    """Build the final ontology artifact from canonical concept payloads."""
    merged, canonical_map = resolve_equivalence_families(concepts)
    return apply_taxonomy_links(
        merged,
        canonical_map,
        taxonomy_links=taxonomy_links,
        enable_legacy_fallback=enable_legacy_fallback,
    )


def build_ontology_output_path(input_path: str, output_folder: str | None = None) -> str:
    """Build the ontology-level output path for a chunk JSONL input."""
    source_path = Path(input_path)
    folder = Path(output_folder) if output_folder else source_path.parent
    if source_path.name.endswith("_knowledge_chunks.jsonl"):
        filename = source_path.name.replace("_knowledge_chunks.jsonl", "_knowledge_ontology.json")
    else:
        filename = f"{source_path.stem}_knowledge_ontology.json"
    return str(folder / filename)


def export_ontology(ontology: dict[str, dict[str, object]], output_path: str) -> None:
    """Persist ontology concepts as a UTF-8 JSON artifact."""
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as handle:
        json.dump(ontology, handle, ensure_ascii=False, indent=2)
