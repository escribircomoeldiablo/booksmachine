"""Section-aware chunking with deterministic cross-section packing."""

from __future__ import annotations

from dataclasses import dataclass

from .chunk_types import ChunkRecord, ChunkSet, ChunkStats
from .structure_types import DocumentMap, SectionRecord

SENTENCE_MARKERS = (". ", "? ", "! ")
STRONG_TYPES = {"chapter", "appendix", "bibliography", "index"}


@dataclass(slots=True)
class _Atom:
    section_id: str
    section_index: int
    section_type: str
    start_char: int
    end_char: int
    start_page: int | None
    end_page: int | None
    is_weak: bool


@dataclass(slots=True)
class _PackedChunk:
    atoms: list[_Atom]

    @property
    def start_char(self) -> int:
        return self.atoms[0].start_char

    @property
    def end_char(self) -> int:
        return self.atoms[-1].end_char

    @property
    def length(self) -> int:
        return self.end_char - self.start_char


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


def _unknown_is_weak(
    section: SectionRecord,
    *,
    min_size: int,
    previous_section_type: str | None,
) -> bool:
    length = section["end_char"] - section["start_char"]
    if length > min_size:
        return False
    if previous_section_type == "chapter":
        return False
    return True


def _section_is_weak(
    section: SectionRecord,
    *,
    min_size: int,
    previous_section_type: str | None,
) -> bool:
    section_type = section["type"]
    if section_type in STRONG_TYPES:
        return False
    if section_type == "unknown":
        return _unknown_is_weak(
            section,
            min_size=min_size,
            previous_section_type=previous_section_type,
        )
    return True


def _build_atoms(
    normalized_text: str,
    document_map: DocumentMap,
    *,
    target_size: int,
    min_size: int,
    split_window: int,
    excluded_section_types: set[str],
) -> tuple[list[_Atom], int, int, int, int]:
    atoms: list[_Atom] = []
    sections_consumed = 0
    sections_split = 0
    sections_merged = 0
    weak_sections_total = 0

    ordered_sections = sorted(
        document_map["sections"],
        key=lambda item: (item["start_char"], item["end_char"]),
    )
    previous_kept_type: str | None = None

    for section in ordered_sections:
        section_type = section["type"]
        if section_type in excluded_section_types:
            continue
        section_text = normalized_text[section["start_char"] : section["end_char"]].strip()
        if not section_text:
            continue

        is_weak = _section_is_weak(
            section,
            min_size=min_size,
            previous_section_type=previous_kept_type,
        )
        if is_weak:
            weak_sections_total += 1

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
            text_piece = normalized_text[start:end].strip()
            if not text_piece:
                continue
            atoms.append(
                _Atom(
                    section_id=section["id"],
                    section_index=section["section_index"],
                    section_type=section_type,
                    start_char=start,
                    end_char=end,
                    start_page=section["start_page"],
                    end_page=section["end_page"],
                    is_weak=is_weak,
                )
            )

        previous_kept_type = section_type

    atoms.sort(key=lambda item: (item.start_char, item.end_char))
    return atoms, sections_consumed, sections_split, sections_merged, weak_sections_total


def _boundary_is_strong(left: _Atom, right: _Atom) -> bool:
    if left.section_id == right.section_id:
        return False
    return left.section_type in STRONG_TYPES or right.section_type in STRONG_TYPES


def _pack_atoms(
    atoms: list[_Atom],
    *,
    target_size: int,
    min_size: int,
    hard_max: int,
) -> list[_PackedChunk]:
    if not atoms:
        return []

    packed: list[_PackedChunk] = []
    current = _PackedChunk(atoms=[atoms[0]])

    for atom in atoms[1:]:
        left = current.atoms[-1]
        strong_boundary = _boundary_is_strong(left, atom)
        prospective = atom.end_char - current.start_char

        if strong_boundary:
            packed.append(current)
            current = _PackedChunk(atoms=[atom])
            continue

        if prospective <= target_size:
            current.atoms.append(atom)
            continue

        # Allow controlled overflow to avoid microchunks, but never above hard_max.
        if prospective <= hard_max:
            if current.length < min_size:
                current.atoms.append(atom)
                continue
            if atom.is_weak and atom.end_char - atom.start_char < min_size:
                current.atoms.append(atom)
                continue

        packed.append(current)
        current = _PackedChunk(atoms=[atom])

    packed.append(current)
    return packed


def _coalesce_small_chunks(
    packed: list[_PackedChunk],
    *,
    min_size: int,
    hard_max: int,
) -> list[_PackedChunk]:
    if not packed:
        return []

    i = 0
    result: list[_PackedChunk] = []
    while i < len(packed):
        current = packed[i]
        if current.length >= min_size or i == len(packed) - 1:
            result.append(current)
            i += 1
            continue

        nxt = packed[i + 1]
        left = current.atoms[-1]
        right = nxt.atoms[0]
        if _boundary_is_strong(left, right):
            # Never cross strong boundaries in rescue pass.
            result.append(current)
            i += 1
            continue

        merged_len = nxt.end_char - current.start_char
        if merged_len <= hard_max:
            result.append(_PackedChunk(atoms=current.atoms + nxt.atoms))
            i += 2
            continue

        result.append(current)
        i += 1

    return result


def _build_record(text: str, packed: _PackedChunk) -> ChunkRecord:
    first = packed.atoms[0]
    last = packed.atoms[-1]
    section_id = first.section_id if first.section_id == last.section_id else f"{first.section_id}__{last.section_id}"
    section_index = first.section_index
    return ChunkRecord(
        chunk_index=-1,
        chunk_id="",
        section_id=section_id,
        section_index=section_index,
        start_char=packed.start_char,
        end_char=packed.end_char,
        start_page=first.start_page,
        end_page=last.end_page,
        text=text[packed.start_char : packed.end_char].strip(),
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
    hard_max = int(target_size * 1.5)

    atoms, sections_consumed, sections_split, sections_merged, weak_sections_total = _build_atoms(
        normalized_text,
        document_map,
        target_size=target_size,
        min_size=min_size,
        split_window=split_window,
        excluded_section_types=excluded,
    )

    packed = _pack_atoms(
        atoms,
        target_size=target_size,
        min_size=min_size,
        hard_max=hard_max,
    )
    packed = _coalesce_small_chunks(
        packed,
        min_size=min_size,
        hard_max=hard_max,
    )

    chunks: list[ChunkRecord] = []
    weak_sections_absorbed = 0
    for packed_chunk in packed:
        record = _build_record(normalized_text, packed_chunk)
        if not record["text"]:
            continue
        chunk_section_ids = {atom.section_id for atom in packed_chunk.atoms}
        if len(chunk_section_ids) > 1:
            weak_sections_absorbed += len(
                {
                    atom.section_id
                    for atom in packed_chunk.atoms
                    if atom.is_weak
                }
            )
        chunks.append(record)

    chunks.sort(key=lambda item: (item["start_char"], item["end_char"]))
    for idx, chunk in enumerate(chunks):
        chunk["chunk_index"] = idx
        chunk["chunk_id"] = f"chunk_{idx}_{chunk['start_char']}_{chunk['end_char']}"

    total_chars = sum(chunk["end_char"] - chunk["start_char"] for chunk in chunks)
    avg_sections_per_chunk = float(len(atoms)) / len(chunks) if chunks else 0.0
    weak_sections_absorbed_ratio = (
        float(weak_sections_absorbed) / weak_sections_total
        if weak_sections_total > 0
        else 0.0
    )
    stats = ChunkStats(
        total_chunks=len(chunks),
        avg_chunk_size=(float(total_chars) / len(chunks) if chunks else 0.0),
        sections_consumed=sections_consumed,
        sections_split=sections_split,
        sections_merged=sections_merged,
        avg_sections_per_chunk=avg_sections_per_chunk,
        weak_sections_absorbed=weak_sections_absorbed,
        weak_sections_total=weak_sections_total,
        weak_sections_absorbed_ratio=weak_sections_absorbed_ratio,
        hard_max_chunk_size=hard_max,
    )
    return ChunkSet(chunks=chunks, stats=stats)
