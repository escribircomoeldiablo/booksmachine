"""Section-aware chunking based on DocumentMap ranges."""

from __future__ import annotations

from .chunk_types import ChunkRecord, ChunkSet, ChunkStats
from .structure_types import DocumentMap, SectionRecord

SENTENCE_MARKERS = (". ", "? ", "! ")


def _validate(target_size: int, min_size: int, split_window: int) -> None:
    if target_size <= 0:
        raise ValueError("target_size must be greater than 0")
    if min_size < 0:
        raise ValueError("min_size must be 0 or greater")
    if split_window <= 0:
        raise ValueError("split_window must be greater than 0")
    if min_size > target_size:
        raise ValueError("min_size must be smaller than or equal to target_size")


def _find_backward_split(text: str, start: int, target_end: int, split_window: int) -> int:
    search_start = max(start, target_end - split_window)
    window = text[search_start:target_end]
    if not window:
        return target_end

    idx = window.rfind("\n\n")
    if idx >= 0:
        return search_start + idx + 2

    best_sentence = -1
    for marker in SENTENCE_MARKERS:
        local = window.rfind(marker)
        if local > best_sentence:
            best_sentence = local
    if best_sentence >= 0:
        return search_start + best_sentence + 2

    space = window.rfind(" ")
    if space >= 0:
        return search_start + space + 1
    return target_end


def _split_section_ranges(
    text: str,
    section: SectionRecord,
    *,
    target_size: int,
    min_size: int,
    split_window: int,
) -> tuple[list[tuple[int, int]], int]:
    section_start = section["start_char"]
    section_end = section["end_char"]
    if section_end <= section_start:
        return ([], 0)

    ranges: list[tuple[int, int]] = []
    start = section_start
    while start < section_end:
        remaining = section_end - start
        if remaining <= target_size:
            end = section_end
        else:
            target_end = start + target_size
            end = _find_backward_split(text, start, target_end, split_window)
            if end <= start:
                end = target_end
        ranges.append((start, end))
        start = end

    merges = 0
    if len(ranges) > 1:
        last_start, last_end = ranges[-1]
        prev_start, prev_end = ranges[-2]
        last_len = last_end - last_start
        prev_len = prev_end - prev_start
        if last_len < min_size and prev_len + last_len <= target_size:
            ranges[-2] = (prev_start, last_end)
            ranges.pop()
            merges = 1
    return (ranges, merges)


def _build_record(text: str, section: SectionRecord, start: int, end: int) -> ChunkRecord:
    return ChunkRecord(
        chunk_index=-1,
        chunk_id="",
        section_id=section["id"],
        section_index=section["section_index"],
        start_char=start,
        end_char=end,
        start_page=section["start_page"],
        end_page=section["end_page"],
        text=text[start:end].strip(),
    )


def build_structural_chunks(
    normalized_text: str,
    document_map: DocumentMap,
    *,
    target_size: int = 14000,
    min_size: int = 3000,
    split_window: int = 450,
    excluded_section_types: set[str] | None = None,
) -> ChunkSet:
    """Build deterministic chunks constrained to DocumentMap sections."""
    _validate(target_size, min_size, split_window)
    excluded = excluded_section_types or set()

    chunks: list[ChunkRecord] = []
    sections_consumed = 0
    sections_split = 0
    sections_merged = 0

    ordered_sections = sorted(
        document_map["sections"],
        key=lambda item: (item["start_char"], item["end_char"]),
    )
    for section in ordered_sections:
        if section["type"] in excluded:
            continue
        section_text = normalized_text[section["start_char"] : section["end_char"]].strip()
        if not section_text:
            continue

        sections_consumed += 1
        ranges, merges = _split_section_ranges(
            normalized_text,
            section,
            target_size=target_size,
            min_size=min_size,
            split_window=split_window,
        )
        if len(ranges) > 1:
            sections_split += 1
        sections_merged += merges
        for start, end in ranges:
            if end <= start:
                continue
            record = _build_record(normalized_text, section, start, end)
            if record["text"]:
                chunks.append(record)

    chunks.sort(key=lambda item: (item["start_char"], item["end_char"]))
    for idx, chunk in enumerate(chunks):
        chunk["chunk_index"] = idx
        chunk["chunk_id"] = f"chunk_{idx}_{chunk['start_char']}_{chunk['end_char']}"

    total_chars = sum(chunk["end_char"] - chunk["start_char"] for chunk in chunks)
    stats = ChunkStats(
        total_chunks=len(chunks),
        avg_chunk_size=(float(total_chars) / len(chunks) if chunks else 0.0),
        sections_consumed=sections_consumed,
        sections_split=sections_split,
        sections_merged=sections_merged,
    )
    return ChunkSet(chunks=chunks, stats=stats)
