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


OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")
MODEL_NAME: str = os.getenv("MODEL_NAME", "gpt-4.1-mini")
CHUNK_SIZE: int = _get_int("CHUNK_SIZE", 1800)
CHUNK_OVERLAP: int = _get_int("CHUNK_OVERLAP", 200)
OUTPUT_FOLDER: str = os.getenv("OUTPUT_FOLDER", "outputs")
