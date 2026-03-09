"""End-to-end book processing pipeline."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Callable

from .chunker import split_into_chunks
from .chunker_structural import build_structural_chunks
from .compiler import (
    build_block_output_path,
    build_chunk_output_path,
    build_output_path,
    compile_block_summaries,
    compile_chunk_summaries,
    compile_compendium,
)
from .config import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    OUTPUT_FOLDER,
    PIPELINE_VERSION,
    STRUCTURE_MAX_HEADINGS_FOR_LLM,
    STRUCTURE_MAX_SECTION_SIZE_CHARS,
    STRUCTURE_MIN_HEADING_SCORE,
    STRUCTURE_PASS_ENABLED,
    STRUCTURE_PASS_USE_LLM,
    STRUCTURAL_CHUNKER_ENABLED,
    STRUCTURAL_CHUNKER_MIN_SIZE,
    STRUCTURAL_CHUNKER_SPLIT_WINDOW,
    STRUCTURAL_CHUNKER_TARGET_SIZE,
)
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
DEFAULT_SMOKE_MAX_CHUNKS = 3
ProgressCallback = Callable[[str, str, dict[str, object]], None]


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
    chunking_mode = "legacy"
    chunking_target_size = CHUNK_SIZE
    chunking_min_size = 0
    chunking_split_window = 0
    structural_chunk_stats: dict[str, object] | None = None

    chunks: list[str]
    if (
        STRUCTURAL_CHUNKER_ENABLED
        and structure_enabled
        and structure_map is not None
        and structure_map.get("text_hash") == book_hash
    ):
        sections = structure_map.get("sections", [])
        if isinstance(sections, list) and len(sections) > 1:
            chunk_set = build_structural_chunks(
                text,
                structure_map,  # type: ignore[arg-type]
                target_size=STRUCTURAL_CHUNKER_TARGET_SIZE,
                min_size=STRUCTURAL_CHUNKER_MIN_SIZE,
                split_window=STRUCTURAL_CHUNKER_SPLIT_WINDOW,
            )
            chunks = [record["text"] for record in chunk_set["chunks"]]
            chunking_mode = "structural"
            chunking_target_size = STRUCTURAL_CHUNKER_TARGET_SIZE
            chunking_min_size = STRUCTURAL_CHUNKER_MIN_SIZE
            chunking_split_window = STRUCTURAL_CHUNKER_SPLIT_WINDOW
            structural_chunk_stats = dict(chunk_set["stats"])
        else:
            chunks = split_into_chunks(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)
    else:
        chunks = split_into_chunks(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)
    if not chunks:
        raise ValueError(f"No readable content found in: {source_path}")

    output_path = build_output_path(str(source_path), OUTPUT_FOLDER)
    chunk_output_path = build_chunk_output_path(str(source_path), OUTPUT_FOLDER)
    block_output_path = build_block_output_path(str(source_path), OUTPUT_FOLDER)
    total_chunks_detected = len(chunks)
    chunking_hash = _chunking_fingerprint(
        mode=chunking_mode,
        chunk_size=CHUNK_SIZE,
        overlap=CHUNK_OVERLAP,
        target_size=chunking_target_size,
        min_size=chunking_min_size,
        split_window=chunking_split_window,
    )
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
        if output_language == "es":
            chunk_summary = summarize_chunk(chunks[chunk_index - 1])
        else:
            chunk_summary = summarize_chunk(
                chunks[chunk_index - 1],
                output_language=output_language,
            )
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
            },
        )

    ordered_summaries = [summaries_by_index[index] for index in selected_indices]
    chunks_really_processed = len(ordered_summaries)
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
    if structure_enabled and structure_map is not None:
        sidecar_payload = build_document_map_sidecar_payload(
            structure_map,
            pipeline_version=PIPELINE_VERSION,
        )
        save_text(document_map_path, serialize_document_map_sidecar(sidecar_payload))

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
    if structure_enabled and structure_map is not None:
        _log(verbose, f"Document map output path: {document_map_path}")
    _emit_progress(
        progress_callback,
        "done",
        "Proceso completado",
        output_path=output_path,
        chunk_output_path=chunk_output_path,
        block_output_path=block_output_path,
        document_map_path=(document_map_path if structure_enabled and structure_map is not None else None),
        llm_calls_made=llm_calls_made,
    )

    return output_path
