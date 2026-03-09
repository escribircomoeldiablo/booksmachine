"""Deterministic heading detection and preliminary segmentation."""

from __future__ import annotations

import re

from .structure_types import HeadingCandidate, PageUnit, PreSegment

_ROMAN_PATTERN = r"(?:[IVXLCDM]+)"
_DECIMAL_PATTERN = r"(?:\d+(?:\.\d+)*)"
_HEADING_RULES: list[tuple[str, re.Pattern[str], float]] = [
    (
        "chapter_pattern",
        re.compile(r"^(?:chapter|capitulo|cap[íi]tulo)\s+.+$", re.IGNORECASE),
        0.95,
    ),
    ("part_pattern", re.compile(r"^(?:part)\s+.+$", re.IGNORECASE), 0.9),
    ("appendix_pattern", re.compile(r"^(?:appendix)\s+.+$", re.IGNORECASE), 0.9),
    (
        "bibliography_pattern",
        re.compile(r"^(?:bibliography|references|works cited)$", re.IGNORECASE),
        0.9,
    ),
    ("index_pattern", re.compile(r"^(?:index)$", re.IGNORECASE), 0.9),
    (
        "roman_numeral",
        re.compile(rf"^{_ROMAN_PATTERN}(?:[\.\):])?\s+[A-Za-z].+$"),
        0.8,
    ),
    (
        "decimal_numbering",
        re.compile(rf"^{_DECIMAL_PATTERN}(?:[\.\):])?\s+[A-Za-z].+$"),
        0.8,
    ),
]


def _line_to_page(start_char: int, page_units: list[PageUnit] | None) -> int | None:
    if not page_units:
        return None
    for page_unit in page_units:
        if page_unit["start_char"] <= start_char < page_unit["end_char"]:
            return page_unit["page"]
    return None


def _line_quality_score(line: str) -> float:
    letters = [char for char in line if char.isalpha()]
    if not letters:
        return 0.0
    uppercase = sum(1 for char in letters if char.isupper())
    ratio = uppercase / len(letters)
    if ratio >= 0.9:
        return 0.25
    if ratio >= 0.6:
        return 0.15
    return 0.05


def _score_for_line(line: str) -> tuple[float, str | None]:
    stripped = line.strip()
    if not stripped:
        return 0.0, None
    if len(stripped) > 120:
        return 0.0, None

    best_score = 0.0
    best_pattern: str | None = None
    for name, rule, base_score in _HEADING_RULES:
        if rule.match(stripped):
            score = min(1.0, base_score + _line_quality_score(stripped))
            if score > best_score:
                best_score = score
                best_pattern = name

    if best_pattern is None and len(stripped) <= 80 and stripped == stripped.title():
        best_score = 0.55 + _line_quality_score(stripped)
        best_pattern = "title_case_short"

    return min(best_score, 1.0), best_pattern


def detect_headings_and_segments(
    normalized_text: str,
    *,
    page_units: list[PageUnit] | None = None,
    min_heading_score: float = 0.55,
) -> tuple[list[HeadingCandidate], list[PreSegment]]:
    """Detect heading candidates and split text into preliminary macro-segments."""
    text = normalized_text
    if not text:
        return [], []

    headings: list[HeadingCandidate] = []
    cursor = 0
    next_index = 0
    for line in text.splitlines(keepends=True):
        raw = line.rstrip("\n")
        line_start = cursor
        line_end = cursor + len(raw)
        cursor += len(line)
        stripped = raw.strip()
        if not stripped:
            continue
        score, pattern = _score_for_line(stripped)
        if score < min_heading_score:
            continue
        headings.append(
            HeadingCandidate(
                index=next_index,
                id=f"heading_{next_index}",
                text=stripped,
                start_char=line_start,
                end_char=line_end,
                page=_line_to_page(line_start, page_units),
                score=round(score, 4),
                pattern=pattern,
            )
        )
        next_index += 1

    if not headings:
        return [], [PreSegment(heading_index=None, start_char=0, end_char=len(text))]

    segments: list[PreSegment] = []
    sorted_headings = sorted(headings, key=lambda item: item["start_char"])
    first_start = sorted_headings[0]["start_char"]
    if first_start > 0:
        segments.append(PreSegment(heading_index=None, start_char=0, end_char=first_start))

    for idx, heading in enumerate(sorted_headings):
        start = heading["start_char"]
        end = len(text) if idx == len(sorted_headings) - 1 else sorted_headings[idx + 1]["start_char"]
        if end > start:
            segments.append(
                PreSegment(
                    heading_index=heading["index"],
                    start_char=start,
                    end_char=end,
                )
            )

    return headings, segments
