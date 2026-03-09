"""Post-processing consolidation from chunk knowledge into concept knowledge."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from .concept_filter import filter_valid_concepts
from .concept_normalization import normalize_concept_name

CONSOLIDATED_FIELDS: tuple[str, ...] = (
    "definitions",
    "technical_rules",
    "procedures",
    "terminology",
    "examples",
    "relationships",
)

_CHUNK_INDEX_RE = re.compile(r"^chunk_(\d+)_")


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
                target.extend(chunk.get(field_name, []))

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


def consolidate_knowledge_chunks(path: str, output_path: str | None = None) -> str:
    """Run the full concept consolidation pipeline for one knowledge_chunks JSONL file."""
    chunks = load_chunk_knowledge(path)
    normalized_chunks = normalize_concepts(chunks)
    concept_index = build_concept_index(normalized_chunks)
    concepts = merge_concept_knowledge(concept_index, normalized_chunks)
    concepts = filter_valid_concepts(concepts)
    destination = output_path or build_concepts_output_path(path)
    export_concepts(concepts, destination)
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description="Consolidate knowledge_chunks JSONL into concept JSON.")
    parser.add_argument("input_path")
    parser.add_argument("--output-path", default=None)
    args = parser.parse_args()
    consolidate_knowledge_chunks(args.input_path, args.output_path)


if __name__ == "__main__":
    main()
