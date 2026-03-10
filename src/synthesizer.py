"""Multi-level synthesis helpers for block and global compendium stages."""

from __future__ import annotations

import math
from typing import Callable, TypedDict

from .ai_client import ask_llm

BLOCK_SIZE = 8


def _block_output_style(output_language: str) -> str:
    if output_language == "original":
        return (
            "Devuelve una sintesis estructurada y concisa en el idioma original dominante de "
            "los resumenes. Evita traducir terminos salvo necesidad de claridad."
        )
    return (
        "Devuelve una sintesis estructurada y concisa en espanol, con encabezados claros y "
        "puntos. Evita repetir ideas equivalentes. Conserva sin traducir palabras en latin "
        "y terminos que deban mantenerse en su idioma original por contexto. No colapses "
        "multiples pasos estructurados en un solo parrafo ni mezcles variantes de autores."
    )


def _compendium_output_style(output_language: str) -> str:
    if output_language == "original":
        return (
            "Devuelve un compendio global coherente en el idioma original dominante de los "
            "resumenes, con jerarquia clara y sin redundancia. Usa solo informacion presente "
            "en los resumenes de bloques."
        )
    return (
        "Devuelve un compendio global coherente en espanol, con jerarquia clara y sin "
        "redundancia. Usa solo informacion presente en los resumenes de bloques. Conserva "
        "sin traducir palabras en latin y terminos que deban mantenerse en su idioma original "
        "por contexto. Conserva pasos, reglas de decision, precondiciones, excepciones y "
        "variantes por autor como secciones separadas; no las reduzcas a prosa libre."
    )


class ChunkSummaryRecord(TypedDict):
    chunk_index: int
    summary_text: str


class BlockSummaryRecord(TypedDict):
    block_index: int
    chunk_start: int
    chunk_end: int
    chunk_indices: list[int]
    summary_text: str


BlockProgressCallback = Callable[[int, int], None]


def expected_synthesis_calls(chunk_count: int, *, block_size: int = BLOCK_SIZE) -> int:
    """Return expected LLM calls for level-2 synthesis."""
    if chunk_count <= 0:
        return 0
    blocks = math.ceil(chunk_count / block_size)
    return blocks + (1 if blocks > 1 else 0)


def make_chunk_summary_records(summaries: list[str]) -> list[ChunkSummaryRecord]:
    """Normalize ordered chunk summaries into stable records."""
    records: list[ChunkSummaryRecord] = []
    for index, summary in enumerate(summaries, start=1):
        if not summary.strip():
            raise RuntimeError(f"Chunk summary is empty for chunk {index}.")
        records.append({"chunk_index": index, "summary_text": summary})
    return records


def group_chunk_summary_records(
    chunk_records: list[ChunkSummaryRecord],
    *,
    block_size: int = BLOCK_SIZE,
) -> list[list[ChunkSummaryRecord]]:
    """Group chunk summary records into fixed-size blocks."""
    if block_size <= 0:
        raise ValueError("block_size must be greater than 0")
    return [
        chunk_records[start : start + block_size]
        for start in range(0, len(chunk_records), block_size)
    ]


def build_block_prompt(
    block_index: int,
    block_chunks: list[ChunkSummaryRecord],
    output_language: str = "es",
) -> str:
    """Build prompt for block synthesis from chunk summaries."""
    lines: list[str] = [
        "Eres un asistente de sintesis tecnica.",
        f"Sintetiza el Bloque {block_index} a partir de los siguientes resumenes de chunks.",
        _block_output_style(output_language),
        "Preserva secciones estructuradas de procedimiento. Si no hay base compartida suficiente, manten variantes separadas.",
        "",
        "Resumenes de chunks:",
    ]
    for record in block_chunks:
        lines.extend(
            [
                f"- Chunk {record['chunk_index']}:",
                str(record["summary_text"]),
            ]
        )
    return "\n".join(lines)


def synthesize_blocks(
    chunk_records: list[ChunkSummaryRecord],
    *,
    block_size: int = BLOCK_SIZE,
    output_language: str = "es",
    progress_callback: BlockProgressCallback | None = None,
) -> tuple[list[BlockSummaryRecord], int]:
    """Synthesize chunk summaries into block summaries."""
    grouped_blocks = group_chunk_summary_records(chunk_records, block_size=block_size)
    block_records: list[BlockSummaryRecord] = []
    llm_calls_made = 0

    total_blocks = len(grouped_blocks)
    for block_index, block_chunks in enumerate(grouped_blocks, start=1):
        if progress_callback is not None:
            progress_callback(block_index, total_blocks)
        prompt = build_block_prompt(
            block_index,
            block_chunks,
            output_language=output_language,
        )
        block_summary = ask_llm(prompt)
        llm_calls_made += 1
        chunk_indices = [record["chunk_index"] for record in block_chunks]
        block_records.append(
            {
                "block_index": block_index,
                "chunk_start": chunk_indices[0],
                "chunk_end": chunk_indices[-1],
                "chunk_indices": chunk_indices,
                "summary_text": block_summary,
            }
        )

    return block_records, llm_calls_made


def build_compendium_prompt(
    block_records: list[BlockSummaryRecord],
    output_language: str = "es",
) -> str:
    """Build prompt for final global compendium from block summaries."""
    lines: list[str] = [
        "Eres un asistente de sintesis tecnica.",
        "Crea el compendio global final a partir de estos resumenes de bloques.",
        _compendium_output_style(output_language),
        "No conviertas multiples pasos estructurados en un unico parrafo resumen.",
        "",
        "Resumenes de bloques:",
    ]
    for record in block_records:
        lines.extend(
            [
                (
                    f"- Block {record['block_index']} "
                    f"(Chunks {record['chunk_start']}-{record['chunk_end']}):"
                ),
                str(record["summary_text"]),
            ]
        )
    return "\n".join(lines)


def synthesize_compendium(
    block_records: list[BlockSummaryRecord],
    *,
    output_language: str = "es",
) -> tuple[str, int]:
    """Synthesize block summaries into the final compendium."""
    if not block_records:
        raise RuntimeError("Cannot synthesize compendium without block summaries.")
    if len(block_records) == 1:
        return str(block_records[0]["summary_text"]), 0
    prompt = build_compendium_prompt(block_records, output_language=output_language)
    return ask_llm(prompt), 1
