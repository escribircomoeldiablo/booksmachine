"""Front matter extraction and strict outline generation."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .ai_client import ask_llm
from .front_matter_parser import parse_front_matter_outline_json
from .front_matter_schema import FrontMatterOutlineV1, FrontMatterSource, make_empty_front_matter_outline
from .structure_types import DocumentMap

_PROMPT_TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "prompts" / "front_matter_outline.txt"
_TOC_RE = re.compile(r"\b(contents|table of contents)\b", re.IGNORECASE)
_INTRO_RE = re.compile(r"\bintroduction\b", re.IGNORECASE)
_PREFACE_RE = re.compile(r"\b(preface|prologue)\b", re.IGNORECASE)


@dataclass(slots=True)
class FrontMatterExtractionInput:
    book_title: str
    source: FrontMatterSource
    prompt_sections: list[dict[str, str]]


@dataclass(slots=True)
class FrontMatterExtractionResult:
    record: FrontMatterOutlineV1
    parse_error: str | None
    used_fallback: bool


def _load_template() -> str:
    return _PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")


def _section_text(text: str, start_char: int, end_char: int) -> str:
    return text[start_char:end_char].strip()


def _normalize_excerpt(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.strip().splitlines()).strip()


def _signal_flags(label: str) -> tuple[bool, bool, bool]:
    lowered = label.strip().lower()
    return (
        bool(_TOC_RE.search(lowered)),
        bool(_INTRO_RE.search(lowered)),
        bool(_PREFACE_RE.search(lowered)),
    )


def collect_front_matter_input(
    *,
    text: str,
    document_map: DocumentMap | None,
    book_title: str,
    max_sections: int,
    max_chars: int,
    initial_excerpt_chars: int,
) -> FrontMatterExtractionInput:
    sections_payload: list[dict[str, str]] = []
    seen_ranges: set[tuple[int, int]] = set()
    has_toc = False
    has_introduction = False
    has_preface = False
    strategy_parts: list[str] = []
    remaining_chars = max(0, max_chars)
    early_sections = []
    headings = []
    if document_map is not None:
        early_sections = list(document_map.get("sections", []))[: max(1, max_sections * 2)]
        headings = list(document_map.get("headings", []))[: max(1, max_sections * 3)]

    def add_section(*, source_kind: str, label: str, excerpt: str, start_char: int, end_char: int) -> None:
        nonlocal remaining_chars, has_toc, has_introduction, has_preface
        if len(sections_payload) >= max_sections or remaining_chars <= 0:
            return
        normalized = _normalize_excerpt(excerpt)
        if not normalized:
            return
        clipped = normalized[:remaining_chars].strip()
        if not clipped:
            return
        sections_payload.append(
            {
                "source_kind": source_kind,
                "label": label.strip() or "unknown",
                "text": clipped,
            }
        )
        remaining_chars -= len(clipped)
        toc, intro, preface = _signal_flags(label)
        has_toc = has_toc or toc
        has_introduction = has_introduction or intro
        has_preface = has_preface or preface
        seen_ranges.add((start_char, end_char))

    for section in early_sections:
        if not isinstance(section, dict):
            continue
        section_type = section.get("type")
        start_char = section.get("start_char")
        end_char = section.get("end_char")
        label = section.get("label", "")
        if not isinstance(start_char, int) or not isinstance(end_char, int) or end_char <= start_char:
            continue
        if (start_char, end_char) in seen_ranges:
            continue
        if section_type == "front_matter":
            add_section(
                source_kind="document_map",
                label=str(label),
                excerpt=_section_text(text, start_char, end_char),
                start_char=start_char,
                end_char=end_char,
            )
            if "document_map" not in strategy_parts:
                strategy_parts.append("document_map")

    for heading in headings:
        if len(sections_payload) >= max_sections or remaining_chars <= 0:
            break
        if not isinstance(heading, dict):
            continue
        label = heading.get("text", "")
        start_char = heading.get("start_char")
        if not isinstance(label, str) or not isinstance(start_char, int):
            continue
        toc, intro, preface = _signal_flags(label)
        if not (toc or intro or preface):
            continue
        matching_section = None
        for section in early_sections:
            if not isinstance(section, dict):
                continue
            section_start = section.get("start_char")
            section_end = section.get("end_char")
            if isinstance(section_start, int) and isinstance(section_end, int) and section_start <= start_char < section_end:
                matching_section = section
                break
        if matching_section is None:
            continue
        section_start = matching_section["start_char"]
        section_end = matching_section["end_char"]
        if (section_start, section_end) in seen_ranges:
            continue
        add_section(
            source_kind="early_headings",
            label=label,
            excerpt=_section_text(text, section_start, section_end),
            start_char=section_start,
            end_char=section_end,
        )
        if "early_headings" not in strategy_parts:
            strategy_parts.append("early_headings")

    if not sections_payload and remaining_chars > 0:
        excerpt_end = min(len(text), max(0, initial_excerpt_chars), max_chars)
        excerpt = text[:excerpt_end].strip()
        add_section(
            source_kind="initial_excerpt",
            label="initial_excerpt",
            excerpt=excerpt,
            start_char=0,
            end_char=excerpt_end,
        )
        strategy_parts = ["initial_excerpt"]

    if not strategy_parts:
        strategy = "initial_excerpt"
    elif len(strategy_parts) == 1:
        strategy = strategy_parts[0]
    else:
        strategy = "mixed"

    return FrontMatterExtractionInput(
        book_title=book_title,
        source=FrontMatterSource(
            has_toc=has_toc,
            has_introduction=has_introduction,
            has_preface=has_preface,
            strategy=strategy,  # type: ignore[arg-type]
        ),
        prompt_sections=sections_payload,
    )


def build_front_matter_outline_prompt(extraction_input: FrontMatterExtractionInput) -> str:
    template = _load_template()
    source_payload = {
        "has_toc": extraction_input.source.has_toc,
        "has_introduction": extraction_input.source.has_introduction,
        "has_preface": extraction_input.source.has_preface,
        "strategy": extraction_input.source.strategy,
    }
    sections_payload = json.dumps(extraction_input.prompt_sections, ensure_ascii=False)
    return template.format(
        book_title=extraction_input.book_title,
        source_json=json.dumps(source_payload, ensure_ascii=False),
        sections_json=sections_payload,
    )


def extract_front_matter_outline(extraction_input: FrontMatterExtractionInput) -> FrontMatterExtractionResult:
    if not extraction_input.prompt_sections:
        record = make_empty_front_matter_outline(
            book_title=extraction_input.book_title,
            source=extraction_input.source,
            confidence_notes=["no_front_matter_input_selected"],
        )
        return FrontMatterExtractionResult(record=record, parse_error=None, used_fallback=True)

    prompt = build_front_matter_outline_prompt(extraction_input)
    raw = ask_llm(prompt)
    parsed = parse_front_matter_outline_json(
        raw,
        book_title=extraction_input.book_title,
        source=extraction_input.source,
        fallback_notes=[],
    )
    if parsed.ok:
        return FrontMatterExtractionResult(record=parsed.record, parse_error=None, used_fallback=False)
    return FrontMatterExtractionResult(record=parsed.record, parse_error=parsed.error, used_fallback=True)
