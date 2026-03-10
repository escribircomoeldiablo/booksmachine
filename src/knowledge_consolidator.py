"""Post-processing consolidation from chunk knowledge into concept knowledge."""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

from .concept_canonicalizer import canonicalize_concepts
from .concept_filter import filter_valid_concepts
from .concept_normalization import normalize_concept_name
from .config import ONTOLOGY_ENABLE_INFERRED_TAXONOMY
from .concept_subconcept_promoter import promote_taxonomy_subconcepts, restore_promoted_subconcepts
from .family_candidate_validator import validate_candidate_families
from .family_discovery import discover_family_candidates
from .domain_families import load_family_catalog
from .family_assigner import assign_families
from .ontology_builder import build_ontology, build_ontology_output_path, export_ontology
from .procedure_frame_builder import build_procedure_frames
from .taxonomy_inference import infer_taxonomy_links

CONSOLIDATED_FIELDS: tuple[str, ...] = (
    "definitions",
    "technical_rules",
    "procedures",
    "terminology",
    "examples",
    "relationships",
)
CONCEPT_EVIDENCE_FIELDS: tuple[str, ...] = (
    "definitions",
    "technical_rules",
    "terminology",
    "examples",
    "relationships",
)
PROCEDURAL_FIELDS: tuple[str, ...] = (
    "procedure_steps",
    "decision_rules",
    "preconditions",
    "exceptions",
    "author_variants",
    "procedure_outputs",
)
PROCEDURE_EVIDENCE_FIELDS: tuple[str, ...] = PROCEDURAL_FIELDS

_CHUNK_INDEX_RE = re.compile(r"^chunk_(\d+)_")
_DEFINITION_HEAD_RE = re.compile(r"^\s*([^:]+):\s+.+$")
_PAREN_SUFFIX_RE = re.compile(r"^\s*([^(]+?)\s*\(.+\)\s*$")
_STRUCTURAL_PARENT_PROJECTION_SPECS: dict[str, dict[str, object]] = {
    "house angularity": {
        "aliases": ("house angularity", "angularity of house", "angularity and favorability of house"),
        "children": ("angular house", "succedent house", "cadent house"),
        "min_children": 3,
    },
    "favorability of house": {
        "aliases": (
            "favorability of house",
            "angularity and favorability of house",
            "fortunate and unfortunate house",
            "fortunate and unfortunate houses",
        ),
        "children": ("benefic houses", "malefic houses"),
        "min_children": 2,
    },
}
_PROCEDURAL_CONCEPT_ALIASES: dict[str, tuple[str, ...]] = {
    "predominator": (
        "predominator",
        "predominator epikratetor",
        "epikratetor",
        "predomination",
        "predominance of light",
        "predomination of the light",
        "predomination of the sect light",
        "sect light",
        "light of the sect",
        "luminar de secta",
        "luz de la secta",
        "luz predominante",
        "criterio de predominancia",
        "criteria for predomination",
    ),
    "predominator epikratetor": (
        "predominator",
        "predominator epikratetor",
        "epikratetor",
        "predomination",
        "predominance of light",
        "predomination of the light",
        "predomination of the sect light",
        "sect light",
        "light of the sect",
        "luminar de secta",
        "luz de la secta",
        "luz predominante",
        "criterio de predominancia",
        "criteria for predomination",
    ),
    "oikodespotes": (
        "oikodespotes",
        "master of the nativity",
        "lord assigned by the predominator",
    ),
}
_PROCEDURAL_FALLBACK_PRIORITIES: dict[str, int] = {
    "predominator": 100,
    "oikodespotes": 80,
    "sect": 40,
    "house system": 10,
}
_STRICT_PROCEDURAL_MATCH_CONCEPTS: set[str] = {
    "oikodespotes",
    "house system",
}


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


def _normalize_surface_key(value: str) -> str:
    normalized = value.lower().replace("-", " ")
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    return " ".join(normalized.split()).strip()


def _normalize_step_text(value: str) -> str:
    text = " ".join(str(value).split()).strip()
    text = re.sub(r"^(?:step|paso)\s*\d+[:.)-]?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^\d+[:.)-]?\s*", "", text)
    return text.strip(" .;:")


def _canonical_author_name(value: str) -> str:
    text = " ".join(str(value).split()).strip()
    if not text:
        return ""
    map_ = {
        "valens": "Valens",
        "porphyry": "Porphyry",
        "paulus": "Paulus",
        "dorotheus": "Dorotheus",
        "ptolemy": "Ptolemy",
        "antiochus": "Antiochus",
    }
    lowered = text.lower()
    return map_.get(lowered, text.title() if lowered == text else text)


def _step_id_from_text(order: int, text: str) -> str:
    surface = re.sub(r"[^a-z0-9]+", "-", _normalize_step_text(text).lower()).strip("-")
    return f"step-{order:03d}-{surface[:48] or 'step'}"


def _new_step(item: dict[str, object], order: int) -> dict[str, object]:
    text = _normalize_step_text(str(item.get("text", "")))
    step_id = str(item.get("id", "")).strip() or _step_id_from_text(order, text)
    return {"id": step_id, "order": order, "text": text}


def _new_rule(item: dict[str, object]) -> dict[str, object]:
    return {
        "condition": " ".join(str(item.get("condition", "")).split()).strip(),
        "outcome": " ".join(str(item.get("outcome", "")).split()).strip(),
        "related_steps": [str(v).strip() for v in item.get("related_steps", []) if isinstance(v, str) and str(v).strip()],
    }


def _new_condition(item: dict[str, object]) -> dict[str, object]:
    return {
        "text": " ".join(str(item.get("text", "")).split()).strip(),
        "scope": " ".join(str(item.get("scope", "")).split()).strip(),
        "related_steps": [str(v).strip() for v in item.get("related_steps", []) if isinstance(v, str) and str(v).strip()],
    }


def _new_variant(item: dict[str, object], *, operation: str = "") -> dict[str, object]:
    return {
        "author": _canonical_author_name(str(item.get("author", ""))),
        "kind": " ".join(str(item.get("kind", "")).split()).strip().lower(),
        "text": " ".join(str(item.get("text", "")).split()).strip(),
        "related_steps": [str(v).strip() for v in item.get("related_steps", []) if isinstance(v, str) and str(v).strip()],
        "operation": operation or "annotate",
    }


def _new_output(item: dict[str, object]) -> dict[str, object]:
    return {"text": " ".join(str(item.get("text", "")).split()).strip()}


def _sentence_case(value: str) -> str:
    text = " ".join(str(value).split()).strip()
    if not text:
        return ""
    return text[0].upper() + text[1:]


def _normalize_condition_text(value: str) -> str:
    text = " ".join(str(value).split()).strip()
    text = re.sub(r"^(?:if|si)\s+", "", text, flags=re.IGNORECASE)
    return text.strip(" .;:")


def _normalize_outcome_text(value: str) -> str:
    return " ".join(str(value).split()).strip().strip(" .;:")


def _derived_step_from_rule(rule: dict[str, object], *, order: int) -> dict[str, object] | None:
    condition = _normalize_condition_text(str(rule.get("condition", "")))
    outcome = _normalize_outcome_text(str(rule.get("outcome", "")))
    if not condition or not outcome:
        return None
    text = _sentence_case(f"if {condition}, then {outcome}")
    return {"id": _step_id_from_text(order, text), "order": order, "text": text}


def _decision_rule_sentence(rule: dict[str, object]) -> str:
    raw_condition = " ".join(str(rule.get("condition", "")).split()).strip()
    condition = _normalize_condition_text(raw_condition)
    outcome = _normalize_outcome_text(str(rule.get("outcome", "")))
    if not condition or not outcome:
        return ""
    if re.match(r"^(?:if|si)\b", raw_condition, re.IGNORECASE):
        return f"{_sentence_case(raw_condition.rstrip(' .;:'))}, then {outcome}."
    return f"If {condition}, then {outcome}."


def _has_explicit_shared_step(payload: dict[str, object], step: dict[str, object]) -> bool:
    step_text = _normalize_step_text(str(step.get("text", ""))).lower()
    return any(_normalize_step_text(str(existing.get("text", ""))).lower() == step_text for existing in payload["shared_procedure"])


def _build_shared_procedure_from_rules(payload: dict[str, object]) -> list[dict[str, object]]:
    if payload["shared_procedure"] or len(payload["decision_rules"]) < 2:
        return list(payload["shared_procedure"])
    if payload["preconditions"] or payload["exceptions"]:
        return []

    authors = {variant["author"] for variant in payload["author_variant_overrides"] if variant.get("author")}
    if len(authors) > 1:
        return []

    derived_steps: list[dict[str, object]] = []
    seen_texts: set[str] = set()
    for order, rule in enumerate(payload["decision_rules"], start=1):
        step = _derived_step_from_rule(rule, order=order)
        if step is None:
            continue
        normalized_text = _normalize_step_text(step["text"]).lower()
        if normalized_text in seen_texts or _has_explicit_shared_step(payload, step):
            continue
        seen_texts.add(normalized_text)
        derived_steps.append(step)

    if len(derived_steps) < 2:
        return []
    return derived_steps


def _empty_procedure_evidence() -> dict[str, list[dict[str, object]]]:
    return {field_name: [] for field_name in PROCEDURE_EVIDENCE_FIELDS}


def _empty_concept_evidence() -> dict[str, list[dict[str, object]]]:
    return {field_name: [] for field_name in CONCEPT_EVIDENCE_FIELDS}


def _append_evidence(bucket: dict[str, list[dict[str, object]]], field_name: str, *, chunk_index: int, value: object) -> None:
    entry = {"chunk_index": chunk_index, "value": value}
    if entry not in bucket[field_name]:
        bucket[field_name].append(entry)


def _normalize_surface(value: str) -> str:
    normalized = value.lower().replace("-", " ")
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    return " ".join(normalized.split()).strip()


def _surface_variants(concept: str) -> set[str]:
    variants = {concept}
    variants.update(_PROCEDURAL_CONCEPT_ALIASES.get(concept, ()))
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


def _chunk_supports_concept_alias(chunk: dict[str, object], concept: str) -> bool:
    aliases = _surface_variants(concept)
    concept_blobs: list[str] = []
    for field_name in ("concepts", "_normalized_concepts", "definitions", "technical_rules", "procedures", "relationships", "terminology"):
        values = chunk.get(field_name, [])
        if isinstance(values, list):
            concept_blobs.extend(str(value) for value in values if isinstance(value, str))
    blob = _normalize_surface(" ".join(concept_blobs))
    if not blob:
        return False
    return any(_contains_exact_term(blob, variant) for variant in aliases)


def _procedural_item_supports_concept(item: dict[str, object], concept: str) -> bool:
    blob = _normalize_surface(json.dumps(item, ensure_ascii=False))
    if not blob:
        return False
    return any(_contains_exact_term(blob, variant) for variant in _surface_variants(concept))


def _preferred_procedural_anchor(chunk: dict[str, object]) -> str | None:
    normalized_concepts = [
        value
        for value in chunk.get("_normalized_concepts", [])
        if isinstance(value, str) and value
    ]
    ranked = [
        concept
        for concept in normalized_concepts
        if concept in _PROCEDURAL_FALLBACK_PRIORITIES and _chunk_supports_concept_alias(chunk, concept)
    ]
    if not ranked:
        return None
    ranked.sort(key=lambda concept: (-_PROCEDURAL_FALLBACK_PRIORITIES.get(concept, 0), concept))
    return ranked[0]


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


def _procedural_items_for_concept(chunk: dict[str, object], concept: str, field_name: str) -> list[dict[str, object]]:
    values = chunk.get(field_name, [])
    if not isinstance(values, list):
        return []
    concept_surface = _normalize_surface(concept)
    matched: list[dict[str, object]] = []
    for item in values:
        if not isinstance(item, dict):
            continue
        blob = json.dumps(item, ensure_ascii=False)
        if _text_supports_concept(blob, concept) or concept_surface in _normalize_surface(blob):
            matched.append(item)
            continue
        related_steps = item.get("related_steps", [])
        if isinstance(related_steps, list) and any(isinstance(step, str) and concept_surface in _normalize_surface(step) for step in related_steps):
            matched.append(item)
    if matched:
        return matched
    normalized_concepts = [
        value
        for value in chunk.get("_normalized_concepts", [])
        if isinstance(value, str) and value
    ]
    if normalized_concepts == [concept]:
        return [item for item in values if isinstance(item, dict)]
    if concept in _STRICT_PROCEDURAL_MATCH_CONCEPTS:
        return []
    preferred_anchor = _preferred_procedural_anchor(chunk)
    if preferred_anchor == concept and _chunk_supports_concept_alias(chunk, concept):
        return [item for item in values if isinstance(item, dict)]
    return matched


def _structural_parent_spec(concept: str) -> dict[str, object] | None:
    for spec in _STRUCTURAL_PARENT_PROJECTION_SPECS.values():
        aliases = {normalize_concept_name(alias) for alias in spec["aliases"]}
        if concept in aliases:
            return spec
    return None


def _chunk_structural_children(
    chunk: dict[str, object],
    *,
    child_names: tuple[str, ...],
) -> list[str]:
    chunk_concepts = {
        normalize_concept_name(value)
        for value in chunk.get("concepts", [])
        if isinstance(value, str)
    }
    chunk_concepts.update(
        value
        for value in chunk.get("_normalized_concepts", [])
        if isinstance(value, str)
    )
    chunk_concepts.update(
        _definition_head(value)
        for value in chunk.get("definitions", [])
        if isinstance(value, str) and _definition_head(value)
    )
    chunk_concepts.update(
        _terminology_head(value)
        for value in chunk.get("terminology", [])
        if isinstance(value, str)
    )

    observed: list[str] = []
    for child_name in child_names:
        if child_name in chunk_concepts:
            observed.append(child_name)
    return _dedupe_preserve_order(observed)


def _project_structural_parent_minimum(
    payload: dict[str, object],
    *,
    concept: str,
    source_chunks: list[int],
    chunk_lookup: dict[int, dict[str, object]],
) -> None:
    spec = _structural_parent_spec(concept)
    if spec is None:
        return
    if any(payload.get(field_name) for field_name in ("definitions", "technical_rules", "procedures", "relationships")):
        return

    child_names = tuple(str(child) for child in spec["children"])
    min_children = int(spec["min_children"])
    preserved_terms: list[str] = []
    supporting_chunks: list[int] = []

    for chunk_index in source_chunks:
        chunk = chunk_lookup.get(chunk_index)
        if not chunk:
            continue
        observed_children = _chunk_structural_children(chunk, child_names=child_names)
        if len(observed_children) < min_children:
            continue
        supporting_chunks.append(chunk_index)
        for child_name in observed_children:
            preserved_terms.append(child_name.replace(" house", " houses").title().replace(" Houses", " houses"))

    if not supporting_chunks or not preserved_terms:
        return

    payload["terminology"] = _dedupe_preserve_order(list(payload["terminology"]) + preserved_terms)
    payload["source_chunks"] = _dedupe_preserve_order(list(payload["source_chunks"]) + supporting_chunks)


def merge_concept_fields(payload: dict[str, object], *, concept: str, chunk: dict[str, object], chunk_index: int) -> None:
    concept_evidence = payload["concept_evidence"]
    for field_name in CONSOLIDATED_FIELDS:
        values = _field_values_for_concept(chunk, concept, field_name)
        payload[field_name] = _dedupe_preserve_order(list(payload[field_name]) + values)
        for value in values:
            if field_name in concept_evidence:
                _append_evidence(concept_evidence, field_name, chunk_index=chunk_index, value=value)


def merge_procedural_fields(payload: dict[str, object], *, concept: str, chunk: dict[str, object], chunk_index: int) -> None:
    procedure_evidence = payload["procedure_evidence"]

    step_candidates = []
    for idx, item in enumerate(_procedural_items_for_concept(chunk, concept, "procedure_steps"), start=1):
        order = item.get("order") if isinstance(item.get("order"), int) else idx
        step_candidates.append(_new_step(item, order))
    for step in step_candidates:
        if step["text"] and not any(
            existing["order"] == step["order"] and _normalize_step_text(str(existing["text"])) == _normalize_step_text(str(step["text"]))
            for existing in payload["shared_procedure"]
        ):
            payload["shared_procedure"].append(step)
            _append_evidence(procedure_evidence, "procedure_steps", chunk_index=chunk_index, value=step)

    for field_name, factory in (
        ("decision_rules", _new_rule),
        ("preconditions", _new_condition),
        ("exceptions", _new_condition),
        ("procedure_outputs", _new_output),
    ):
        for item in _procedural_items_for_concept(chunk, concept, field_name):
            normalized = factory(item)
            if not any(existing == normalized for existing in payload[field_name]):
                payload[field_name].append(normalized)
                _append_evidence(procedure_evidence, field_name, chunk_index=chunk_index, value=normalized)

    variants = []
    for item in _procedural_items_for_concept(chunk, concept, "author_variants"):
        variants.append(_new_variant(item))
    for variant in variants:
        if not variant["author"] or not variant["kind"] or not variant["text"]:
            continue
        if not any(existing == variant for existing in payload["author_variant_overrides"]):
            payload["author_variant_overrides"].append(variant)
            _append_evidence(procedure_evidence, "author_variants", chunk_index=chunk_index, value=variant)


def _finalize_procedural_payload(payload: dict[str, object]) -> None:
    if not payload["shared_procedure"]:
        payload["shared_procedure"] = _build_shared_procedure_from_rules(payload)

    steps = sorted(payload["shared_procedure"], key=lambda item: (int(item["order"]), str(item["id"])))
    normalized_steps: list[dict[str, object]] = []
    seen_steps: set[tuple[int, str]] = set()
    for index, item in enumerate(steps, start=1):
        text = _normalize_step_text(str(item.get("text", "")))
        if not text:
            continue
        order = int(item.get("order", index))
        key = (order, text.lower())
        if key in seen_steps:
            continue
        seen_steps.add(key)
        normalized_steps.append({"id": str(item.get("id") or _step_id_from_text(order, text)), "order": order, "text": text})
    payload["shared_procedure"] = normalized_steps

    authors = {variant["author"] for variant in payload["author_variant_overrides"] if variant.get("author")}
    if len(authors) > 1 and len(payload["shared_procedure"]) < 2:
        payload["shared_procedure"] = []

    preconditions = []
    for item in payload["preconditions"]:
        scope = f" ({item['scope']})" if item.get("scope") else ""
        preconditions.append(f"Precondition{scope}: {item['text']}")
    exceptions = []
    for item in payload["exceptions"]:
        scope = f" ({item['scope']})" if item.get("scope") else ""
        exceptions.append(f"Exception{scope}: {item['text']}")
    payload["procedures"] = _dedupe_preserve_order(
        [f"{step['order']}. {step['text']}" for step in payload["shared_procedure"]]
        + [sentence for sentence in (_decision_rule_sentence(item) for item in payload["decision_rules"]) if sentence]
        + preconditions
        + exceptions
        + [f"{item['author']} [{item['kind']}]: {item['text']}" for item in payload["author_variant_overrides"]]
        + [f"Output: {item['text']}" for item in payload["procedure_outputs"]]
    )


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
            "shared_procedure": [],
            "decision_rules": [],
            "preconditions": [],
            "exceptions": [],
            "author_variant_overrides": [],
            "procedure_outputs": [],
            "concept_evidence": _empty_concept_evidence(),
            "procedure_evidence": _empty_procedure_evidence(),
            "source_chunks": list(source_chunks),
        }
        for chunk_index in source_chunks:
            chunk = chunk_lookup.get(chunk_index)
            if not chunk:
                continue
            merge_concept_fields(payload, concept=concept, chunk=chunk, chunk_index=chunk_index)
            merge_procedural_fields(payload, concept=concept, chunk=chunk, chunk_index=chunk_index)

        for field_name in ("definitions", "technical_rules", "terminology", "examples", "relationships"):
            payload[field_name] = _dedupe_preserve_order(payload[field_name])

        _finalize_procedural_payload(payload)

        _project_structural_parent_minimum(
            payload,
            concept=concept,
            source_chunks=list(source_chunks),
            chunk_lookup=chunk_lookup,
        )

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


def build_families_output_path(input_path: str, output_folder: str | None = None) -> str:
    """Build the family-level output path for a chunk JSONL input."""
    source_path = Path(input_path)
    folder = Path(output_folder) if output_folder else source_path.parent
    if source_path.name.endswith("_knowledge_chunks.jsonl"):
        filename = source_path.name.replace("_knowledge_chunks.jsonl", "_knowledge_families.json")
    else:
        filename = f"{source_path.stem}_knowledge_families.json"
    return str(folder / filename)


def build_family_candidates_output_path(input_path: str, output_folder: str | None = None) -> str:
    """Build the family-candidate output path for a chunk JSONL input."""
    source_path = Path(input_path)
    folder = Path(output_folder) if output_folder else source_path.parent
    if source_path.name.endswith("_knowledge_chunks.jsonl"):
        filename = source_path.name.replace("_knowledge_chunks.jsonl", "_knowledge_family_candidates.json")
    else:
        filename = f"{source_path.stem}_knowledge_family_candidates.json"
    return str(folder / filename)


def build_procedural_audit_output_path(input_path: str, output_folder: str | None = None) -> str:
    """Build the procedural-audit output path for a chunk JSONL input."""
    source_path = Path(input_path)
    folder = Path(output_folder) if output_folder else source_path.parent
    if source_path.name.endswith("_knowledge_chunks.jsonl"):
        filename = source_path.name.replace("_knowledge_chunks.jsonl", "_procedural_audit.json")
    else:
        filename = f"{source_path.stem}_procedural_audit.json"
    return str(folder / filename)


def build_procedure_frames_output_path(input_path: str, output_folder: str | None = None) -> str:
    """Build the procedure-frame output path for a chunk JSONL input."""
    source_path = Path(input_path)
    folder = Path(output_folder) if output_folder else source_path.parent
    if source_path.name.endswith("_knowledge_chunks.jsonl"):
        filename = source_path.name.replace("_knowledge_chunks.jsonl", "_procedure_frames.json")
    else:
        filename = f"{source_path.stem}_procedure_frames.json"
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


def _build_family_payload(path: str) -> dict[str, object]:
    """Build family assignment payload from canonical concepts."""
    concepts = _build_canonical_concepts(path)
    return assign_families(concepts, load_family_catalog())


def _build_family_candidates_payload(path: str, *, llm_callable=None) -> dict[str, object]:
    """Build validated book-specific family candidates from unassigned concepts."""
    concepts = _build_canonical_concepts(path)
    catalog = load_family_catalog()
    family_payload = assign_families(concepts, catalog)
    raw_candidates = discover_family_candidates(
        concepts=concepts,
        family_payload=family_payload,
        llm_callable=llm_callable,
    )
    return validate_candidate_families(
        raw_candidates,
        unassigned_concepts=[
            concept_name
            for concept_name in family_payload.get("unassigned_concepts", [])
            if isinstance(concept_name, str)
        ],
        existing_catalog=catalog,
        existing_families=family_payload,
    )


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


def export_families(payload: dict[str, object], output_path: str) -> None:
    """Persist concept family assignments as a UTF-8 JSON artifact."""
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def export_family_candidates(payload: dict[str, object], output_path: str) -> None:
    """Persist family candidate discovery artifact as a UTF-8 JSON artifact."""
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def export_procedural_audit(payload: dict[str, object], output_path: str) -> None:
    """Persist procedural audit artifact as UTF-8 JSON."""
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def export_procedure_frames(payload: dict[str, object], output_path: str) -> None:
    """Persist procedure-frame artifact as UTF-8 JSON."""
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


def build_procedural_audit(path: str, output_path: str | None = None) -> str:
    """Build a procedural audit artifact from consolidated concept knowledge."""
    concepts = _build_canonical_concepts(path)
    payload = {
        concept_name: {
            "shared_procedure": concept_payload.get("shared_procedure", []),
            "decision_rules": concept_payload.get("decision_rules", []),
            "preconditions": concept_payload.get("preconditions", []),
            "exceptions": concept_payload.get("exceptions", []),
            "author_variant_overrides": concept_payload.get("author_variant_overrides", []),
            "procedure_outputs": concept_payload.get("procedure_outputs", []),
            "procedure_evidence": concept_payload.get("procedure_evidence", _empty_procedure_evidence()),
        }
        for concept_name, concept_payload in concepts.items()
        if any(
            concept_payload.get(field_name)
            for field_name in (
                "shared_procedure",
                "decision_rules",
                "preconditions",
                "exceptions",
                "author_variant_overrides",
                "procedure_outputs",
            )
        )
    }
    destination = output_path or build_procedural_audit_output_path(path)
    export_procedural_audit(payload, destination)
    return destination


def build_procedure_frames_artifact(path: str, output_path: str | None = None) -> str:
    """Build a procedure-frame artifact from consolidated concept knowledge."""
    concepts = _build_canonical_concepts(path)
    payload = build_procedure_frames(concepts)
    destination = output_path or build_procedure_frames_output_path(path)
    export_procedure_frames(payload, destination)
    return destination


def build_knowledge_families(path: str, output_path: str | None = None) -> str:
    """Build a family assignment artifact from consolidated concept knowledge."""
    payload = _build_family_payload(path)
    destination = output_path or build_families_output_path(path)
    export_families(payload, destination)
    return destination


def build_knowledge_family_candidates(
    path: str,
    output_path: str | None = None,
    *,
    llm_callable=None,
) -> str:
    """Build a validated family-candidate artifact from unassigned concepts."""
    payload = _build_family_candidates_payload(path, llm_callable=llm_callable)
    destination = output_path or build_family_candidates_output_path(path)
    export_family_candidates(payload, destination)
    return destination


def build_knowledge_ontology(path: str, output_path: str | None = None) -> str:
    """Build an ontology artifact from consolidated concept knowledge."""
    concepts = _build_canonical_concepts(path)
    family_payload = assign_families(concepts, load_family_catalog())
    export_families(family_payload, build_families_output_path(path))
    export_family_candidates(
        _build_family_candidates_payload(path),
        build_family_candidates_output_path(path),
    )
    taxonomy = infer_taxonomy_links(concepts)
    taxonomy_links = taxonomy["links"] if ONTOLOGY_ENABLE_INFERRED_TAXONOMY else None
    ontology = build_ontology(concepts, taxonomy_links=taxonomy_links, family_memberships=family_payload)
    destination = output_path or build_ontology_output_path(path)
    export_ontology(ontology, destination)
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build derived knowledge artifacts from a *_knowledge_chunks.jsonl file."
    )
    parser.add_argument("input_path")
    parser.add_argument(
        "--artifact",
        choices=["concepts", "families", "family-candidates", "ontology", "procedural-audit", "procedure-frames", "all"],
        default="concepts",
        help="Artifact to generate from the knowledge chunks input.",
    )
    parser.add_argument("--output-path", default=None)
    args = parser.parse_args()
    if args.artifact == "all":
        if args.output_path is not None:
            parser.error("--output-path can only be used when --artifact targets a single file.")
        destinations = [
            consolidate_knowledge_chunks(args.input_path),
            build_knowledge_families(args.input_path),
            build_knowledge_family_candidates(args.input_path),
            build_knowledge_ontology(args.input_path),
            build_procedural_audit(args.input_path),
            build_procedure_frames_artifact(args.input_path),
        ]
        for destination in destinations:
            print(destination)
        return

    builders = {
        "concepts": consolidate_knowledge_chunks,
        "families": build_knowledge_families,
        "family-candidates": build_knowledge_family_candidates,
        "ontology": build_knowledge_ontology,
        "procedural-audit": build_procedural_audit,
        "procedure-frames": build_procedure_frames_artifact,
    }
    destination = builders[args.artifact](args.input_path, args.output_path)
    print(destination)


if __name__ == "__main__":
    main()
