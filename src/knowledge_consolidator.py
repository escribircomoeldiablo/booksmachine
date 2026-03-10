"""Post-processing consolidation from chunk knowledge into concept knowledge."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from .concept_canonicalizer import canonicalize_concepts
from .concept_filter import filter_valid_concepts
from .concept_normalization import normalize_concept_name
from .config import ONTOLOGY_ENABLE_INFERRED_TAXONOMY
from .concept_subconcept_promoter import promote_taxonomy_subconcepts, restore_promoted_subconcepts
from .ontology_builder import build_ontology, build_ontology_output_path, export_ontology
from .taxonomy_inference import infer_taxonomy_links

CONSOLIDATED_FIELDS: tuple[str, ...] = (
    "definitions",
    "technical_rules",
    "procedures",
    "terminology",
    "examples",
    "relationships",
)

_CHUNK_INDEX_RE = re.compile(r"^chunk_(\d+)_")
_DEFINITION_HEAD_RE = re.compile(r"^\s*([^:]+):\s+.+$")
_PAREN_SUFFIX_RE = re.compile(r"^\s*([^(]+?)\s*\(.+\)\s*$")


def _derive_audit_path(path: str) -> Path:
    source_path = Path(path)
    if source_path.name.endswith("_knowledge_chunks.jsonl"):
        return source_path.with_name(source_path.name.replace("_knowledge_chunks.jsonl", "_knowledge_audit.jsonl"))
    return source_path.with_name(f"{source_path.stem}_audit.jsonl")


def _load_audit_map(path: str) -> dict[str, dict[str, object]]:
    audit_path = _derive_audit_path(path)
    if not audit_path.exists():
        return {}

    audit_map: dict[str, dict[str, object]] = {}
    with audit_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            record = json.loads(stripped)
            chunk_id = str(record.get("chunk_id", "")).strip()
            if chunk_id:
                audit_map[chunk_id] = record
    return audit_map


def _extract_chunk_index(record: dict[str, object], fallback_index: int) -> int:
    chunk_index = record.get("chunk_index")
    if isinstance(chunk_index, int):
        return chunk_index

    chunk_id = str(record.get("chunk_id", "")).strip()
    match = _CHUNK_INDEX_RE.match(chunk_id)
    if match:
        return int(match.group(1)) + 1
    return fallback_index


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _normalize_surface(value: str) -> str:
    normalized = value.lower().replace("-", " ")
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    return " ".join(normalized.split()).strip()


def _surface_variants(concept: str) -> set[str]:
    variants = {concept}
    if concept.endswith(" house"):
        variants.add(f"{concept[:-6]} houses")
    if concept.endswith(" houses"):
        variants.add(f"{concept[:-7]} house")
    if concept.endswith(" system"):
        variants.add(f"{concept[:-7]} systems")
    if concept.endswith(" systems"):
        variants.add(f"{concept[:-8]} system")
    return {variant for variant in variants if variant}


def _contains_exact_term(value: str, term: str) -> bool:
    pattern = re.compile(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", re.IGNORECASE)
    return bool(pattern.search(value))


def _text_supports_concept(value: str, concept: str) -> bool:
    surface = _normalize_surface(value)
    if not surface:
        return False
    return any(_contains_exact_term(surface, variant) for variant in _surface_variants(concept))


def _definition_head(value: str) -> str | None:
    match = _DEFINITION_HEAD_RE.match(value)
    if not match:
        return None
    return normalize_concept_name(match.group(1))


def _terminology_head(value: str) -> str:
    stripped = value.strip()
    paren_match = _PAREN_SUFFIX_RE.match(stripped)
    if paren_match:
        stripped = paren_match.group(1)
    return normalize_concept_name(stripped)


def _should_project_chunk_locally(chunk: dict[str, object]) -> bool:
    chunk_type = str(chunk.get("_chunk_type", "")).strip().lower()
    decision = str(chunk.get("_decision", "")).strip().lower()
    concepts = chunk.get("_normalized_concepts", [])
    concept_count = len(concepts) if isinstance(concepts, list) else 0
    if chunk_type in {"glossary", "captions_tables_charts"}:
        return True
    if decision == "extract_degraded":
        return True
    return concept_count >= 5


def _field_values_for_concept(chunk: dict[str, object], concept: str, field_name: str) -> list[str]:
    values = chunk.get(field_name, [])
    if not isinstance(values, list):
        return []
    if not _should_project_chunk_locally(chunk):
        return [value for value in values if isinstance(value, str)]

    matched: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        if field_name == "definitions" and _definition_head(value) == concept:
            matched.append(value)
            continue
        if field_name == "terminology" and _terminology_head(value) == concept:
            matched.append(value)
            continue
        if _text_supports_concept(value, concept):
            matched.append(value)
    return matched


def load_chunk_knowledge(path: str) -> list[dict]:
    """Load chunk-level JSONL records, excluding skipped chunks when audit data exists."""
    audit_map = _load_audit_map(path)
    loaded: list[dict] = []

    with Path(path).open("r", encoding="utf-8") as handle:
        for fallback_index, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            record = json.loads(stripped)
            chunk_id = str(record.get("chunk_id", "")).strip()
            audit_record = audit_map.get(chunk_id, {})
            decision = audit_record.get("decision")
            if decision == "skip":
                continue

            materialized = dict(record)
            materialized["chunk_index"] = _extract_chunk_index(audit_record or record, fallback_index)
            materialized["_decision"] = str(audit_record.get("decision", "")).strip().lower()
            materialized["_chunk_type"] = str(audit_record.get("chunk_type", "")).strip().lower()
            loaded.append(materialized)

    return loaded


def normalize_concepts(chunks: list[dict]) -> list[dict]:
    """Attach normalized concept identifiers to each chunk without altering source text."""
    normalized_chunks: list[dict] = []
    for chunk in chunks:
        normalized_chunk = dict(chunk)
        concepts = chunk.get("concepts", [])
        normalized_concepts: list[str] = []
        for concept in concepts:
            canonical = normalize_concept_name(concept)
            if canonical:
                normalized_concepts.append(canonical)
        normalized_chunk["_normalized_concepts"] = _dedupe_preserve_order(normalized_concepts)
        normalized_chunks.append(normalized_chunk)
    return normalized_chunks


def build_concept_index(chunks: list[dict]) -> dict:
    """Build normalized concept -> chunk_index mapping preserving first-seen order."""
    concept_index: dict[str, list[int]] = {}
    for chunk in chunks:
        chunk_index = int(chunk["chunk_index"])
        for concept in chunk.get("_normalized_concepts", []):
            bucket = concept_index.setdefault(concept, [])
            if chunk_index not in bucket:
                bucket.append(chunk_index)
    return concept_index


def merge_concept_knowledge(concept_index: dict, chunks: list[dict]) -> dict:
    """Merge chunk-level knowledge into a concept-keyed dictionary."""
    merged: dict[str, dict[str, object]] = {}
    chunk_lookup = {int(chunk["chunk_index"]): chunk for chunk in chunks}

    for concept, source_chunks in concept_index.items():
        payload: dict[str, object] = {
            "concept": concept,
            "definitions": [],
            "technical_rules": [],
            "procedures": [],
            "terminology": [],
            "examples": [],
            "relationships": [],
            "source_chunks": list(source_chunks),
        }
        for chunk_index in source_chunks:
            chunk = chunk_lookup.get(chunk_index)
            if not chunk:
                continue
            for field_name in CONSOLIDATED_FIELDS:
                target = payload[field_name]
                target.extend(_field_values_for_concept(chunk, concept, field_name))

        for field_name in CONSOLIDATED_FIELDS:
            payload[field_name] = _dedupe_preserve_order(payload[field_name])

        merged[concept] = payload

    return merged


def export_concepts(concepts: dict, output_path: str) -> None:
    """Persist consolidated concepts as a UTF-8 JSON artifact."""
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as handle:
        json.dump(concepts, handle, ensure_ascii=False, indent=2)


def build_concepts_output_path(input_path: str, output_folder: str | None = None) -> str:
    """Build the concept-level knowledge output path for a chunk JSONL input."""
    source_path = Path(input_path)
    folder = Path(output_folder) if output_folder else source_path.parent
    if source_path.name.endswith("_knowledge_chunks.jsonl"):
        filename = source_path.name.replace("_knowledge_chunks.jsonl", "_knowledge_concepts.json")
    else:
        filename = f"{source_path.stem}_knowledge_concepts.json"
    return str(folder / filename)


def _build_taxonomy_output_path(input_path: str, output_folder: str | None = None) -> str:
    """Build the taxonomy-level audit output path for a chunk JSONL input."""
    source_path = Path(input_path)
    folder = Path(output_folder) if output_folder else source_path.parent
    if source_path.name.endswith("_knowledge_chunks.jsonl"):
        filename = source_path.name.replace("_knowledge_chunks.jsonl", "_knowledge_taxonomy.json")
    else:
        filename = f"{source_path.stem}_knowledge_taxonomy.json"
    return str(folder / filename)


def _build_canonical_concepts(path: str) -> dict[str, dict[str, object]]:
    """Build canonicalized concept payloads from one chunk knowledge artifact."""
    chunks = load_chunk_knowledge(path)
    normalized_chunks = normalize_concepts(chunks)
    concept_index = build_concept_index(normalized_chunks)
    concepts = merge_concept_knowledge(concept_index, normalized_chunks)
    concepts = promote_taxonomy_subconcepts(concepts)
    concepts = restore_promoted_subconcepts(filter_valid_concepts(concepts), concepts)
    return canonicalize_concepts(concepts)


def _build_taxonomy_audit_payload(path: str) -> dict[str, list[dict[str, object]]]:
    """Build inferred taxonomy audit payload from canonical concepts."""
    concepts = _build_canonical_concepts(path)
    return infer_taxonomy_links(concepts)


def _taxonomy_edges(ontology: dict[str, dict[str, object]]) -> list[dict[str, str]]:
    """Extract stable parent-child taxonomy edges from an ontology payload."""
    edges: list[dict[str, str]] = []
    for parent_name in sorted(ontology):
        child_concepts = ontology[parent_name].get("child_concepts", [])
        if not isinstance(child_concepts, list):
            continue
        for child_name in child_concepts:
            if not isinstance(child_name, str):
                continue
            edges.append({"parent": parent_name, "child": child_name})
    return edges


def _build_taxonomy_comparison_payload(path: str) -> dict[str, list[dict[str, object]]]:
    """Compare inferred-only taxonomy application against inferred-plus-legacy fallback."""
    concepts = _build_canonical_concepts(path)
    taxonomy = infer_taxonomy_links(concepts)
    taxonomy_links = list(taxonomy["links"])
    inferred_only = build_ontology(
        concepts,
        taxonomy_links=taxonomy_links,
        enable_legacy_fallback=False,
    )
    inferred_plus_legacy = build_ontology(
        concepts,
        taxonomy_links=taxonomy_links,
        enable_legacy_fallback=True,
    )
    inferred_only_edges = _taxonomy_edges(inferred_only)
    inferred_plus_legacy_edges = _taxonomy_edges(inferred_plus_legacy)
    inferred_only_pairs = {(edge["parent"], edge["child"]) for edge in inferred_only_edges}
    legacy_only_edges = [
        edge
        for edge in inferred_plus_legacy_edges
        if (edge["parent"], edge["child"]) not in inferred_only_pairs
    ]
    return {
        "links": taxonomy_links,
        "inferred_only_edges": inferred_only_edges,
        "inferred_plus_legacy_edges": inferred_plus_legacy_edges,
        "legacy_only_edges": legacy_only_edges,
    }


def _export_taxonomy_audit(payload: dict[str, list[dict[str, object]]], output_path: str) -> None:
    """Persist inferred taxonomy audit payload as a UTF-8 JSON artifact."""
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def consolidate_knowledge_chunks(path: str, output_path: str | None = None) -> str:
    """Run the full concept consolidation pipeline for one knowledge_chunks JSONL file."""
    concepts = _build_canonical_concepts(path)
    destination = output_path or build_concepts_output_path(path)
    export_concepts(concepts, destination)
    return destination


def build_knowledge_ontology(path: str, output_path: str | None = None) -> str:
    """Build an ontology artifact from consolidated concept knowledge."""
    concepts = _build_canonical_concepts(path)
    taxonomy = infer_taxonomy_links(concepts)
    taxonomy_links = taxonomy["links"] if ONTOLOGY_ENABLE_INFERRED_TAXONOMY else None
    ontology = build_ontology(concepts, taxonomy_links=taxonomy_links)
    destination = output_path or build_ontology_output_path(path)
    export_ontology(ontology, destination)
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description="Consolidate knowledge_chunks JSONL into concept JSON.")
    parser.add_argument("input_path")
    parser.add_argument("--output-path", default=None)
    args = parser.parse_args()
    consolidate_knowledge_chunks(args.input_path, args.output_path)


if __name__ == "__main__":
    main()
