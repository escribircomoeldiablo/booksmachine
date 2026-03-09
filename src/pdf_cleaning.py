"""Deterministic and conservative PDF text cleaning."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from .document_types import PdfPageClean, PdfPageRaw

RULE_VERSION = "pdf-cleaning-v1"
LETTER_CLASS = "A-Za-zÀ-ÖØ-öø-ÿ"
SENTENCE_BOUNDARY_PATTERN = re.compile(r"[\.!\?;:]$")
LOWER_CONTINUATION_PATTERN = re.compile(r"^[a-zà-öø-ÿ0-9\(\[\{\"'“‘]")
SINGLE_PAGE_NUMBER_PATTERN = re.compile(r"^\d{1,4}$")
MULTI_SPACE_PATTERN = re.compile(r"[ \t\f\v]+")
DIGIT_PATTERN = re.compile(r"\d+")


@dataclass(slots=True)
class _LineRecord:
    value: str
    source_break_before: bool = False


@dataclass(slots=True)
class _RemovalSets:
    top: set[str]
    bottom: set[str]


def _normalize_line_endings(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _normalize_horizontal_whitespace(text: str) -> str:
    lines: list[str] = []
    for line in text.split("\n"):
        compact = MULTI_SPACE_PATTERN.sub(" ", line).rstrip()
        lines.append(compact)
    return "\n".join(lines)


def _preserve_paragraph_boundaries(text: str) -> str:
    # Keep explicit blank-line boundaries while reducing extraction noise.
    return re.sub(r"\n{3,}", "\n\n", text)


def _dehyphenate_wrapped_words(text: str) -> tuple[str, int]:
    pattern = re.compile(rf"([{LETTER_CLASS}])-\s*\n\s*([{LETTER_CLASS}])")
    return pattern.subn(r"\1\2", text)


def _should_merge(prev: str, curr: str) -> bool:
    if not prev or not curr:
        return False
    if SENTENCE_BOUNDARY_PATTERN.search(prev):
        return False

    curr_stripped = curr.lstrip()
    if not curr_stripped:
        return False

    return bool(LOWER_CONTINUATION_PATTERN.match(curr_stripped))


def _merge_intra_paragraph_lines(text: str) -> tuple[list[str], int]:
    paragraphs = text.split("\n\n")
    merged_paragraphs: list[str] = []
    merge_count = 0

    for paragraph in paragraphs:
        source_lines = [line.strip() for line in paragraph.split("\n") if line.strip()]
        if not source_lines:
            merged_paragraphs.append("")
            continue

        merged: list[str] = [source_lines[0]]
        for line in source_lines[1:]:
            prev = merged[-1]
            if _should_merge(prev, line):
                merged[-1] = f"{prev} {line.lstrip()}".strip()
                merge_count += 1
            else:
                merged.append(line)

        merged_paragraphs.append("\n".join(merged))

    merged_text = "\n\n".join(merged_paragraphs)
    merged_text = re.sub(r"\n{3,}", "\n\n", merged_text)
    return merged_text.split("\n"), merge_count


def _canonicalize_zone_line(line: str) -> str:
    compact = MULTI_SPACE_PATTERN.sub(" ", line.strip().lower())
    compact = DIGIT_PATTERN.sub("<num>", compact)
    return compact


def _collect_non_empty_zone_lines(lines: Iterable[str], limit: int) -> tuple[list[str], list[str]]:
    non_empty = [line for line in lines if line.strip()]
    return non_empty[:limit], non_empty[-limit:] if limit > 0 else []


def _detect_zone_repetitions(clean_pages: list[PdfPageClean], *, zone_depth: int = 3) -> _RemovalSets:
    min_repeats = 5
    top_counts: dict[str, int] = {}
    bottom_counts: dict[str, int] = {}

    for page in clean_pages:
        top_lines, bottom_lines = _collect_non_empty_zone_lines(page.clean_lines, zone_depth)

        seen_top: set[str] = set()
        for line in top_lines:
            key = _canonicalize_zone_line(line)
            if key:
                seen_top.add(key)

        seen_bottom: set[str] = set()
        for line in bottom_lines:
            key = _canonicalize_zone_line(line)
            if key:
                seen_bottom.add(key)

        for key in seen_top:
            top_counts[key] = top_counts.get(key, 0) + 1
        for key in seen_bottom:
            bottom_counts[key] = bottom_counts.get(key, 0) + 1

    top_remove: set[str] = set()
    bottom_remove: set[str] = set()
    for key, top_count in top_counts.items():
        bottom_count = bottom_counts.get(key, 0)
        if top_count >= min_repeats and top_count > bottom_count:
            top_remove.add(key)

    for key, bottom_count in bottom_counts.items():
        top_count = top_counts.get(key, 0)
        if bottom_count >= min_repeats and bottom_count > top_count:
            bottom_remove.add(key)

    return _RemovalSets(top=top_remove, bottom=bottom_remove)


def _remove_headers_and_footers(
    clean_pages: list[PdfPageClean],
    removal_sets: _RemovalSets,
    *,
    zone_depth: int = 3,
) -> None:
    for page in clean_pages:
        non_empty_indices = [idx for idx, line in enumerate(page.clean_lines) if line.strip()]
        if not non_empty_indices:
            continue

        top_zone = set(non_empty_indices[:zone_depth])
        bottom_zone = set(non_empty_indices[-zone_depth:])
        retained: list[str] = []

        for idx, line in enumerate(page.clean_lines):
            key = _canonicalize_zone_line(line)
            removed = False

            if idx in top_zone and key in removal_sets.top:
                page.removed_header_lines += 1
                removed = True
            elif idx in bottom_zone and key in removal_sets.bottom:
                page.removed_footer_lines += 1
                removed = True

            if not removed:
                retained.append(line)

        page.clean_lines = retained


def _remove_page_numbers(clean_pages: list[PdfPageClean]) -> None:
    for page in clean_pages:
        retained: list[str] = []
        for line in page.clean_lines:
            stripped = line.strip()
            if SINGLE_PAGE_NUMBER_PATTERN.fullmatch(stripped):
                page.removed_page_numbers += 1
                continue
            retained.append(line)
        page.clean_lines = retained


def _rebuild_page_text(clean_pages: list[PdfPageClean]) -> None:
    for page in clean_pages:
        text = "\n".join(page.clean_lines)
        text = re.sub(r"\n{3,}", "\n\n", text)
        page.clean_text = text.strip()
        page.clean_lines = page.clean_text.split("\n") if page.clean_text else []


def clean_pdf_pages(raw_pages: list[PdfPageRaw]) -> list[PdfPageClean]:
    """Clean PDF pages with deterministic rule ordering."""
    clean_pages: list[PdfPageClean] = []

    for page in raw_pages:
        # 1) Normalize line endings.
        text = _normalize_line_endings(page.raw_text)
        # 2) Normalize horizontal whitespace.
        text = _normalize_horizontal_whitespace(text)
        # 3) Preserve paragraph boundaries.
        text = _preserve_paragraph_boundaries(text)
        # 4) Dehyphenate wrapped words.
        text, dehyphenation_count = _dehyphenate_wrapped_words(text)
        # 5) Guarded intra-paragraph line merging.
        merged_lines, line_merge_count = _merge_intra_paragraph_lines(text)

        clean_pages.append(
            PdfPageClean(
                page_index=page.page_index,
                clean_text="",
                clean_lines=merged_lines,
                dehyphenation_count=dehyphenation_count,
                line_merge_count=line_merge_count,
            )
        )

    # 6) Header/footer detection (two-pass).
    removal_sets = _detect_zone_repetitions(clean_pages)
    _remove_headers_and_footers(clean_pages, removal_sets)
    # 7) Page-number removal.
    _remove_page_numbers(clean_pages)
    # 8) Rebuild page text preserving paragraph separators.
    _rebuild_page_text(clean_pages)

    return clean_pages


def assemble_clean_text(clean_pages: list[PdfPageClean]) -> str:
    """Assemble ordered pages into a single chunker-ready string."""
    pieces = [page.clean_text.strip() for page in clean_pages if page.clean_text.strip()]
    text = "\n\n".join(pieces)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
