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


OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")
MODEL_NAME: str = os.getenv("MODEL_NAME", "gpt-4.1-mini")
OPENAI_TIMEOUT_SECONDS: float = _get_float("OPENAI_TIMEOUT_SECONDS", 60.0)
OPENAI_MAX_RETRIES: int = _get_int("OPENAI_MAX_RETRIES", 6)
OPENAI_RETRY_BACKOFF_SECONDS: float = _get_float("OPENAI_RETRY_BACKOFF_SECONDS", 1.0)
CHUNK_SIZE: int = _get_int("CHUNK_SIZE", 1800)
CHUNK_OVERLAP: int = _get_int("CHUNK_OVERLAP", 200)
OUTPUT_FOLDER: str = os.getenv("OUTPUT_FOLDER", "outputs")
STRUCTURE_PASS_ENABLED: bool = _get_bool("STRUCTURE_PASS_ENABLED", False)
STRUCTURE_PASS_USE_LLM: bool = _get_bool("STRUCTURE_PASS_USE_LLM", True)
STRUCTURE_MIN_HEADING_SCORE: float = _get_float("STRUCTURE_MIN_HEADING_SCORE", 0.55)
STRUCTURE_MAX_HEADINGS_FOR_LLM: int = _get_int("STRUCTURE_MAX_HEADINGS_FOR_LLM", 200)
STRUCTURE_MAX_SECTION_SIZE_CHARS: int = _get_int("STRUCTURE_MAX_SECTION_SIZE_CHARS", 200000)
STRUCTURAL_CHUNKER_ENABLED: bool = _get_bool("STRUCTURAL_CHUNKER_ENABLED", False)
STRUCTURAL_CHUNKER_TARGET_SIZE: int = _get_int("STRUCTURAL_CHUNKER_TARGET_SIZE", 14000)
STRUCTURAL_CHUNKER_MIN_SIZE: int = _get_int("STRUCTURAL_CHUNKER_MIN_SIZE", 3000)
STRUCTURAL_CHUNKER_SPLIT_WINDOW: int = _get_int("STRUCTURAL_CHUNKER_SPLIT_WINDOW", 450)
PIPELINE_VERSION: str = os.getenv("PIPELINE_VERSION", "booksmachine_0.9")
