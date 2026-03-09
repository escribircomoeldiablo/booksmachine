"""Post-processing utilities to clean DocumentMap sidecars for LLM consumption."""

from __future__ import annotations

import copy
import re

from .structure_pass import validate_document_map
from .structure_types import DocumentMap, SectionRecord

_INDEX_ENTRY_PATTERN = re.compile(
    r".+(?:\s|,)\d+(?:[-–]\d+)?(?:\s*,\s*\d+(?:[-–]\d+)?)*\.?$"
)


def _normalize_label(label: object) -> str:
    if not isinstance(label, str):
        return "unknown"
    compact = " ".join(label.split()).strip()
    return compact or "unknown"


def _is_letter_marker(section: SectionRecord) -> bool:
    label = _normalize_label(section.get("label"))
    return bool(re.fullmatch(r"[A-Z]", label))


def _looks_like_index_entry_label(label: str) -> bool:
    if len(label) <= 2:
        return False
    return bool(_INDEX_ENTRY_PATTERN.match(label))


def _merge_letter_markers(sections: list[SectionRecord]) -> list[SectionRecord]:
    merged: list[SectionRecord] = []
    for section in sections:
        if (
            _is_letter_marker(section)
            and section.get("type") == "unknown"
            and merged
            and merged[-1]["type"] == "unknown"
        ):
            # Keep coverage stable while removing low-value alphabet marker nodes.
            merged[-1]["end_char"] = section["end_char"]
            merged[-1]["end_page"] = section.get("end_page", merged[-1].get("end_page"))
            continue
        merged.append(section)

    promoted: list[SectionRecord] = []
    cursor = 0
    while cursor < len(merged):
        section = merged[cursor]
        if (
            _is_letter_marker(section)
            and section.get("type") == "unknown"
            and cursor + 1 < len(merged)
        ):
            nxt = merged[cursor + 1]
            if nxt.get("type") == "unknown" and _looks_like_index_entry_label(_normalize_label(nxt.get("label"))):
                nxt = copy.deepcopy(nxt)
                nxt["start_char"] = section["start_char"]
                if section.get("start_page") is not None:
                    nxt["start_page"] = section["start_page"]
                promoted.append(nxt)
                cursor += 2
                continue
        promoted.append(section)
        cursor += 1
    return promoted


def _fill_page_gaps(sections: list[SectionRecord]) -> None:
    for index, section in enumerate(sections):
        previous = sections[index - 1] if index > 0 else None
        nxt = sections[index + 1] if index + 1 < len(sections) else None

        if section.get("start_page") is None:
            if previous is not None and previous.get("end_page") is not None:
                section["start_page"] = previous["end_page"]
            elif nxt is not None and nxt.get("start_page") is not None:
                section["start_page"] = nxt["start_page"]

        if section.get("end_page") is None:
            if nxt is not None and nxt.get("start_page") is not None:
                section["end_page"] = nxt["start_page"]
            elif section.get("start_page") is not None:
                section["end_page"] = section["start_page"]
            elif previous is not None and previous.get("end_page") is not None:
                section["end_page"] = previous["end_page"]

        start_page = section.get("start_page")
        end_page = section.get("end_page")
        if isinstance(start_page, int) and isinstance(end_page, int) and end_page < start_page:
            section["end_page"] = start_page


def clean_document_map(document_map: DocumentMap, *, max_section_size_chars: int = 200000) -> DocumentMap:
    """Return a cleaned copy of DocumentMap with stricter section hygiene."""
    cleaned = copy.deepcopy(document_map)
    sections = cleaned["sections"]

    for section in sections:
        section["label"] = _normalize_label(section.get("label"))

    sections = sorted(sections, key=lambda item: item["start_char"])
    sections = _merge_letter_markers(sections)
    _fill_page_gaps(sections)

    for index, section in enumerate(sections):
        section["section_index"] = index
        section["id"] = f"section_{section['start_char']}"

    cleaned["sections"] = sections
    cleaned["stats"]["sections_generated"] = len(sections)
    cleaned["stats"]["unknown_sections"] = sum(1 for section in sections if section["type"] == "unknown")
    validate_document_map(cleaned, max_section_size_chars=max_section_size_chars)
    return cleaned


def clean_document_map_sidecar_payload(
    payload: dict[str, object],
    *,
    max_section_size_chars: int = 200000,
) -> dict[str, object]:
    cleaned_payload = copy.deepcopy(payload)
    document_map_obj = cleaned_payload.get("document_map")
    if not isinstance(document_map_obj, dict):
        raise ValueError("payload missing document_map object")
    cleaned_map = clean_document_map(document_map_obj, max_section_size_chars=max_section_size_chars)  # type: ignore[arg-type]
    cleaned_payload["document_map"] = cleaned_map
    metadata = cleaned_payload.get("metadata")
    if isinstance(metadata, dict):
        metadata["postprocess"] = "document_map_cleaner_v1"
    return cleaned_payload

