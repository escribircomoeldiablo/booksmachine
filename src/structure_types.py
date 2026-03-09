"""Typed records for structure pass detection, classification, and map assembly."""

from __future__ import annotations

from typing import Literal, TypedDict

SectionType = Literal[
    "front_matter",
    "chapter",
    "section",
    "appendix",
    "bibliography",
    "index",
    "unknown",
]


class PageUnit(TypedDict):
    page: int
    start_char: int
    end_char: int


class HeadingCandidate(TypedDict):
    index: int
    id: str
    text: str
    start_char: int
    end_char: int
    page: int | None
    score: float
    pattern: str | None


class PreSegment(TypedDict):
    heading_index: int | None
    start_char: int
    end_char: int


class SectionRecord(TypedDict):
    section_index: int
    id: str
    label: str
    type: SectionType
    start_page: int | None
    end_page: int | None
    start_char: int
    end_char: int
    confidence: float


class DocumentMapStats(TypedDict):
    heading_candidates: int
    classified_headings: int
    sections_generated: int
    unknown_sections: int


class DocumentMap(TypedDict):
    version: str
    generator: str
    text_hash: str
    source_fingerprint: str
    normalized_text_length: int
    sections: list[SectionRecord]
    headings: list[HeadingCandidate]
    stats: DocumentMapStats
