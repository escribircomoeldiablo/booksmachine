"""Summary compilation helpers."""

from __future__ import annotations

from pathlib import Path


def compile_chunk_summaries(summaries: list[str]) -> str:
    """Compile ordered chunk summaries into the historical chunk artifact."""
    chunks: list[str] = []
    for index, summary in enumerate(summaries, start=1):
        chunks.append(f"## Chunk {index}\n{summary}")
    return "\n\n---\n\n".join(chunks)


def compile_block_summaries(block_records: list[dict[str, object]]) -> str:
    """Compile ordered block summaries with traceability metadata."""
    blocks: list[str] = []
    for record in block_records:
        block_index = record["block_index"]
        chunk_start = record["chunk_start"]
        chunk_end = record["chunk_end"]
        summary_text = record["summary_text"]
        blocks.append(f"## Block {block_index} (Chunks {chunk_start}-{chunk_end})\n{summary_text}")
    return "\n\n---\n\n".join(blocks)


def compile_compendium(compendium_text: str) -> str:
    """Return the final compendium artifact text."""
    return compendium_text


def build_output_path(input_path: str, output_folder: str) -> str:
    """Build the final compendium output path."""
    source_path = Path(input_path)
    return str(Path(output_folder) / f"{source_path.stem}_summary.txt")


def build_chunk_output_path(input_path: str, output_folder: str) -> str:
    """Build the chunk-summary artifact output path."""
    source_path = Path(input_path)
    return str(Path(output_folder) / f"{source_path.stem}_summary_chunks.txt")


def build_block_output_path(input_path: str, output_folder: str) -> str:
    """Build the block-summary artifact output path."""
    source_path = Path(input_path)
    return str(Path(output_folder) / f"{source_path.stem}_summary_blocks.txt")


def build_knowledge_chunks_output_path(input_path: str, output_folder: str) -> str:
    """Build the chunk-level knowledge JSONL artifact output path."""
    source_path = Path(input_path)
    return str(Path(output_folder) / f"{source_path.stem}_knowledge_chunks.jsonl")


def build_knowledge_audit_output_path(input_path: str, output_folder: str) -> str:
    """Build the chunk-level knowledge audit sidecar JSONL output path."""
    source_path = Path(input_path)
    return str(Path(output_folder) / f"{source_path.stem}_knowledge_audit.jsonl")


def build_front_matter_outline_output_path(input_path: str, output_folder: str) -> str:
    """Build the front matter outline artifact output path."""
    source_path = Path(input_path)
    return str(Path(output_folder) / f"{source_path.stem}_front_matter_outline.json")
