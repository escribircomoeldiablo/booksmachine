"""General file system utility functions."""

from __future__ import annotations

from pathlib import Path


def ensure_dir(path: str) -> None:
    """Create a directory if it does not already exist."""
    Path(path).mkdir(parents=True, exist_ok=True)


def read_text(path: str) -> str:
    """Read and return UTF-8 text from a file path."""
    return Path(path).read_text(encoding="utf-8")


def save_text(path: str, content: str) -> None:
    """Write UTF-8 text to a file, creating parent directories when needed."""
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")
