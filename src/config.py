"""Project configuration loaded from environment variables."""

from __future__ import annotations

import os


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return parsed


def _get_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = float(value)
    except ValueError:
        return default
    return parsed


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_csv_set(name: str, default: set[str]) -> set[str]:
    value = os.getenv(name)
    if value is None:
        return set(default)
    parsed = {
        item.strip().lower()
        for item in value.split(",")
        if item.strip()
    }
    return parsed if parsed else set(default)


OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")
MODEL_NAME: str = os.getenv("MODEL_NAME", "gpt-4.1-mini")
OPENAI_TIMEOUT_SECONDS: float = _get_float("OPENAI_TIMEOUT_SECONDS", 60.0)
OPENAI_MAX_RETRIES: int = _get_int("OPENAI_MAX_RETRIES", 6)
OPENAI_RETRY_BACKOFF_SECONDS: float = _get_float("OPENAI_RETRY_BACKOFF_SECONDS", 1.0)
CHUNK_SIZE: int = _get_int("CHUNK_SIZE", 1800)
CHUNK_OVERLAP: int = _get_int("CHUNK_OVERLAP", 200)
OUTPUT_FOLDER: str = os.getenv("OUTPUT_FOLDER", "outputs")
STRUCTURE_PASS_ENABLED: bool = _get_bool("STRUCTURE_PASS_ENABLED", True)
STRUCTURE_PASS_USE_LLM: bool = _get_bool("STRUCTURE_PASS_USE_LLM", True)
STRUCTURE_MIN_HEADING_SCORE: float = _get_float("STRUCTURE_MIN_HEADING_SCORE", 0.55)
STRUCTURE_MAX_HEADINGS_FOR_LLM: int = _get_int("STRUCTURE_MAX_HEADINGS_FOR_LLM", 200)
STRUCTURE_MAX_SECTION_SIZE_CHARS: int = _get_int("STRUCTURE_MAX_SECTION_SIZE_CHARS", 200000)
STRUCTURAL_CHUNKER_ENABLED: bool = _get_bool("STRUCTURAL_CHUNKER_ENABLED", True)
STRUCTURAL_CHUNKER_TARGET_SIZE: int = _get_int("STRUCTURAL_CHUNKER_TARGET_SIZE", 14000)
STRUCTURAL_CHUNKER_MIN_SIZE: int = _get_int("STRUCTURAL_CHUNKER_MIN_SIZE", 3000)
STRUCTURAL_CHUNKER_SPLIT_WINDOW: int = _get_int("STRUCTURAL_CHUNKER_SPLIT_WINDOW", 450)
STRUCTURAL_CHUNKER_EXCLUDED_TYPES: set[str] = _get_csv_set(
    "STRUCTURAL_CHUNKER_EXCLUDED_TYPES",
    {"index", "bibliography"},
)
FRONT_MATTER_OUTLINE_ENABLED: bool = _get_bool("FRONT_MATTER_OUTLINE_ENABLED", False)
FRONT_MATTER_MAX_SECTIONS: int = _get_int("FRONT_MATTER_MAX_SECTIONS", 6)
FRONT_MATTER_MAX_CHARS: int = _get_int("FRONT_MATTER_MAX_CHARS", 12000)
FRONT_MATTER_INITIAL_EXCERPT_CHARS: int = _get_int("FRONT_MATTER_INITIAL_EXCERPT_CHARS", 6000)
KNOWLEDGE_EXTRACTION_ENABLED: bool = _get_bool("KNOWLEDGE_EXTRACTION_ENABLED", False)
KNOWLEDGE_PRECHECK_ENABLED: bool = _get_bool("KNOWLEDGE_PRECHECK_ENABLED", True)
KNOWLEDGE_PRECHECK_REVIEW_DEFAULT: str = os.getenv(
    "KNOWLEDGE_PRECHECK_REVIEW_DEFAULT",
    "extract",
).strip().lower()
KNOWLEDGE_PRECHECK_HARD_OCR_NOISE_RATIO: float = _get_float(
    "KNOWLEDGE_PRECHECK_HARD_OCR_NOISE_RATIO", 0.008
)
KNOWLEDGE_PRECHECK_HARD_FOOTNOTE_DENSITY: float = _get_float(
    "KNOWLEDGE_PRECHECK_HARD_FOOTNOTE_DENSITY", 0.30
)
KNOWLEDGE_PRECHECK_HARD_SHORT_LINE_RATIO: float = _get_float(
    "KNOWLEDGE_PRECHECK_HARD_SHORT_LINE_RATIO", 0.75
)
KNOWLEDGE_PRECHECK_NON_DOCTRINAL_SECTION_REF_NOISE_RATIO: float = _get_float(
    "KNOWLEDGE_PRECHECK_NON_DOCTRINAL_SECTION_REF_NOISE_RATIO", 0.55
)
KNOWLEDGE_PRECHECK_TYPE_CONFLICT_RATIO: float = _get_float(
    "KNOWLEDGE_PRECHECK_TYPE_CONFLICT_RATIO", 0.72
)
KNOWLEDGE_CLAMP_ENABLE: bool = _get_bool("KNOWLEDGE_CLAMP_ENABLE", True)
KNOWLEDGE_DECISION_POLICY_ENABLE: bool = _get_bool("KNOWLEDGE_DECISION_POLICY_ENABLE", True)
KNOWLEDGE_MIN_NON_GLOSSARIAL_DEFINITIONS_FOR_EXTRACT: int = _get_int(
    "KNOWLEDGE_MIN_NON_GLOSSARIAL_DEFINITIONS_FOR_EXTRACT", 2
)
KNOWLEDGE_NEAR_EMPTY_MAX_SEMANTIC_ITEMS: int = _get_int(
    "KNOWLEDGE_NEAR_EMPTY_MAX_SEMANTIC_ITEMS", 1
)
KNOWLEDGE_TERMINOLOGY_DOMINANT_MIN_TERMS: int = _get_int(
    "KNOWLEDGE_TERMINOLOGY_DOMINANT_MIN_TERMS", 3
)
KNOWLEDGE_TERMINOLOGY_DOMINANT_RATIO_THRESHOLD: float = _get_float(
    "KNOWLEDGE_TERMINOLOGY_DOMINANT_RATIO_THRESHOLD", 2.0
)
KNOWLEDGE_FILTER_EDITORIAL_ENABLE: bool = _get_bool("KNOWLEDGE_FILTER_EDITORIAL_ENABLE", True)
KNOWLEDGE_FILTER_GENERIC_DEFINITIONS_ENABLE: bool = _get_bool(
    "KNOWLEDGE_FILTER_GENERIC_DEFINITIONS_ENABLE", True
)
KNOWLEDGE_FILTER_MODERN_ENABLE: bool = _get_bool("KNOWLEDGE_FILTER_MODERN_ENABLE", True)
KNOWLEDGE_DEGRADED_WEAK_SUPPORT_CONCEPTS_MAX: int = _get_int(
    "KNOWLEDGE_DEGRADED_WEAK_SUPPORT_CONCEPTS_MAX", 2
)
KNOWLEDGE_DEGRADED_WEAK_SUPPORT_TERMINOLOGY_MAX: int = _get_int(
    "KNOWLEDGE_DEGRADED_WEAK_SUPPORT_TERMINOLOGY_MAX", 3
)
ONTOLOGY_ENABLE_INFERRED_TAXONOMY: bool = _get_bool("ONTOLOGY_ENABLE_INFERRED_TAXONOMY", False)
PIPELINE_VERSION: str = os.getenv("PIPELINE_VERSION", "booksmachine_0.9")
