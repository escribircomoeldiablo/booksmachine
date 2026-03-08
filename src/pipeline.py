"""End-to-end book processing pipeline."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .chunker import split_into_chunks
from .compiler import (
    build_block_output_path,
    build_chunk_output_path,
    build_output_path,
    compile_block_summaries,
    compile_chunk_summaries,
    compile_compendium,
)
from .config import CHUNK_OVERLAP, CHUNK_SIZE, OUTPUT_FOLDER
from .loader import load_book
from .summarizer import summarize_chunk
from .synthesizer import (
    expected_synthesis_calls,
    make_chunk_summary_records,
    synthesize_blocks,
    synthesize_compendium,
)
from .utils import ensure_dir, save_text

CHECKPOINT_DIR_NAME = ".checkpoints"
DEFAULT_SMOKE_MAX_CHUNKS = 3


def _relative_cost_scale(expected_calls: int) -> str:
    if expected_calls <= 3:
        return "low"
    if expected_calls <= 12:
        return "medium"
    return "high"


def _log(verbose: bool, message: str) -> None:
    if verbose:
        print(message)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _checkpoint_root(output_folder: str, book_hash: str, chunking_hash: str) -> Path:
    return Path(output_folder) / CHECKPOINT_DIR_NAME / book_hash / chunking_hash


def _chunk_checkpoint_path(root: Path, chunk_index: int) -> Path:
    return root / f"chunk_{chunk_index}.txt"


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


def _save_manifest(checkpoint_root: Path, payload: dict[str, object]) -> None:
    save_text(
        str(checkpoint_root / "manifest.json"),
        json.dumps(payload, indent=2, sort_keys=True),
    )


def process_book(
    path: str,
    *,
    mode: str = "full",
    max_chunks: int | None = None,
    dry_run: bool = False,
    verbose: bool = False,
    resume: bool = True,
) -> str:
    """Process a book file and save an aggregated technical summary."""
    if mode not in {"full", "smoke"}:
        raise ValueError("mode must be either 'full' or 'smoke'")
    if max_chunks is not None and max_chunks <= 0:
        raise ValueError("max_chunks must be greater than 0 when provided")

    source_path = Path(path)
    text = load_book(str(source_path))

    chunks = split_into_chunks(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)
    if not chunks:
        raise ValueError(f"No readable content found in: {source_path}")

    output_path = build_output_path(str(source_path), OUTPUT_FOLDER)
    chunk_output_path = build_chunk_output_path(str(source_path), OUTPUT_FOLDER)
    block_output_path = build_block_output_path(str(source_path), OUTPUT_FOLDER)
    total_chunks_detected = len(chunks)
    chunking_hash = _sha256_text(f"{CHUNK_SIZE}:{CHUNK_OVERLAP}")
    book_hash = _sha256_text(text)
    checkpoint_root = _checkpoint_root(OUTPUT_FOLDER, book_hash, chunking_hash)

    cached_summaries: dict[int, str] = {}
    if resume:
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
    _log(verbose, f"Dry run: {dry_run}")
    _log(verbose, f"Resume enabled: {resume}")
    _log(verbose, f"Total chunks detected: {total_chunks_detected}")
    _log(verbose, f"Chunks to process: {chunks_to_process}")
    _log(verbose, f"LLM calls expected (chunk layer): {chunk_llm_calls_expected}")
    _log(verbose, f"LLM calls expected (synthesis layer): {synthesis_llm_calls_expected}")
    _log(verbose, f"LLM calls expected: {llm_calls_expected}")
    _log(verbose, f"Estimated relative cost: {_relative_cost_scale(llm_calls_expected)}")

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
        return output_path

    chunk_llm_calls_made = 0
    summaries_by_index = dict(cached_summaries)
    for run_position, chunk_index in enumerate(planned_new_indices, start=1):
        _log(
            verbose,
            f"[Chunk {run_position}/{len(planned_new_indices)}] Summarizing source chunk {chunk_index}",
        )
        chunk_summary = summarize_chunk(chunks[chunk_index - 1])
        summaries_by_index[chunk_index] = chunk_summary
        chunk_llm_calls_made += 1

        if resume:
            ensure_dir(str(checkpoint_root))
            save_text(str(_chunk_checkpoint_path(checkpoint_root, chunk_index)), chunk_summary)

    if resume:
        ensure_dir(str(checkpoint_root))
        _save_manifest(
            checkpoint_root,
            {
                "input_path": str(source_path),
                "book_fingerprint": book_hash,
                "chunking_fingerprint": chunking_hash,
                "chunk_size": CHUNK_SIZE,
                "chunk_overlap": CHUNK_OVERLAP,
                "total_chunks_detected": total_chunks_detected,
            },
        )

    ordered_summaries = [summaries_by_index[index] for index in selected_indices]
    chunks_really_processed = len(ordered_summaries)
    chunk_summary_records = make_chunk_summary_records(ordered_summaries)
    block_summary_records, block_llm_calls = synthesize_blocks(chunk_summary_records)
    compendium_summary, compendium_llm_calls = synthesize_compendium(block_summary_records)
    synthesis_llm_calls_made = block_llm_calls + compendium_llm_calls
    llm_calls_made = chunk_llm_calls_made + synthesis_llm_calls_made

    chunk_summary_artifact = compile_chunk_summaries(ordered_summaries)
    block_summary_artifact = compile_block_summaries(block_summary_records)
    final_summary = compile_compendium(compendium_summary)

    ensure_dir(OUTPUT_FOLDER)
    save_text(chunk_output_path, chunk_summary_artifact)
    save_text(block_output_path, block_summary_artifact)
    save_text(output_path, final_summary)

    _log(verbose, "== Final Summary ==")
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

    return output_path
