"""Structure Pass orchestration: detect, classify, assemble, validate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .structure_classifier import classify_headings
from .structure_detector import detect_headings_and_segments
from .structure_types import (
    DocumentMap,
    DocumentMapStats,
    HeadingCandidate,
    PageUnit,
    PreSegment,
    SectionRecord,
)

DOCUMENT_MAP_VERSION = "1.0"
DOCUMENT_MAP_GENERATOR = "structure_pass_v1"
PIPELINE_VERSION_DEFAULT = "booksmachine_0.9"


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _page_for_offset(offset: int, page_units: list[PageUnit] | None) -> int | None:
    if not page_units:
        return None
    for unit in page_units:
        if unit["start_char"] <= offset < unit["end_char"]:
            return unit["page"]
    return None


def _section_id(start_char: int) -> str:
    return f"section_{start_char}"


def _section_from_segment(
    segment: PreSegment,
    *,
    heading: HeadingCandidate | None,
    label: str,
    section_type: str,
    confidence: float,
    page_units: list[PageUnit] | None,
) -> SectionRecord:
    start_char = segment["start_char"]
    end_char = segment["end_char"]
    start_page = _page_for_offset(start_char, page_units)
    end_page = _page_for_offset(max(start_char, end_char - 1), page_units)
    return SectionRecord(
        section_index=0,
        id=_section_id(start_char),
        label=label if label else "unknown",
        type=section_type if section_type else "unknown",
        start_page=start_page,
        end_page=end_page,
        start_char=start_char,
        end_char=end_char,
        confidence=float(min(1.0, max(0.0, confidence))),
    )


def _subdivide_large_sections(
    sections: list[SectionRecord],
    *,
    max_section_size_chars: int,
    page_units: list[PageUnit] | None,
) -> list[SectionRecord]:
    normalized: list[SectionRecord] = []
    max_size = max(1, max_section_size_chars)
    for section in sections:
        length = section["end_char"] - section["start_char"]
        if length <= max_size:
            normalized.append(section)
            continue

        start = section["start_char"]
        while start < section["end_char"]:
            end = min(start + max_size, section["end_char"])
            start_page = _page_for_offset(start, page_units)
            end_page = _page_for_offset(max(start, end - 1), page_units)
            normalized.append(
                SectionRecord(
                    section_index=0,
                    id=_section_id(start),
                    label=section["label"],
                    type=section["type"],
                    start_page=start_page,
                    end_page=end_page,
                    start_char=start,
                    end_char=end,
                    confidence=section["confidence"],
                )
            )
            start = end
    return normalized


def _normalize_sections(
    sections: list[SectionRecord],
    *,
    normalized_text_length: int,
    max_section_size_chars: int,
    page_units: list[PageUnit] | None,
) -> list[SectionRecord]:
    if normalized_text_length == 0:
        return []
    ordered = sorted(sections, key=lambda item: (item["start_char"], item["end_char"]))
    collapsed: list[SectionRecord] = []
    cursor = 0
    for section in ordered:
        start = max(section["start_char"], cursor)
        end = min(section["end_char"], normalized_text_length)
        if end <= start:
            continue
        if start > cursor:
            collapsed.append(
                SectionRecord(
                    section_index=0,
                    id=_section_id(cursor),
                    label="unknown",
                    type="unknown",
                    start_page=_page_for_offset(cursor, page_units),
                    end_page=_page_for_offset(start - 1, page_units),
                    start_char=cursor,
                    end_char=start,
                    confidence=0.0,
                )
            )
        collapsed.append(
            SectionRecord(
                section_index=0,
                id=_section_id(start),
                label=section["label"] or "unknown",
                type=section["type"],
                start_page=_page_for_offset(start, page_units),
                end_page=_page_for_offset(end - 1, page_units),
                start_char=start,
                end_char=end,
                confidence=section["confidence"],
            )
        )
        cursor = end

    if cursor < normalized_text_length:
        collapsed.append(
            SectionRecord(
                section_index=0,
                id=_section_id(cursor),
                label="unknown",
                type="unknown",
                start_page=_page_for_offset(cursor, page_units),
                end_page=_page_for_offset(normalized_text_length - 1, page_units),
                start_char=cursor,
                end_char=normalized_text_length,
                confidence=0.0,
            )
        )

    stabilized = _subdivide_large_sections(
        collapsed,
        max_section_size_chars=max_section_size_chars,
        page_units=page_units,
    )
    stabilized.sort(key=lambda item: item["start_char"])
    for idx, section in enumerate(stabilized):
        section["section_index"] = idx
        section["id"] = _section_id(section["start_char"])
    return stabilized


def validate_document_map(
    document_map: DocumentMap,
    *,
    max_section_size_chars: int,
    expected_text_hash: str | None = None,
) -> None:
    text_len = document_map["normalized_text_length"]
    if text_len < 0:
        raise ValueError("normalized_text_length must be >= 0")
    if expected_text_hash is not None and document_map["text_hash"] != expected_text_hash:
        raise ValueError("document_map text_hash mismatch")

    headings = document_map["headings"]
    seen_heading_indexes: set[int] = set()
    for heading in headings:
        index = heading["index"]
        if index in seen_heading_indexes:
            raise ValueError("duplicate heading index")
        seen_heading_indexes.add(index)
        if heading["start_char"] < 0 or heading["end_char"] > text_len or heading["end_char"] <= heading["start_char"]:
            raise ValueError("invalid heading offsets")
        if heading["score"] < 0.0 or heading["score"] > 1.0:
            raise ValueError("invalid heading score")

    sections = document_map["sections"]
    if text_len > 0 and not sections:
        raise ValueError("sections cannot be empty when text is non-empty")
    if sections:
        sorted_sections = sorted(sections, key=lambda item: item["start_char"])
        for expected_idx, section in enumerate(sorted_sections):
            if section["section_index"] != expected_idx:
                raise ValueError("non-contiguous section_index")
            if section["id"] != _section_id(section["start_char"]):
                raise ValueError("invalid section id")
            if not section["label"]:
                raise ValueError("empty section label")
            if section["end_char"] <= section["start_char"]:
                raise ValueError("invalid section range")
            if section["start_char"] < 0 or section["end_char"] > text_len:
                raise ValueError("section range out of bounds")
            if section["end_char"] - section["start_char"] > max_section_size_chars:
                raise ValueError("section exceeds max size")
            if expected_idx > 0 and sorted_sections[expected_idx - 1]["end_char"] != section["start_char"]:
                raise ValueError("section coverage gap or overlap")
        if sorted_sections[0]["start_char"] != 0 or sorted_sections[-1]["end_char"] != text_len:
            raise ValueError("section coverage incomplete")


def build_document_map(
    normalized_text: str,
    *,
    source_fingerprint: str,
    page_units: list[PageUnit] | None = None,
    use_llm: bool = True,
    min_heading_score: float = 0.55,
    max_headings_for_llm: int = 200,
    max_section_size_chars: int = 200000,
) -> DocumentMap:
    """Build the final versioned DocumentMap for a normalized input text."""
    text_hash = _sha256_text(normalized_text)
    headings, segments = detect_headings_and_segments(
        normalized_text,
        page_units=page_units,
        min_heading_score=min_heading_score,
    )
    heading_by_index = {item["index"]: item for item in headings}
    classified_by_index, selected_indexes = classify_headings(
        headings,
        max_headings_for_llm=max_headings_for_llm,
        use_llm=use_llm,
    )

    base_sections: list[SectionRecord] = []
    for segment in segments:
        heading_index = segment["heading_index"]
        if heading_index is None:
            base_sections.append(
                _section_from_segment(
                    segment,
                    heading=None,
                    label="unknown",
                    section_type="unknown",
                    confidence=0.0,
                    page_units=page_units,
                )
            )
            continue
        heading = heading_by_index.get(heading_index)
        if heading is None:
            continue
        classification = classified_by_index.get(heading_index)
        if classification is None:
            if heading_index in selected_indexes:
                section_type = "unknown"
                confidence = 0.0
            else:
                section_type = "unknown"
                confidence = 0.0
        else:
            section_type = classification["type"]
            confidence = classification["confidence"]
        base_sections.append(
            _section_from_segment(
                segment,
                heading=heading,
                label=heading["text"],
                section_type=section_type,
                confidence=confidence,
                page_units=page_units,
            )
        )

    sections = _normalize_sections(
        base_sections,
        normalized_text_length=len(normalized_text),
        max_section_size_chars=max_section_size_chars,
        page_units=page_units,
    )
    stats = DocumentMapStats(
        heading_candidates=len(headings),
        classified_headings=len(classified_by_index),
        sections_generated=len(sections),
        unknown_sections=sum(1 for item in sections if item["type"] == "unknown"),
    )
    document_map = DocumentMap(
        version=DOCUMENT_MAP_VERSION,
        generator=DOCUMENT_MAP_GENERATOR,
        text_hash=text_hash,
        source_fingerprint=source_fingerprint,
        normalized_text_length=len(normalized_text),
        sections=sections,
        headings=headings,
        stats=stats,
    )
    validate_document_map(
        document_map,
        max_section_size_chars=max_section_size_chars,
        expected_text_hash=text_hash,
    )
    return document_map


def build_document_map_sidecar_payload(
    document_map: DocumentMap,
    *,
    pipeline_version: str = PIPELINE_VERSION_DEFAULT,
) -> dict[str, object]:
    return {
        "metadata": {
            "pipeline_version": pipeline_version,
            "structure_version": document_map["version"],
            "generator": document_map["generator"],
        },
        "document_map": document_map,
    }


def build_document_map_output_path(input_path: str, output_folder: str) -> str:
    source_path = Path(input_path)
    return str(Path(output_folder) / f"{source_path.stem}_document_map.json")


def serialize_document_map_sidecar(payload: dict[str, object]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True)
