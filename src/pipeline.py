"""End-to-end book processing pipeline."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Callable

from .chunker import split_into_chunks
from .chunker_structural import build_structural_chunks
from .compiler import (
    build_block_output_path,
    build_chunk_output_path,
    build_knowledge_audit_output_path,
    build_knowledge_chunks_output_path,
    build_output_path,
    compile_block_summaries,
    compile_chunk_summaries,
    compile_compendium,
)
from .config import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    KNOWLEDGE_DECISION_POLICY_ENABLE,
    KNOWLEDGE_DEGRADED_WEAK_SUPPORT_CONCEPTS_MAX,
    KNOWLEDGE_DEGRADED_WEAK_SUPPORT_TERMINOLOGY_MAX,
    KNOWLEDGE_FILTER_EDITORIAL_ENABLE,
    KNOWLEDGE_FILTER_GENERIC_DEFINITIONS_ENABLE,
    KNOWLEDGE_FILTER_MODERN_ENABLE,
    KNOWLEDGE_EXTRACTION_ENABLED,
    KNOWLEDGE_CLAMP_ENABLE,
    KNOWLEDGE_MIN_NON_GLOSSARIAL_DEFINITIONS_FOR_EXTRACT,
    KNOWLEDGE_NEAR_EMPTY_MAX_SEMANTIC_ITEMS,
    KNOWLEDGE_PRECHECK_ENABLED,
    KNOWLEDGE_PRECHECK_REVIEW_DEFAULT,
    KNOWLEDGE_TERMINOLOGY_DOMINANT_MIN_TERMS,
    KNOWLEDGE_TERMINOLOGY_DOMINANT_RATIO_THRESHOLD,
    OUTPUT_FOLDER,
    PIPELINE_VERSION,
    STRUCTURE_MAX_HEADINGS_FOR_LLM,
    STRUCTURE_MAX_SECTION_SIZE_CHARS,
    STRUCTURE_MIN_HEADING_SCORE,
    STRUCTURE_PASS_ENABLED,
    STRUCTURE_PASS_USE_LLM,
    STRUCTURAL_CHUNKER_ENABLED,
    STRUCTURAL_CHUNKER_EXCLUDED_TYPES,
    STRUCTURAL_CHUNKER_MIN_SIZE,
    STRUCTURAL_CHUNKER_SPLIT_WINDOW,
    STRUCTURAL_CHUNKER_TARGET_SIZE,
)
from .document_map_cleaner import clean_document_map
from .knowledge_extractor import chunk_knowledge_to_summary_text, extract_chunk_knowledge
from .knowledge_normalize import (
    CORE_FIELDS,
    SEMANTIC_FIELDS,
    apply_post_extraction_clamp,
    apply_semantic_local_filter,
)
from .knowledge_precheck import (
    DECISION_EXTRACT,
    DECISION_EXTRACT_DEGRADED,
    DECISION_SKIP,
    precheck_chunk_extractability,
)
from .knowledge_schema import ChunkKnowledgeV1, SectionRef, make_empty_chunk_knowledge
from .loader import load_book, load_book_with_structure
from .structure_pass import (
    build_document_map,
    build_document_map_output_path,
    build_document_map_sidecar_payload,
    serialize_document_map_sidecar,
)
from .summarizer import summarize_chunk
from .synthesizer import (
    expected_synthesis_calls,
    make_chunk_summary_records,
    synthesize_blocks,
    synthesize_compendium,
)
from .utils import ensure_dir, save_text

CHECKPOINT_DIR_NAME = ".checkpoints"
CHECKPOINT_NAMESPACE_SUMMARY = "summary"
CHECKPOINT_NAMESPACE_KNOWLEDGE = "knowledge"
DEFAULT_SMOKE_MAX_CHUNKS = 3
ProgressCallback = Callable[[str, str, dict[str, object]], None]
FALLBACK_REASON_SEMANTIC_UNKNOWN_RATIO = "semantic_gate_unknown_ratio"
FALLBACK_REASON_SEMANTIC_INDEX_LIKE_RATIO = "semantic_gate_index_like_ratio"
FALLBACK_REASON_SEMANTIC_SECONDARY = "semantic_gate_secondary_metrics"
FALLBACK_REASON_POSTCHECK_CHUNK_COUNT = "postcheck_chunk_count"
FALLBACK_REASON_POSTCHECK_SMALL_CHUNK_RATIO = "postcheck_small_chunk_ratio"
FALLBACK_REASON_STRUCTURAL_MAP_INVALID = "structural_map_invalid"
FALLBACK_REASON_STRUCTURAL_MAP_INSUFFICIENT_SECTIONS = "structural_map_insufficient_sections"
RECOGNIZED_TYPES = {"chapter", "section", "appendix", "front_matter", "bibliography", "index"}
CHUNK_USEFUL_TYPES = {"chapter", "section", "appendix", "front_matter"}
TRIVIAL_UNKNOWN_LABELS = {"unknown", "section"}
STRUCTURE_QUALITY_THRESHOLDS = {
    "unknown_ratio_max": 0.85,
    "section_density_per_10k_chars_max": 12.0,
    "chunk_useful_type_ratio_min": 0.20,
    "index_like_ratio_max": 0.20,
    "classified_heading_ratio_min": 0.10,
}


def _relative_cost_scale(expected_calls: int) -> str:
    if expected_calls <= 3:
        return "low"
    if expected_calls <= 12:
        return "medium"
    return "high"


def _log(verbose: bool, message: str) -> None:
    if verbose:
        print(message)


def _emit_progress(
    progress_callback: ProgressCallback | None,
    stage: str,
    message: str,
    **details: object,
) -> None:
    if progress_callback is None:
        return
    progress_callback(stage, message, details)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _checkpoint_root(
    output_folder: str,
    book_hash: str,
    mode_namespace: str,
    chunking_hash: str,
) -> Path:
    return Path(output_folder) / CHECKPOINT_DIR_NAME / book_hash / mode_namespace / chunking_hash


def _chunk_checkpoint_path(root: Path, chunk_index: int) -> Path:
    return root / f"chunk_{chunk_index}.txt"


def _knowledge_checkpoint_path(root: Path, chunk_index: int) -> Path:
    return root / f"chunk_{chunk_index}.json"


def _load_checkpointed_summaries(
    checkpoint_root: Path,
    total_chunks: int,
) -> dict[int, str]:
    cached: dict[int, str] = {}
    for chunk_index in range(1, total_chunks + 1):
        chunk_path = _chunk_checkpoint_path(checkpoint_root, chunk_index)
        if chunk_path.exists():
            cached[chunk_index] = chunk_path.read_text(encoding="utf-8")
    return cached


def _load_checkpointed_knowledge(
    checkpoint_root: Path,
    total_chunks: int,
) -> dict[int, ChunkKnowledgeV1]:
    cached: dict[int, ChunkKnowledgeV1] = {}
    for chunk_index in range(1, total_chunks + 1):
        chunk_path = _knowledge_checkpoint_path(checkpoint_root, chunk_index)
        if not chunk_path.exists():
            continue
        try:
            payload = json.loads(chunk_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                continue
            section_refs = payload.get("section_refs", [])
            refs: list[SectionRef] = []
            if isinstance(section_refs, list):
                for item in section_refs:
                    if not isinstance(item, dict):
                        continue
                    label = item.get("label")
                    section_type = item.get("type")
                    start_char = item.get("start_char")
                    end_char = item.get("end_char")
                    if (
                        isinstance(label, str)
                        and isinstance(section_type, str)
                        and isinstance(start_char, int)
                        and isinstance(end_char, int)
                    ):
                        refs.append(
                            SectionRef(
                                label=label,
                                type=section_type,
                                start_char=start_char,
                                end_char=end_char,
                            )
                        )
            def _list(key: str) -> list[str]:
                value = payload.get(key, [])
                if isinstance(value, list):
                    return [item.strip() for item in value if isinstance(item, str) and item.strip()]
                return []

            schema_version = payload.get("schema_version")
            chunk_id = payload.get("chunk_id")
            source_fingerprint = payload.get("source_fingerprint")
            if not (
                isinstance(schema_version, str)
                and isinstance(chunk_id, str)
                and isinstance(source_fingerprint, str)
            ):
                continue
            cached[chunk_index] = ChunkKnowledgeV1(
                schema_version=schema_version,
                chunk_id=chunk_id,
                source_fingerprint=source_fingerprint,
                section_refs=refs,
                concepts=_list("concepts"),
                definitions=_list("definitions"),
                technical_rules=_list("technical_rules"),
                procedures=_list("procedures"),
                terminology=_list("terminology"),
                relationships=_list("relationships"),
                examples=_list("examples"),
                ambiguities=_list("ambiguities"),
            )
        except (json.JSONDecodeError, OSError):
            continue
    return cached


def _save_manifest(checkpoint_root: Path, payload: dict[str, object]) -> None:
    save_text(
        str(checkpoint_root / "manifest.json"),
        json.dumps(payload, indent=2, sort_keys=True),
    )


def _chunking_fingerprint(
    *,
    mode: str,
    chunk_size: int,
    overlap: int,
    target_size: int,
    min_size: int,
    split_window: int,
) -> str:
    if mode == "structural":
        token = f"structural:{target_size}:{min_size}:{split_window}"
    else:
        token = f"legacy:{chunk_size}:{overlap}"
    return _sha256_text(token)


def _is_index_like_label(label: str) -> bool:
    stripped = label.strip()
    if not stripped:
        return False
    if re.fullmatch(r"[A-Z]", stripped):
        return True
    if re.search(r"\.{3,}\s*\d+\s*$", stripped):
        return True
    if re.search(r"(?:\s|,)\d+(?:[-–]\d+)?(?:\s*,\s*\d+(?:[-–]\d+)?)*\.?$", stripped):
        if "," in stripped:
            return True
        if len(stripped.split()) <= 6:
            return True
    lowered = stripped.lower()
    if any(keyword in lowered for keyword in ("contents", "table of contents")):
        return True
    return False


def _is_unknown_heading_label(label: object) -> bool:
    if not isinstance(label, str):
        return False
    stripped = label.strip()
    lowered = stripped.lower()
    if not stripped:
        return False
    if lowered in TRIVIAL_UNKNOWN_LABELS:
        return False
    if re.fullmatch(r"[A-Z]", stripped):
        return False
    return True


def _float_ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return float(numerator) / float(denominator)


def _evaluate_structure_quality(
    structure_map: dict[str, object],
    *,
    normalized_text: str,
) -> tuple[dict[str, object], bool, str | None]:
    sections_obj = structure_map.get("sections")
    stats_obj = structure_map.get("stats")
    sections = sections_obj if isinstance(sections_obj, list) else []
    stats = stats_obj if isinstance(stats_obj, dict) else {}
    sections_generated = len(sections)
    text_len = len(normalized_text)
    heading_candidates = int(stats.get("heading_candidates", 0))
    classified_headings = int(stats.get("classified_headings", 0))

    unknown_sections = 0
    recognized_sections = 0
    chunk_useful_sections = 0
    index_like_sections = 0
    unknown_heading = 0
    for item in sections:
        if not isinstance(item, dict):
            continue
        section_type = item.get("type")
        if section_type == "unknown":
            unknown_sections += 1
            if _is_unknown_heading_label(item.get("label")):
                unknown_heading += 1
        elif isinstance(section_type, str) and section_type in RECOGNIZED_TYPES:
            recognized_sections += 1
        if isinstance(section_type, str) and section_type in CHUNK_USEFUL_TYPES:
            chunk_useful_sections += 1
        label = item.get("label")
        if isinstance(label, str) and _is_index_like_label(label):
            index_like_sections += 1

    unknown_ratio = _float_ratio(unknown_sections, sections_generated)
    section_density_base = max(1.0, float(text_len) / 10000.0)
    section_density = float(sections_generated) / section_density_base
    recognized_ratio = _float_ratio(recognized_sections, sections_generated)
    chunk_useful_ratio = _float_ratio(chunk_useful_sections, sections_generated)
    index_like_ratio = _float_ratio(index_like_sections, sections_generated)
    classified_ratio = _float_ratio(classified_headings, max(1, heading_candidates))
    unknown_gap = max(0, unknown_sections - unknown_heading)

    metrics: dict[str, object] = {
        "sections_generated": sections_generated,
        "normalized_text_length": text_len,
        "unknown_sections": unknown_sections,
        "unknown_heading": unknown_heading,
        "unknown_gap": unknown_gap,
        "unknown_ratio": unknown_ratio,
        "section_density_per_10k_chars": section_density,
        "recognized_type_ratio": recognized_ratio,
        "chunk_useful_type_ratio": chunk_useful_ratio,
        "index_like_ratio": index_like_ratio,
        "classified_heading_ratio": classified_ratio,
        "thresholds": dict(STRUCTURE_QUALITY_THRESHOLDS),
    }

    unknown_fail = unknown_ratio > STRUCTURE_QUALITY_THRESHOLDS["unknown_ratio_max"]
    index_like_fail = index_like_ratio > STRUCTURE_QUALITY_THRESHOLDS["index_like_ratio_max"]
    secondary_failures = 0
    if section_density > STRUCTURE_QUALITY_THRESHOLDS["section_density_per_10k_chars_max"]:
        secondary_failures += 1
    if chunk_useful_ratio < STRUCTURE_QUALITY_THRESHOLDS["chunk_useful_type_ratio_min"]:
        secondary_failures += 1
    if classified_ratio < STRUCTURE_QUALITY_THRESHOLDS["classified_heading_ratio_min"]:
        secondary_failures += 1

    if unknown_fail:
        return metrics, False, FALLBACK_REASON_SEMANTIC_UNKNOWN_RATIO
    if index_like_fail:
        return metrics, False, FALLBACK_REASON_SEMANTIC_INDEX_LIKE_RATIO
    if secondary_failures >= 2:
        return metrics, False, FALLBACK_REASON_SEMANTIC_SECONDARY
    return metrics, True, None


def _build_section_refs_for_chunk(
    *,
    chunk_index: int,
    chunking_mode: str,
    structural_chunk_records: list[dict[str, object]] | None,
    structure_map: dict[str, object] | None,
) -> list[SectionRef]:
    if chunking_mode != "structural" or not structural_chunk_records or structure_map is None:
        return []
    if chunk_index <= 0 or chunk_index > len(structural_chunk_records):
        return []
    chunk_record = structural_chunk_records[chunk_index - 1]
    sections_obj = structure_map.get("sections")
    if not isinstance(sections_obj, list):
        return []
    chunk_start = chunk_record.get("start_char")
    chunk_end = chunk_record.get("end_char")
    if not isinstance(chunk_start, int) or not isinstance(chunk_end, int) or chunk_end <= chunk_start:
        return []
    refs: list[SectionRef] = []

    def _is_noisy_ref(label: str, section_type: str) -> bool:
        normalized = " ".join(label.split()).strip()
        lowered = normalized.lower()
        if not normalized:
            return True
        if section_type in {"index"}:
            return True
        if re.fullmatch(r"[\W_]{1,8}", normalized):
            return True
        if _is_garbage_label(normalized):
            return True
        if len(normalized.split()) <= 2 and section_type in {"unknown", "section"} and len(normalized) <= 8:
            return True
        if any(token in lowered for token in ("bibliography", "references", "sources")) and section_type == "unknown":
            return True
        return False

    for section in sections_obj:
        if not isinstance(section, dict):
            continue
        label = section.get("label")
        section_type = section.get("type")
        start_char = section.get("start_char")
        end_char = section.get("end_char")
        if (
            not isinstance(label, str)
            or not isinstance(section_type, str)
            or not isinstance(start_char, int)
            or not isinstance(end_char, int)
            or end_char <= start_char
        ):
            continue
        overlaps = max(start_char, chunk_start) < min(end_char, chunk_end)
        if not overlaps:
            continue
        if _is_noisy_ref(label, section_type):
            continue
        refs.append(
            SectionRef(
                label=label,
                type=section_type,
                start_char=start_char,
                end_char=end_char,
            )
        )
    if refs:
        return refs
    section_index = chunk_record.get("section_index")
    if not isinstance(section_index, int) or section_index < 0 or section_index >= len(sections_obj):
        return []
    section = sections_obj[section_index]
    if not isinstance(section, dict):
        return []
    label = section.get("label")
    section_type = section.get("type")
    start_char = section.get("start_char")
    end_char = section.get("end_char")
    if not isinstance(label, str) or not isinstance(section_type, str):
        return []
    if not isinstance(start_char, int) or not isinstance(end_char, int):
        return []
    if _is_noisy_ref(label, section_type):
        return []
    return [SectionRef(label=label, type=section_type, start_char=start_char, end_char=end_char)]


def _all_fields_empty(record: ChunkKnowledgeV1) -> bool:
    return all(len(getattr(record, field_name)) == 0 for field_name in SEMANTIC_FIELDS)


def _has_core_doctrinal_content(record: ChunkKnowledgeV1) -> bool:
    return bool(record.definitions or record.technical_rules or record.procedures)


def _is_concept_heavy_doctrine_light(record: ChunkKnowledgeV1) -> bool:
    return bool(record.concepts) and not _has_core_doctrinal_content(record)


_RE_DEFINITION_OPERATIONAL_SIGNAL = re.compile(
    r"\b(if|when|si|cuando|then|indicates|indica|applies|aplica|depends|depende|"
    r"strength|fuerza|weak|debil|manifest|manifiesta|effect|efecto)\b",
    re.IGNORECASE,
)
_RE_GLOSSARIAL_EQUIVALENCE = re.compile(
    r"\b(is|means|refers to|es|significa|equivale)\b",
    re.IGNORECASE,
)


def _is_non_glossarial_definition(value: str) -> bool:
    text = " ".join(value.strip().split())
    if not text:
        return False
    if _RE_DEFINITION_OPERATIONAL_SIGNAL.search(text):
        return True
    if ":" in text:
        _, rhs = text.split(":", 1)
        rhs_text = rhs.strip()
        if _RE_DEFINITION_OPERATIONAL_SIGNAL.search(rhs_text):
            return True
        if len(rhs_text.split()) <= 6:
            return False
    if _RE_GLOSSARIAL_EQUIVALENCE.search(text):
        return False
    return False


def _count_non_glossarial_definitions(definitions: list[str]) -> int:
    return sum(1 for item in definitions if _is_non_glossarial_definition(item))


def _semantic_items_count(record: ChunkKnowledgeV1) -> int:
    return sum(len(getattr(record, field_name)) for field_name in SEMANTIC_FIELDS)


def _is_terminology_dominant(record: ChunkKnowledgeV1) -> bool:
    terminology_count = len(record.terminology)
    if terminology_count < max(0, KNOWLEDGE_TERMINOLOGY_DOMINANT_MIN_TERMS):
        return False
    if record.technical_rules or record.procedures:
        return False
    non_glossarial = _count_non_glossarial_definitions(record.definitions)
    if non_glossarial > 0:
        return False
    concepts_and_definitions = len(record.concepts) + len(record.definitions)
    baseline = max(1.0, float(concepts_and_definitions))
    ratio = float(terminology_count) / baseline
    return ratio >= max(0.0, KNOWLEDGE_TERMINOLOGY_DOMINANT_RATIO_THRESHOLD)


def _doctrinal_support_level(record: ChunkKnowledgeV1) -> str:
    if record.technical_rules or record.procedures:
        return "strong"
    non_glossarial = _count_non_glossarial_definitions(record.definitions)
    if non_glossarial >= max(1, KNOWLEDGE_MIN_NON_GLOSSARIAL_DEFINITIONS_FOR_EXTRACT) and record.concepts:
        return "minimal"
    return "none"


def _semantic_payload_near_empty(record: ChunkKnowledgeV1) -> bool:
    semantic_items = _semantic_items_count(record)
    if semantic_items == 0:
        return True
    if semantic_items > max(0, KNOWLEDGE_NEAR_EMPTY_MAX_SEMANTIC_ITEMS):
        return False
    if record.technical_rules or record.procedures:
        return False
    if _count_non_glossarial_definitions(record.definitions) > 0:
        return False
    if len(record.concepts) > 1:
        return False
    if len(record.terminology) > 1:
        return False
    return True


def _decision_from_filtered_payload(
    *,
    precheck_decision: str,
    record: ChunkKnowledgeV1,
    chunk_type: str,
) -> tuple[str, str, list[str]]:
    reasons: list[str] = []
    support_level = _doctrinal_support_level(record)
    if support_level == "strong":
        reasons.append("strong_doctrinal_support")
    elif support_level == "minimal":
        reasons.append("minimal_doctrinal_support")

    if precheck_decision == DECISION_SKIP:
        reasons.append("semantic_payload_empty_or_near_empty")
        return DECISION_SKIP, "none", reasons

    if _semantic_payload_near_empty(record):
        reasons.append("semantic_payload_empty_or_near_empty")
        if chunk_type == "doctrinal_text":
            if "insufficient_operational_support" not in reasons:
                reasons.append("insufficient_operational_support")
            return DECISION_EXTRACT_DEGRADED, "none", reasons
        return DECISION_SKIP, "none", reasons

    rules_count = len(record.technical_rules)
    procedures_count = len(record.procedures)
    concepts_count = len(record.concepts)
    definitions_count = len(record.definitions)
    non_glossarial_definitions = _count_non_glossarial_definitions(record.definitions)

    concept_heavy_no_operations = (
        concepts_count > 0 and rules_count == 0 and procedures_count == 0 and non_glossarial_definitions == 0
    )
    glossary_like_semantics = (
        definitions_count > 0 and non_glossarial_definitions == 0 and rules_count == 0 and procedures_count == 0
    )
    terminology_dominant = _is_terminology_dominant(record)
    definitions_minimal_no_operations = (
        non_glossarial_definitions > 0
        and non_glossarial_definitions < max(1, KNOWLEDGE_MIN_NON_GLOSSARIAL_DEFINITIONS_FOR_EXTRACT)
        and rules_count == 0
        and procedures_count == 0
    )

    if concept_heavy_no_operations:
        reasons.append("concept_heavy_no_operations")
    if glossary_like_semantics:
        reasons.append("glossary_like_semantics")
    if terminology_dominant:
        reasons.append("terminology_dominant_no_operations")
    if definitions_minimal_no_operations:
        reasons.append("insufficient_operational_support")

    has_negative_operational_signals = (
        concept_heavy_no_operations
        or glossary_like_semantics
        or terminology_dominant
        or definitions_minimal_no_operations
    )

    if precheck_decision == DECISION_EXTRACT_DEGRADED:
        # Promote degraded precheck chunks when filtered payload has valid doctrinal support.
        if support_level in {"strong", "minimal"} and not has_negative_operational_signals:
            return DECISION_EXTRACT, support_level, reasons
        if support_level == "none" and "insufficient_operational_support" not in reasons:
            reasons.append("insufficient_operational_support")
        return DECISION_EXTRACT_DEGRADED, support_level, reasons

    if support_level in {"strong", "minimal"}:
        if not has_negative_operational_signals:
            return DECISION_EXTRACT, support_level, reasons

    if "insufficient_operational_support" not in reasons:
        reasons.append("insufficient_operational_support")
    return DECISION_EXTRACT_DEGRADED, support_level, reasons


def _effective_decision_state(
    *,
    precheck_decision: str,
    record: ChunkKnowledgeV1,
    chunk_type: str,
    policy_enabled: bool,
) -> tuple[str, str, list[str]]:
    if not policy_enabled:
        return precheck_decision, _doctrinal_support_level(record), []
    decision, support_level, reasons = _decision_from_filtered_payload(
        precheck_decision=precheck_decision,
        record=record,
        chunk_type=chunk_type,
    )
    return decision, support_level, reasons


def _is_garbage_label(label: str) -> bool:
    stripped = label.strip()
    if not stripped:
        return True
    if _is_index_like_label(stripped):
        return True
    if re.search(r"[\^£®§¤¢¥©]", stripped):
        return True
    return False


def _chunk_id_for_index(
    *,
    chunk_index: int,
    chunking_mode: str,
    structural_chunk_records: list[dict[str, object]] | None,
) -> str:
    if chunking_mode == "structural" and structural_chunk_records and chunk_index <= len(structural_chunk_records):
        chunk_id = structural_chunk_records[chunk_index - 1].get("chunk_id")
        if isinstance(chunk_id, str) and chunk_id.strip():
            return chunk_id
    return f"legacy_chunk_{chunk_index}"


def process_book(
    path: str,
    *,
    mode: str = "full",
    max_chunks: int | None = None,
    dry_run: bool = False,
    verbose: bool = False,
    resume: bool = True,
    output_language: str = "es",
    progress_callback: ProgressCallback | None = None,
) -> str:
    """Process a book file and save an aggregated technical summary."""
    if mode not in {"full", "smoke"}:
        raise ValueError("mode must be either 'full' or 'smoke'")
    if max_chunks is not None and max_chunks <= 0:
        raise ValueError("max_chunks must be greater than 0 when provided")
    if output_language not in {"es", "original"}:
        raise ValueError("output_language must be either 'es' or 'original'")

    source_path = Path(path)
    _emit_progress(progress_callback, "loading", f"Cargando documento: {source_path.name}")
    structure_enabled = STRUCTURE_PASS_ENABLED
    if structure_enabled:
        text, page_units = load_book_with_structure(str(source_path))
    else:
        text = load_book(str(source_path))
        page_units = None
    book_hash = _sha256_text(text)
    document_map_path = build_document_map_output_path(str(source_path), OUTPUT_FOLDER)
    structure_map: dict[str, object] | None = None
    structure_quality: dict[str, object] | None = None
    structure_quality_passed: bool | None = None
    structural_postcheck: dict[str, object] | None = None
    structural_postcheck_passed: bool | None = None
    fallback_reason: str | None = None
    excluded_section_types_active = sorted(STRUCTURAL_CHUNKER_EXCLUDED_TYPES)
    excluded_sections_count = 0
    if structure_enabled:
        _emit_progress(progress_callback, "structure", "Construyendo DocumentMap")
        structure_map = build_document_map(
            text,
            source_fingerprint=str(source_path),
            page_units=page_units,
            use_llm=STRUCTURE_PASS_USE_LLM,
            min_heading_score=STRUCTURE_MIN_HEADING_SCORE,
            max_headings_for_llm=STRUCTURE_MAX_HEADINGS_FOR_LLM,
            max_section_size_chars=STRUCTURE_MAX_SECTION_SIZE_CHARS,
        )
        try:
            structure_map = clean_document_map(
                structure_map,  # type: ignore[arg-type]
                max_section_size_chars=STRUCTURE_MAX_SECTION_SIZE_CHARS,
            )
        except ValueError:
            pass
        _log(
            verbose,
            (
                "Structure pass: "
                f"{structure_map['stats']['sections_generated']} sections, "
                f"{structure_map['stats']['heading_candidates']} headings, "
                f"text_hash={structure_map['text_hash']}"
            ),
        )
    _emit_progress(progress_callback, "chunking", "Dividiendo documento en chunks")
    processing_mode = "knowledge_extraction" if KNOWLEDGE_EXTRACTION_ENABLED else "summary"
    chunking_mode = "legacy"
    chunking_target_size = CHUNK_SIZE
    chunking_min_size = 0
    chunking_split_window = 0
    structural_chunk_stats: dict[str, object] | None = None
    structural_chunk_records: list[dict[str, object]] | None = None

    chunks: list[str]
    if (
        STRUCTURAL_CHUNKER_ENABLED
        and structure_enabled
    ):
        if structure_map is None or structure_map.get("text_hash") != book_hash:
            fallback_reason = FALLBACK_REASON_STRUCTURAL_MAP_INVALID
            chunks = split_into_chunks(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)
        else:
            sections = structure_map.get("sections", [])
            if not isinstance(sections, list) or len(sections) <= 1:
                fallback_reason = FALLBACK_REASON_STRUCTURAL_MAP_INSUFFICIENT_SECTIONS
                chunks = split_into_chunks(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)
            else:
                structure_quality, structure_quality_passed, gate_fallback_reason = _evaluate_structure_quality(
                    structure_map,
                    normalized_text=text,
                )
                if not structure_quality_passed:
                    fallback_reason = gate_fallback_reason
                    chunks = split_into_chunks(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)
                else:
                    excluded_sections_count = sum(
                        1
                        for item in sections
                        if isinstance(item, dict)
                        and isinstance(item.get("type"), str)
                        and item["type"] in STRUCTURAL_CHUNKER_EXCLUDED_TYPES
                    )
                    chunk_set = build_structural_chunks(
                        text,
                        structure_map,  # type: ignore[arg-type]
                        target_size=STRUCTURAL_CHUNKER_TARGET_SIZE,
                        min_size=STRUCTURAL_CHUNKER_MIN_SIZE,
                        split_window=STRUCTURAL_CHUNKER_SPLIT_WINDOW,
                        excluded_section_types=STRUCTURAL_CHUNKER_EXCLUDED_TYPES,
                    )
                    structural_chunks = [record["text"] for record in chunk_set["chunks"]]
                    structural_chunk_records = list(chunk_set["chunks"])
                    legacy_reference = split_into_chunks(
                        text,
                        chunk_size=CHUNK_SIZE,
                        overlap=CHUNK_OVERLAP,
                    )
                    legacy_count = max(1, len(legacy_reference))
                    structural_count = len(structural_chunks)
                    small_chunk_min = max(400, STRUCTURAL_CHUNKER_MIN_SIZE // 2)
                    small_chunk_count = sum(1 for chunk in structural_chunks if len(chunk) < small_chunk_min)
                    small_chunk_ratio = _float_ratio(small_chunk_count, max(1, structural_count))
                    structural_postcheck = {
                        "legacy_reference_chunks": legacy_count,
                        "structural_chunks": structural_count,
                        "small_chunk_min_chars": small_chunk_min,
                        "small_chunk_ratio": small_chunk_ratio,
                    }
                    if structural_count > legacy_count * 1.75:
                        structural_postcheck_passed = False
                        fallback_reason = FALLBACK_REASON_POSTCHECK_CHUNK_COUNT
                        chunks = legacy_reference
                        structural_chunk_records = None
                    elif small_chunk_ratio > 0.35:
                        structural_postcheck_passed = False
                        fallback_reason = FALLBACK_REASON_POSTCHECK_SMALL_CHUNK_RATIO
                        chunks = legacy_reference
                        structural_chunk_records = None
                    else:
                        structural_postcheck_passed = True
                        chunks = structural_chunks
                        chunking_mode = "structural"
                        chunking_target_size = STRUCTURAL_CHUNKER_TARGET_SIZE
                        chunking_min_size = STRUCTURAL_CHUNKER_MIN_SIZE
                        chunking_split_window = STRUCTURAL_CHUNKER_SPLIT_WINDOW
                        structural_chunk_stats = dict(chunk_set["stats"])
    else:
        chunks = split_into_chunks(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)
    if not chunks:
        raise ValueError(f"No readable content found in: {source_path}")
    if fallback_reason is not None:
        _log(verbose, f"Fallback to legacy chunking: {fallback_reason}")

    output_path = build_output_path(str(source_path), OUTPUT_FOLDER)
    chunk_output_path = build_chunk_output_path(str(source_path), OUTPUT_FOLDER)
    block_output_path = build_block_output_path(str(source_path), OUTPUT_FOLDER)
    knowledge_output_path = build_knowledge_chunks_output_path(str(source_path), OUTPUT_FOLDER)
    knowledge_audit_output_path = build_knowledge_audit_output_path(str(source_path), OUTPUT_FOLDER)
    total_chunks_detected = len(chunks)
    chunking_hash = _chunking_fingerprint(
        mode=chunking_mode,
        chunk_size=CHUNK_SIZE,
        overlap=CHUNK_OVERLAP,
        target_size=chunking_target_size,
        min_size=chunking_min_size,
        split_window=chunking_split_window,
    )
    checkpoint_namespace = (
        CHECKPOINT_NAMESPACE_KNOWLEDGE if KNOWLEDGE_EXTRACTION_ENABLED else CHECKPOINT_NAMESPACE_SUMMARY
    )
    checkpoint_root = _checkpoint_root(
        OUTPUT_FOLDER,
        book_hash,
        checkpoint_namespace,
        chunking_hash,
    )

    cached_summaries: dict[int, str] = {}
    cached_knowledge: dict[int, ChunkKnowledgeV1] = {}
    if resume:
        if KNOWLEDGE_EXTRACTION_ENABLED:
            cached_knowledge = _load_checkpointed_knowledge(checkpoint_root, total_chunks_detected)
            cached_summaries = {
                idx: chunk_knowledge_to_summary_text(record, output_language=output_language)
                for idx, record in cached_knowledge.items()
            }
        else:
            cached_summaries = _load_checkpointed_summaries(checkpoint_root, total_chunks_detected)

    pending_indices = [
        index for index in range(1, total_chunks_detected + 1) if index not in cached_summaries
    ]
    if max_chunks is not None:
        planned_new_indices = pending_indices[:max_chunks]
    elif mode == "smoke":
        planned_new_indices = pending_indices[:DEFAULT_SMOKE_MAX_CHUNKS]
    else:
        planned_new_indices = pending_indices

    selected_indices = sorted(set(cached_summaries) | set(planned_new_indices))
    chunk_llm_calls_expected = len(planned_new_indices)
    chunks_to_process = len(selected_indices)
    synthesis_llm_calls_expected = expected_synthesis_calls(chunks_to_process)
    llm_calls_expected = chunk_llm_calls_expected + synthesis_llm_calls_expected

    _log(verbose, "== Preflight ==")
    _log(verbose, f"Mode: {mode}")
    _log(verbose, f"Processing mode: {processing_mode}")
    _log(verbose, f"Dry run: {dry_run}")
    _log(verbose, f"Resume enabled: {resume}")
    _log(verbose, f"Total chunks detected: {total_chunks_detected}")
    _log(verbose, f"Chunks to process: {chunks_to_process}")
    _log(verbose, f"LLM calls expected (chunk layer): {chunk_llm_calls_expected}")
    _log(verbose, f"LLM calls expected (synthesis layer): {synthesis_llm_calls_expected}")
    _log(verbose, f"LLM calls expected: {llm_calls_expected}")
    _log(verbose, f"Estimated relative cost: {_relative_cost_scale(llm_calls_expected)}")
    _emit_progress(
        progress_callback,
        "preflight",
        (
            f"Preflight listo: {chunks_to_process} chunks a procesar "
            f"({chunk_llm_calls_expected} nuevos, idioma={output_language})"
        ),
        total_chunks_detected=total_chunks_detected,
        chunks_to_process=chunks_to_process,
        chunk_llm_calls_expected=chunk_llm_calls_expected,
        synthesis_llm_calls_expected=synthesis_llm_calls_expected,
    )

    if dry_run:
        _log(verbose, "Dry run active: skipping LLM calls, compilation, and file writes.")
        _log(verbose, "== Final Summary ==")
        _log(verbose, f"Total chunks detected: {total_chunks_detected}")
        _log(verbose, f"Chunks to process: {chunks_to_process}")
        _log(verbose, "Chunks really processed: 0")
        _log(verbose, f"LLM calls expected (chunk layer): {chunk_llm_calls_expected}")
        _log(verbose, f"LLM calls expected (synthesis layer): {synthesis_llm_calls_expected}")
        _log(verbose, f"LLM calls expected: {llm_calls_expected}")
        _log(verbose, "LLM calls made: 0")
        _log(verbose, f"Output path (not written): {output_path}")
        _emit_progress(progress_callback, "dry_run", "Dry run completado, sin escribir archivos")
        return output_path

    chunk_llm_calls_made = 0
    summaries_by_index = dict(cached_summaries)
    knowledge_records_by_index = dict(cached_knowledge)
    knowledge_parse_failures = 0
    precheck_decision_counts = {
        DECISION_EXTRACT: 0,
        DECISION_EXTRACT_DEGRADED: 0,
        DECISION_SKIP: 0,
    }
    precheck_reason_counts: dict[str, int] = {}
    precheck_signals_by_index: dict[int, dict[str, float | int | bool]] = {}
    precheck_applied_by_index: dict[int, str] = {}
    precheck_reason_codes_by_index: dict[int, list[str]] = {}
    precheck_type_by_index: dict[int, str] = {}
    precheck_type_score_by_index: dict[int, float] = {}
    precheck_confidence_by_index: dict[int, str] = {}
    precheck_dominant_signals_by_index: dict[int, list[str]] = {}
    precheck_mixed_reason_by_index: dict[int, str | None] = {}
    policy_decision_by_index: dict[int, str] = {}
    policy_reason_codes_by_index: dict[int, list[str]] = {}
    doctrinal_support_level_by_index: dict[int, str] = {}
    weak_support_pattern_by_index: dict[int, bool] = {}
    core_doctrine_pre_clamp_by_index: dict[int, bool] = {}
    clamp_actions_by_index: dict[int, list[str]] = {}
    semantic_filter_actions_by_index: dict[int, list[str]] = {}
    for run_position, chunk_index in enumerate(planned_new_indices, start=1):
        _log(
            verbose,
            f"[Chunk {run_position}/{len(planned_new_indices)}] Summarizing source chunk {chunk_index}",
        )
        _emit_progress(
            progress_callback,
            "summarizing",
            f"Resumiendo chunk {run_position}/{len(planned_new_indices)} (origen #{chunk_index})",
            run_position=run_position,
            total_new_chunks=len(planned_new_indices),
            chunk_index=chunk_index,
        )
        if KNOWLEDGE_EXTRACTION_ENABLED:
            chunk_id = _chunk_id_for_index(
                chunk_index=chunk_index,
                chunking_mode=chunking_mode,
                structural_chunk_records=structural_chunk_records,
            )
            section_refs = _build_section_refs_for_chunk(
                chunk_index=chunk_index,
                chunking_mode=chunking_mode,
                structural_chunk_records=structural_chunk_records,
                structure_map=structure_map,
            )
            chunk_text = chunks[chunk_index - 1]
            precheck_decision = DECISION_EXTRACT
            if KNOWLEDGE_PRECHECK_ENABLED:
                precheck = precheck_chunk_extractability(
                    chunk_text=chunk_text,
                    section_refs=section_refs,
                    review_default=KNOWLEDGE_PRECHECK_REVIEW_DEFAULT,
                )
                precheck_applied_by_index[chunk_index] = precheck.decision
                precheck_signals_by_index[chunk_index] = precheck.signals
                precheck_reason_codes_by_index[chunk_index] = list(precheck.reason_codes)
                if precheck.decision in precheck_decision_counts:
                    precheck_decision_counts[precheck.decision] += 1
                precheck_type_by_index[chunk_index] = precheck.chunk_type
                precheck_type_score_by_index[chunk_index] = precheck.type_score
                precheck_confidence_by_index[chunk_index] = precheck.confidence_profile
                precheck_dominant_signals_by_index[chunk_index] = precheck.dominant_signals
                precheck_mixed_reason_by_index[chunk_index] = precheck.mixed_reason
                for reason_code in precheck.reason_codes:
                    precheck_reason_counts[reason_code] = precheck_reason_counts.get(reason_code, 0) + 1
                precheck_decision = precheck.decision

            if precheck_decision == DECISION_SKIP:
                record = make_empty_chunk_knowledge(
                    chunk_id=chunk_id,
                    source_fingerprint=book_hash,
                    section_refs=section_refs,
                )
                policy_decision_by_index[chunk_index] = DECISION_SKIP
                policy_reason_codes_by_index[chunk_index] = []
                doctrinal_support_level_by_index[chunk_index] = "none"
                weak_support_pattern_by_index[chunk_index] = False
                core_doctrine_pre_clamp_by_index[chunk_index] = False
                semantic_filter_actions_by_index[chunk_index] = []
                knowledge_records_by_index[chunk_index] = record
                chunk_summary = chunk_knowledge_to_summary_text(record, output_language=output_language)
            else:
                extraction = extract_chunk_knowledge(
                    chunk_text=chunk_text,
                    chunk_id=chunk_id,
                    source_fingerprint=book_hash,
                    section_refs=section_refs,
                )
                if extraction.used_fallback:
                    knowledge_parse_failures += 1
                    _log(verbose, f"[Chunk {chunk_index}] Knowledge parse fallback: {extraction.parse_error}")
                record = extraction.record
                record, semantic_filter_actions = apply_semantic_local_filter(
                    record,
                    filter_editorial=KNOWLEDGE_FILTER_EDITORIAL_ENABLE,
                    filter_generic_definitions=KNOWLEDGE_FILTER_GENERIC_DEFINITIONS_ENABLE,
                    filter_modern=KNOWLEDGE_FILTER_MODERN_ENABLE,
                )
                semantic_filter_actions_by_index[chunk_index] = semantic_filter_actions
                core_doctrine_pre_clamp_by_index[chunk_index] = _has_core_doctrinal_content(record)
                effective_decision, support_level, policy_reasons = _effective_decision_state(
                    precheck_decision=precheck_decision,
                    record=record,
                    chunk_type=precheck_type_by_index.get(chunk_index, "doctrinal_text"),
                    policy_enabled=KNOWLEDGE_DECISION_POLICY_ENABLE,
                )
                policy_decision_by_index[chunk_index] = effective_decision
                doctrinal_support_level_by_index[chunk_index] = support_level
                policy_reason_codes_by_index[chunk_index] = policy_reasons
                weak_support_pattern = _is_concept_heavy_doctrine_light(record)
                weak_support_pattern_by_index[chunk_index] = weak_support_pattern
                if KNOWLEDGE_CLAMP_ENABLE:
                    confidence_profile = precheck_confidence_by_index.get(chunk_index, "medium")
                    chunk_type = precheck_type_by_index.get(chunk_index, "doctrinal_text")
                    record, clamp_actions = apply_post_extraction_clamp(
                        record,
                        confidence_profile=confidence_profile,
                        decision=effective_decision,
                        chunk_type=chunk_type,
                        chunk_text=chunk_text,
                        weak_support_pattern=weak_support_pattern,
                        weak_support_concepts_max=max(0, KNOWLEDGE_DEGRADED_WEAK_SUPPORT_CONCEPTS_MAX),
                        weak_support_terminology_max=max(0, KNOWLEDGE_DEGRADED_WEAK_SUPPORT_TERMINOLOGY_MAX),
                    )
                    clamp_actions_by_index[chunk_index] = clamp_actions
                knowledge_records_by_index[chunk_index] = record
                chunk_summary = chunk_knowledge_to_summary_text(record, output_language=output_language)
                chunk_llm_calls_made += 1
        elif output_language == "es":
            chunk_summary = summarize_chunk(chunks[chunk_index - 1])
            chunk_llm_calls_made += 1
        else:
            chunk_summary = summarize_chunk(
                chunks[chunk_index - 1],
                output_language=output_language,
            )
            chunk_llm_calls_made += 1
        summaries_by_index[chunk_index] = chunk_summary

        if resume:
            ensure_dir(str(checkpoint_root))
            if KNOWLEDGE_EXTRACTION_ENABLED:
                save_text(
                    str(_knowledge_checkpoint_path(checkpoint_root, chunk_index)),
                    json.dumps(knowledge_records_by_index[chunk_index].to_dict(), ensure_ascii=False),
                )
            else:
                save_text(str(_chunk_checkpoint_path(checkpoint_root, chunk_index)), chunk_summary)

    if resume:
        ensure_dir(str(checkpoint_root))
        _save_manifest(
            checkpoint_root,
            {
                "input_path": str(source_path),
                "processing_mode": processing_mode,
                "book_fingerprint": book_hash,
                "chunking_fingerprint": chunking_hash,
                "chunk_size": CHUNK_SIZE,
                "chunk_overlap": CHUNK_OVERLAP,
                "chunking": {
                    "mode": chunking_mode,
                    "target_size": chunking_target_size,
                    "min_size": chunking_min_size,
                    "split_window": chunking_split_window,
                },
                "total_chunks_detected": total_chunks_detected,
                "structure_enabled": structure_enabled,
                "structure_version": (
                    structure_map["version"] if structure_enabled and structure_map is not None else None
                ),
                "structure_generator": (
                    structure_map["generator"] if structure_enabled and structure_map is not None else None
                ),
                "document_map_text_hash": (
                    structure_map["text_hash"] if structure_enabled and structure_map is not None else None
                ),
                "structural_chunk_stats": (
                    structural_chunk_stats if chunking_mode == "structural" else None
                ),
                "structure_quality": structure_quality,
                "structure_quality_passed": structure_quality_passed,
                "structural_postcheck": structural_postcheck,
                "structural_postcheck_passed": structural_postcheck_passed,
                "fallback_reason": fallback_reason,
                "excluded_section_types_active": excluded_section_types_active,
                "excluded_sections_count": excluded_sections_count,
                "knowledge_parse_failures": knowledge_parse_failures if KNOWLEDGE_EXTRACTION_ENABLED else 0,
                "knowledge_precheck_enabled": KNOWLEDGE_PRECHECK_ENABLED,
                "knowledge_precheck_review_default": KNOWLEDGE_PRECHECK_REVIEW_DEFAULT,
                "knowledge_precheck_decision_counts": (
                    precheck_decision_counts if KNOWLEDGE_EXTRACTION_ENABLED else None
                ),
                "knowledge_precheck_reason_counts": (
                    dict(sorted(precheck_reason_counts.items())) if KNOWLEDGE_EXTRACTION_ENABLED else None
                ),
            },
        )

    ordered_summaries = [summaries_by_index[index] for index in selected_indices]
    ordered_knowledge_records = [
        knowledge_records_by_index[index]
        for index in selected_indices
        if index in knowledge_records_by_index
    ]
    chunks_really_processed = len(ordered_summaries)
    knowledge_chunks_generated = len(ordered_knowledge_records)
    valid_chunk_knowledge_count = max(0, knowledge_chunks_generated - knowledge_parse_failures)
    total_concepts = sum(len(record.concepts) for record in ordered_knowledge_records)
    total_rules = sum(len(record.technical_rules) for record in ordered_knowledge_records)
    total_definitions = sum(len(record.definitions) for record in ordered_knowledge_records)
    chunks_with_terminology = sum(1 for record in ordered_knowledge_records if len(record.terminology) > 0)
    chunks_with_technical_rule = sum(1 for record in ordered_knowledge_records if len(record.technical_rules) > 0)
    total_knowledge_items = sum(
        len(record.concepts)
        + len(record.definitions)
        + len(record.technical_rules)
        + len(record.procedures)
        + len(record.terminology)
        for record in ordered_knowledge_records
    )
    avg_concepts_per_chunk = _float_ratio(total_concepts, max(1, knowledge_chunks_generated))
    avg_rules_per_chunk = _float_ratio(total_rules, max(1, knowledge_chunks_generated))
    avg_definitions_per_chunk = _float_ratio(total_definitions, max(1, knowledge_chunks_generated))
    chunk_terminology_ratio = _float_ratio(chunks_with_terminology, max(1, knowledge_chunks_generated))
    chunk_rule_ratio = _float_ratio(chunks_with_technical_rule, max(1, knowledge_chunks_generated))
    knowledge_avg_items_per_chunk = _float_ratio(total_knowledge_items, max(1, knowledge_chunks_generated))

    def _decision_state_for_index(index: int) -> str:
        return policy_decision_by_index.get(index, precheck_applied_by_index.get(index, DECISION_EXTRACT))

    extracted_chunk_count = sum(
        1
        for index in selected_indices
        if (
            index in knowledge_records_by_index
            and _decision_state_for_index(index) in {DECISION_EXTRACT, DECISION_EXTRACT_DEGRADED}
        )
    )
    extracted_knowledge_records = [
        knowledge_records_by_index[index]
        for index in selected_indices
        if (
            index in knowledge_records_by_index
            and _decision_state_for_index(index) in {DECISION_EXTRACT, DECISION_EXTRACT_DEGRADED}
        )
    ]
    skipped_chunk_count = sum(
        1
        for index in selected_indices
        if _decision_state_for_index(index) == DECISION_SKIP
    )
    extract_degraded_count = sum(
        1
        for index in selected_indices
        if _decision_state_for_index(index) == DECISION_EXTRACT_DEGRADED
    )
    decision_state_counts = {
        DECISION_EXTRACT: sum(1 for index in selected_indices if _decision_state_for_index(index) == DECISION_EXTRACT),
        DECISION_EXTRACT_DEGRADED: sum(
            1 for index in selected_indices if _decision_state_for_index(index) == DECISION_EXTRACT_DEGRADED
        ),
        DECISION_SKIP: sum(1 for index in selected_indices if _decision_state_for_index(index) == DECISION_SKIP),
    }
    extract_strong_count = sum(
        1
        for index in selected_indices
        if _decision_state_for_index(index) == DECISION_EXTRACT
        and doctrinal_support_level_by_index.get(index, "none") == "strong"
    )
    extract_minimal_count = sum(
        1
        for index in selected_indices
        if _decision_state_for_index(index) == DECISION_EXTRACT
        and doctrinal_support_level_by_index.get(index, "none") == "minimal"
    )
    concept_heavy_degraded_count = sum(
        1
        for index in selected_indices
        if _decision_state_for_index(index) == DECISION_EXTRACT_DEGRADED
        and "concept_heavy_no_operations" in policy_reason_codes_by_index.get(index, [])
    )
    glossary_like_degraded_count = sum(
        1
        for index in selected_indices
        if _decision_state_for_index(index) == DECISION_EXTRACT_DEGRADED
        and "glossary_like_semantics" in policy_reason_codes_by_index.get(index, [])
    )
    terminology_dominant_degraded_count = sum(
        1
        for index in selected_indices
        if _decision_state_for_index(index) == DECISION_EXTRACT_DEGRADED
        and "terminology_dominant_no_operations" in policy_reason_codes_by_index.get(index, [])
    )
    empty_or_near_empty_skip_count = sum(
        1
        for index in selected_indices
        if _decision_state_for_index(index) == DECISION_SKIP
        and "semantic_payload_empty_or_near_empty" in policy_reason_codes_by_index.get(index, [])
    )
    concept_heavy_doctrine_light_count = sum(
        1 for record in ordered_knowledge_records if _is_concept_heavy_doctrine_light(record)
    )
    concept_heavy_doctrine_light_ratio = _float_ratio(
        concept_heavy_doctrine_light_count,
        max(1, chunks_really_processed),
    )
    knowledge_items_average_by_decision: dict[str, float] = {}
    state_field_averages: dict[str, dict[str, float]] = {}
    for decision_state in (DECISION_EXTRACT, DECISION_EXTRACT_DEGRADED, DECISION_SKIP):
        records_for_state = [
            knowledge_records_by_index[index]
            for index in selected_indices
            if index in knowledge_records_by_index and _decision_state_for_index(index) == decision_state
        ]
        state_items_total = sum(
            len(record.concepts)
            + len(record.definitions)
            + len(record.technical_rules)
            + len(record.procedures)
            + len(record.terminology)
            for record in records_for_state
        )
        knowledge_items_average_by_decision[decision_state] = _float_ratio(
            state_items_total,
            max(1, len(records_for_state)),
        )
        state_field_averages[decision_state] = {
            "concepts": _float_ratio(sum(len(record.concepts) for record in records_for_state), max(1, len(records_for_state))),
            "definitions": _float_ratio(sum(len(record.definitions) for record in records_for_state), max(1, len(records_for_state))),
            "technical_rules": _float_ratio(
                sum(len(record.technical_rules) for record in records_for_state),
                max(1, len(records_for_state)),
            ),
            "procedures": _float_ratio(sum(len(record.procedures) for record in records_for_state), max(1, len(records_for_state))),
        }
    degraded_chunks_with_core_doctrine = sum(
        1
        for index in selected_indices
        if (
            index in knowledge_records_by_index
            and _decision_state_for_index(index) == DECISION_EXTRACT_DEGRADED
            and core_doctrine_pre_clamp_by_index.get(
                index,
                _has_core_doctrinal_content(knowledge_records_by_index[index]),
            )
        )
    )
    degraded_chunks_with_core_doctrine_ratio = _float_ratio(
        degraded_chunks_with_core_doctrine,
        max(1, extract_degraded_count),
    )
    all_fields_empty_count = sum(1 for record in ordered_knowledge_records if _all_fields_empty(record))
    all_fields_empty_extracted_count = sum(1 for record in extracted_knowledge_records if _all_fields_empty(record))
    all_fields_empty_ratio_over_all_chunks = _float_ratio(all_fields_empty_count, max(1, chunks_really_processed))
    all_fields_empty_ratio_over_extracted_chunks = _float_ratio(
        all_fields_empty_extracted_count,
        max(1, extracted_chunk_count),
    )
    parse_failure_ratio_over_all_chunks = _float_ratio(knowledge_parse_failures, max(1, chunks_really_processed))
    parse_failure_ratio_over_extracted_chunks = _float_ratio(
        knowledge_parse_failures,
        max(1, extracted_chunk_count),
    )
    nonempty_ratio_by_field_over_all_chunks: dict[str, float] = {}
    nonempty_ratio_by_field_over_extracted_chunks: dict[str, float] = {}
    for field_name in SEMANTIC_FIELDS:
        nonempty_count = sum(1 for record in ordered_knowledge_records if len(getattr(record, field_name)) > 0)
        nonempty_extracted_count = sum(
            1 for record in extracted_knowledge_records if len(getattr(record, field_name)) > 0
        )
        nonempty_ratio_by_field_over_all_chunks[field_name] = _float_ratio(nonempty_count, max(1, chunks_really_processed))
        nonempty_ratio_by_field_over_extracted_chunks[field_name] = _float_ratio(
            nonempty_extracted_count,
            max(1, extracted_chunk_count),
        )

    section_type_distribution: dict[str, int] = {}
    unknown_section_chunks = 0
    garbage_label_chunks = 0
    for record in ordered_knowledge_records:
        ref_types = {ref.type for ref in record.section_refs if isinstance(ref.type, str)}
        if not ref_types:
            section_type_distribution["none"] = section_type_distribution.get("none", 0) + 1
        else:
            for section_type in sorted(ref_types):
                section_type_distribution[section_type] = section_type_distribution.get(section_type, 0) + 1
        if any(ref.type == "unknown" for ref in record.section_refs):
            unknown_section_chunks += 1
        if record.section_refs and all(_is_garbage_label(ref.label) for ref in record.section_refs):
            garbage_label_chunks += 1
    unknown_section_ratio_over_all_chunks = _float_ratio(unknown_section_chunks, max(1, chunks_really_processed))
    unknown_section_extracted_chunks = sum(
        1 for record in extracted_knowledge_records if any(ref.type == "unknown" for ref in record.section_refs)
    )
    unknown_section_ratio_over_extracted_chunks = _float_ratio(
        unknown_section_extracted_chunks,
        max(1, extracted_chunk_count),
    )
    garbage_label_ratio_over_all_chunks = _float_ratio(garbage_label_chunks, max(1, chunks_really_processed))
    garbage_label_extracted_chunks = sum(
        1
        for record in extracted_knowledge_records
        if record.section_refs and all(_is_garbage_label(ref.label) for ref in record.section_refs)
    )
    garbage_label_ratio_over_extracted_chunks = _float_ratio(
        garbage_label_extracted_chunks,
        max(1, extracted_chunk_count),
    )
    knowledge_audit_records: list[dict[str, object]] = []
    clamp_action_counts: dict[str, int] = {}
    semantic_filter_action_counts: dict[str, int] = {}
    if KNOWLEDGE_EXTRACTION_ENABLED:
        for index in selected_indices:
            if index not in knowledge_records_by_index:
                continue
            audit_row: dict[str, object] = {
                "chunk_index": index,
                "chunk_id": knowledge_records_by_index[index].chunk_id,
                "chunk_type": precheck_type_by_index.get(index, "doctrinal_text"),
                "type_score": precheck_type_score_by_index.get(index, 0.0),
                "signals": precheck_signals_by_index.get(index, {}),
                "precheck_decision": precheck_applied_by_index.get(index, DECISION_EXTRACT),
                "decision": _decision_state_for_index(index),
                "policy_reason_codes": policy_reason_codes_by_index.get(index, []),
                "doctrinal_support_level": doctrinal_support_level_by_index.get(index, "none"),
                "weak_support_pattern": weak_support_pattern_by_index.get(index, False),
                "confidence_profile": precheck_confidence_by_index.get(index, "medium"),
                "reason_codes": precheck_reason_codes_by_index.get(index, []),
                "dominant_signals": precheck_dominant_signals_by_index.get(index, []),
                "mixed_reason": precheck_mixed_reason_by_index.get(index),
                "semantic_filter_actions": semantic_filter_actions_by_index.get(index, []),
                "clamp_actions": clamp_actions_by_index.get(index, []),
            }
            knowledge_audit_records.append(audit_row)
            for action in clamp_actions_by_index.get(index, []):
                clamp_action_counts[action] = clamp_action_counts.get(action, 0) + 1
            for action in semantic_filter_actions_by_index.get(index, []):
                semantic_filter_action_counts[action] = semantic_filter_action_counts.get(action, 0) + 1
    if resume:
        manifest_path = checkpoint_root / "manifest.json"
        try:
            manifest_payload: dict[str, object] = {}
            if manifest_path.exists():
                loaded_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                if isinstance(loaded_manifest, dict):
                    manifest_payload = loaded_manifest
            manifest_payload.update(
                {
                    "total_chunks": chunks_really_processed,
                    "chunks_sent_to_extraction": extracted_chunk_count,
                    "chunks_skipped_by_precheck": skipped_chunk_count,
                    "chunks_extract_degraded": extract_degraded_count,
                    "extract_strong_count": extract_strong_count,
                    "extract_minimal_count": extract_minimal_count,
                    "concept_heavy_degraded_count": concept_heavy_degraded_count,
                    "glossary_like_degraded_count": glossary_like_degraded_count,
                    "terminology_dominant_degraded_count": terminology_dominant_degraded_count,
                    "empty_or_near_empty_skip_count": empty_or_near_empty_skip_count,
                    "knowledge_decision_policy_enabled": KNOWLEDGE_DECISION_POLICY_ENABLE,
                    "knowledge_decision_state_distribution": decision_state_counts,
                    "concept_heavy_doctrine_light_ratio": concept_heavy_doctrine_light_ratio,
                    "knowledge_avg_items_per_decision_state": knowledge_items_average_by_decision,
                    "knowledge_avg_fields_per_decision_state": state_field_averages,
                    "degraded_chunks_with_core_doctrinal_content_ratio": degraded_chunks_with_core_doctrine_ratio,
                    "all_fields_empty_ratio_over_all_chunks": all_fields_empty_ratio_over_all_chunks,
                    "all_fields_empty_ratio_over_extracted_chunks": all_fields_empty_ratio_over_extracted_chunks,
                    "parse_failure_ratio_over_all_chunks": parse_failure_ratio_over_all_chunks,
                    "parse_failure_ratio_over_extracted_chunks": parse_failure_ratio_over_extracted_chunks,
                    "nonempty_ratio_by_field_over_all_chunks": nonempty_ratio_by_field_over_all_chunks,
                    "nonempty_ratio_by_field_over_extracted_chunks": nonempty_ratio_by_field_over_extracted_chunks,
                    "section_type_distribution": section_type_distribution,
                    "unknown_section_ratio_over_all_chunks": unknown_section_ratio_over_all_chunks,
                    "unknown_section_ratio_over_extracted_chunks": unknown_section_ratio_over_extracted_chunks,
                    "garbage_label_ratio_over_all_chunks": garbage_label_ratio_over_all_chunks,
                    "garbage_label_ratio_over_extracted_chunks": garbage_label_ratio_over_extracted_chunks,
                    "knowledge_core_fields": list(CORE_FIELDS),
                    "knowledge_clamp_enabled": KNOWLEDGE_CLAMP_ENABLE,
                    "knowledge_filter_editorial_enabled": KNOWLEDGE_FILTER_EDITORIAL_ENABLE,
                    "knowledge_filter_generic_definitions_enabled": KNOWLEDGE_FILTER_GENERIC_DEFINITIONS_ENABLE,
                    "knowledge_filter_modern_enabled": KNOWLEDGE_FILTER_MODERN_ENABLE,
                    "knowledge_clamp_action_counts": dict(sorted(clamp_action_counts.items())),
                    "knowledge_semantic_filter_action_counts": dict(sorted(semantic_filter_action_counts.items())),
                    "knowledge_audit_output_path": (
                        knowledge_audit_output_path if KNOWLEDGE_EXTRACTION_ENABLED else None
                    ),
                    "knowledge_precheck_type_distribution": dict(
                        sorted(
                            {
                                chunk_type: sum(1 for _, value in precheck_type_by_index.items() if value == chunk_type)
                                for chunk_type in set(precheck_type_by_index.values())
                            }.items()
                        )
                    ),
                    "knowledge_precheck_confidence_distribution": dict(
                        sorted(
                            {
                                profile: sum(1 for _, value in precheck_confidence_by_index.items() if value == profile)
                                for profile in set(precheck_confidence_by_index.values())
                            }.items()
                        )
                    ),
                }
            )
            _save_manifest(checkpoint_root, manifest_payload)
        except (json.JSONDecodeError, OSError):
            pass
    chunk_summary_records = make_chunk_summary_records(ordered_summaries)
    block_total = (len(chunk_summary_records) + 7) // 8
    _emit_progress(progress_callback, "synthesis", "Sintetizando bloques")

    def on_block_progress(block_index: int, total_blocks: int) -> None:
        _log(verbose, f"[Block {block_index}/{total_blocks}] Summarizing block")
        _emit_progress(
            progress_callback,
            "synthesis",
            f"Resumiendo bloque {block_index}/{total_blocks}",
            block_index=block_index,
            total_blocks=total_blocks,
        )

    if output_language == "es":
        block_summary_records, block_llm_calls = synthesize_blocks(
            chunk_summary_records,
            progress_callback=on_block_progress,
        )
    else:
        block_summary_records, block_llm_calls = synthesize_blocks(
            chunk_summary_records,
            output_language=output_language,
            progress_callback=on_block_progress,
        )

    _log(verbose, f"[Compendium] Building final compendium from {block_total} blocks")
    _emit_progress(progress_callback, "synthesis", "Generando compendio final")
    if output_language == "es":
        compendium_summary, compendium_llm_calls = synthesize_compendium(block_summary_records)
    else:
        compendium_summary, compendium_llm_calls = synthesize_compendium(
            block_summary_records,
            output_language=output_language,
        )
    synthesis_llm_calls_made = block_llm_calls + compendium_llm_calls
    llm_calls_made = chunk_llm_calls_made + synthesis_llm_calls_made

    chunk_summary_artifact = compile_chunk_summaries(ordered_summaries)
    block_summary_artifact = compile_block_summaries(block_summary_records)
    final_summary = compile_compendium(compendium_summary)

    ensure_dir(OUTPUT_FOLDER)
    _emit_progress(progress_callback, "writing", "Guardando artefactos de salida")
    save_text(chunk_output_path, chunk_summary_artifact)
    save_text(block_output_path, block_summary_artifact)
    save_text(output_path, final_summary)
    if KNOWLEDGE_EXTRACTION_ENABLED:
        knowledge_lines = [
            json.dumps(record.to_dict(), ensure_ascii=False)
            for record in ordered_knowledge_records
        ]
        save_text(knowledge_output_path, "\n".join(knowledge_lines))
        audit_lines = [json.dumps(row, ensure_ascii=False) for row in knowledge_audit_records]
        save_text(knowledge_audit_output_path, "\n".join(audit_lines))
    if structure_enabled and structure_map is not None:
        sidecar_payload = build_document_map_sidecar_payload(
            structure_map,
            pipeline_version=PIPELINE_VERSION,
        )
        save_text(document_map_path, serialize_document_map_sidecar(sidecar_payload))

    _log(verbose, "== Final Summary ==")
    _log(verbose, f"Processing mode: {processing_mode}")
    _log(verbose, f"Total chunks detected: {total_chunks_detected}")
    _log(verbose, f"Chunks to process: {chunks_to_process}")
    _log(verbose, f"Chunks really processed: {chunks_really_processed}")
    _log(verbose, f"LLM calls expected (chunk layer): {chunk_llm_calls_expected}")
    _log(verbose, f"LLM calls expected (synthesis layer): {synthesis_llm_calls_expected}")
    _log(verbose, f"LLM calls made (chunk layer): {chunk_llm_calls_made}")
    _log(verbose, f"LLM calls made (synthesis layer): {synthesis_llm_calls_made}")
    _log(verbose, f"LLM calls expected: {llm_calls_expected}")
    _log(verbose, f"LLM calls made: {llm_calls_made}")
    _log(verbose, f"Chunk output path: {chunk_output_path}")
    _log(verbose, f"Block output path: {block_output_path}")
    _log(verbose, f"Output path: {output_path}")
    if KNOWLEDGE_EXTRACTION_ENABLED:
        _log(verbose, f"Knowledge output path: {knowledge_output_path}")
        _log(verbose, f"Knowledge audit path: {knowledge_audit_output_path}")
        _log(verbose, f"total_chunks: {chunks_really_processed}")
        _log(verbose, f"chunks_sent_to_extraction: {extracted_chunk_count}")
        _log(verbose, f"chunks_skipped_by_precheck: {skipped_chunk_count}")
        _log(verbose, f"chunks_extract_degraded: {extract_degraded_count}")
        _log(verbose, f"extract_strong_count: {extract_strong_count}")
        _log(verbose, f"extract_minimal_count: {extract_minimal_count}")
        _log(verbose, f"concept_heavy_degraded_count: {concept_heavy_degraded_count}")
        _log(verbose, f"glossary_like_degraded_count: {glossary_like_degraded_count}")
        _log(verbose, f"terminology_dominant_degraded_count: {terminology_dominant_degraded_count}")
        _log(verbose, f"empty_or_near_empty_skip_count: {empty_or_near_empty_skip_count}")
        _log(verbose, f"knowledge_chunks_generated: {knowledge_chunks_generated}")
        _log(verbose, f"knowledge_parse_failures: {knowledge_parse_failures}")
        _log(verbose, f"all_fields_empty_ratio_over_all_chunks: {all_fields_empty_ratio_over_all_chunks:.4f}")
        _log(verbose, f"all_fields_empty_ratio_over_extracted_chunks: {all_fields_empty_ratio_over_extracted_chunks:.4f}")
        _log(verbose, f"parse_failure_ratio_over_all_chunks: {parse_failure_ratio_over_all_chunks:.4f}")
        _log(verbose, f"parse_failure_ratio_over_extracted_chunks: {parse_failure_ratio_over_extracted_chunks:.4f}")
        _log(
            verbose,
            "nonempty_ratio_by_field_over_all_chunks: "
            f"{json.dumps(nonempty_ratio_by_field_over_all_chunks, sort_keys=True)}",
        )
        _log(
            verbose,
            "nonempty_ratio_by_field_over_extracted_chunks: "
            f"{json.dumps(nonempty_ratio_by_field_over_extracted_chunks, sort_keys=True)}",
        )
        _log(verbose, f"section_type_distribution: {json.dumps(section_type_distribution, sort_keys=True)}")
        _log(verbose, f"unknown_section_ratio_over_all_chunks: {unknown_section_ratio_over_all_chunks:.4f}")
        _log(verbose, f"unknown_section_ratio_over_extracted_chunks: {unknown_section_ratio_over_extracted_chunks:.4f}")
        _log(verbose, f"garbage_label_ratio_over_all_chunks: {garbage_label_ratio_over_all_chunks:.4f}")
        _log(verbose, f"garbage_label_ratio_over_extracted_chunks: {garbage_label_ratio_over_extracted_chunks:.4f}")
        _log(verbose, f"valid_chunk_knowledge_count: {valid_chunk_knowledge_count}")
        _log(verbose, f"avg_concepts_per_chunk: {avg_concepts_per_chunk:.4f}")
        _log(verbose, f"avg_rules_per_chunk: {avg_rules_per_chunk:.4f}")
        _log(verbose, f"avg_definitions_per_chunk: {avg_definitions_per_chunk:.4f}")
        _log(verbose, f"% chunks with terminology: {chunk_terminology_ratio * 100.0:.2f}")
        _log(verbose, f"% chunks with at least 1 technical_rule: {chunk_rule_ratio * 100.0:.2f}")
        _log(verbose, f"knowledge_avg_items_per_chunk: {knowledge_avg_items_per_chunk:.4f}")
        _log(
            verbose,
            "knowledge_decision_state_distribution: "
            f"{json.dumps(decision_state_counts, sort_keys=True)}",
        )
        _log(verbose, f"concept_heavy_doctrine_light_ratio: {concept_heavy_doctrine_light_ratio:.4f}")
        _log(
            verbose,
            "knowledge_avg_items_per_decision_state: "
            f"{json.dumps(knowledge_items_average_by_decision, sort_keys=True)}",
        )
        _log(
            verbose,
            "knowledge_avg_fields_per_decision_state: "
            f"{json.dumps(state_field_averages, sort_keys=True)}",
        )
        _log(
            verbose,
            "degraded_chunks_with_core_doctrinal_content_ratio: "
            f"{degraded_chunks_with_core_doctrine_ratio:.4f}",
        )
    if structure_enabled and structure_map is not None:
        _log(verbose, f"Document map output path: {document_map_path}")
    _emit_progress(
        progress_callback,
        "done",
        "Proceso completado",
        output_path=output_path,
        chunk_output_path=chunk_output_path,
        block_output_path=block_output_path,
        knowledge_output_path=(knowledge_output_path if KNOWLEDGE_EXTRACTION_ENABLED else None),
        document_map_path=(document_map_path if structure_enabled and structure_map is not None else None),
        llm_calls_made=llm_calls_made,
    )

    return output_path
