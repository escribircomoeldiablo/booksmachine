"""Diagnostics and usability checks for PDF extraction."""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from pathlib import Path

from .document_types import ExtractionDiagnostics, PdfPageClean, PdfPageRaw
from .pdf_cleaning import RULE_VERSION

ALPHA_PATTERN = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]")


def analyze_extraction(raw_pages: list[PdfPageRaw], clean_pages: list[PdfPageClean]) -> ExtractionDiagnostics:
    """Build extraction diagnostics and usability decision."""
    page_count = len(raw_pages)
    empty_page_count = sum(1 for page in clean_pages if not page.clean_text.strip())
    raw_char_count = sum(len(page.raw_text) for page in raw_pages)
    clean_char_count = sum(len(page.clean_text) for page in clean_pages)

    dehyphenation_count = sum(page.dehyphenation_count for page in clean_pages)
    line_merge_count = sum(page.line_merge_count for page in clean_pages)
    removed_header_lines = sum(page.removed_header_lines for page in clean_pages)
    removed_footer_lines = sum(page.removed_footer_lines for page in clean_pages)
    removed_page_numbers = sum(page.removed_page_numbers for page in clean_pages)

    alpha_chars = len(ALPHA_PATTERN.findall("".join(page.clean_text for page in clean_pages)))
    alpha_density = (alpha_chars / clean_char_count) if clean_char_count else 0.0
    empty_page_ratio = (empty_page_count / page_count) if page_count else 1.0

    reason: str | None = None
    if clean_char_count < 20:
        reason = "clean_char_count below minimum threshold"
    elif empty_page_ratio > 0.98:
        reason = "empty_page_ratio above maximum threshold"
    elif alpha_density < 0.05:
        reason = "alpha_density below minimum threshold"

    return ExtractionDiagnostics(
        page_count=page_count,
        empty_page_count=empty_page_count,
        raw_char_count=raw_char_count,
        clean_char_count=clean_char_count,
        dehyphenation_count=dehyphenation_count,
        line_merge_count=line_merge_count,
        removed_header_lines=removed_header_lines,
        removed_footer_lines=removed_footer_lines,
        removed_page_numbers=removed_page_numbers,
        alpha_density=alpha_density,
        is_usable=reason is None,
        unusable_reason=reason,
        rule_version=RULE_VERSION,
    )


def write_extraction_report(diagnostics: ExtractionDiagnostics, output_path: Path) -> None:
    """Write diagnostics report JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(diagnostics), indent=2, sort_keys=True), encoding="utf-8")
