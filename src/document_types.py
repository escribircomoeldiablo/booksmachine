"""Typed records for PDF extraction, cleaning, and diagnostics."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class PdfPageRaw:
    page_index: int
    raw_text: str
    raw_lines: list[str]


@dataclass(slots=True)
class PdfPageClean:
    page_index: int
    clean_text: str
    clean_lines: list[str]
    dehyphenation_count: int = 0
    line_merge_count: int = 0
    removed_header_lines: int = 0
    removed_footer_lines: int = 0
    removed_page_numbers: int = 0


@dataclass(slots=True)
class ExtractionDiagnostics:
    page_count: int
    empty_page_count: int
    raw_char_count: int
    clean_char_count: int
    dehyphenation_count: int
    line_merge_count: int
    removed_header_lines: int
    removed_footer_lines: int
    removed_page_numbers: int
    alpha_density: float
    is_usable: bool
    unusable_reason: str | None
    rule_version: str


@dataclass(slots=True)
class BookDocument:
    source_path: str
    source_type: str
    clean_text: str
    pages_raw: list[PdfPageRaw] | None
    pages_clean: list[PdfPageClean] | None
    diagnostics: ExtractionDiagnostics | None
