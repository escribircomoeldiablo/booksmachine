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


OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")
MODEL_NAME: str = os.getenv("MODEL_NAME", "gpt-4.1-mini")
OPENAI_TIMEOUT_SECONDS: float = _get_float("OPENAI_TIMEOUT_SECONDS", 60.0)
OPENAI_MAX_RETRIES: int = _get_int("OPENAI_MAX_RETRIES", 6)
OPENAI_RETRY_BACKOFF_SECONDS: float = _get_float("OPENAI_RETRY_BACKOFF_SECONDS", 1.0)
CHUNK_SIZE: int = _get_int("CHUNK_SIZE", 1800)
CHUNK_OVERLAP: int = _get_int("CHUNK_OVERLAP", 200)
OUTPUT_FOLDER: str = os.getenv("OUTPUT_FOLDER", "outputs")
