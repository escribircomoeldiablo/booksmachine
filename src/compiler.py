"""Summary compilation helpers."""

from __future__ import annotations

from pathlib import Path


def compile_chunk_summaries(summaries: list[str]) -> str:
    """Compile ordered chunk summaries into the final markdown-like output."""
    chunks: list[str] = []
    for index, summary in enumerate(summaries, start=1):
        chunks.append(f"## Chunk {index}\n{summary}")
    return "\n\n---\n\n".join(chunks)


def build_output_path(input_path: str, output_folder: str) -> str:
    """Build the output path keeping current naming and directory semantics."""
    source_path = Path(input_path)
    return str(Path(output_folder) / f"{source_path.stem}_summary.txt")
