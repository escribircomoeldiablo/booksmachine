"""LLM-assisted heading classification with stable index-based reconciliation."""

from __future__ import annotations

import json
import re
from typing import TypedDict

from .ai_client import ask_llm
from .structure_types import HeadingCandidate, SectionType

_ALLOWED_TYPES: set[str] = {
    "front_matter",
    "chapter",
    "section",
    "appendix",
    "bibliography",
    "index",
    "unknown",
}

_PATTERN_TO_TYPE: dict[str, SectionType] = {
    "chapter_pattern": "chapter",
    "part_pattern": "chapter",
    "appendix_pattern": "appendix",
    "bibliography_pattern": "bibliography",
    "index_pattern": "index",
    "roman_numeral": "section",
    "decimal_numbering": "section",
}
_SOFT_SECTION_KEYWORDS = {
    "abstract",
    "conclusion",
    "example",
    "examples",
    "exercise",
    "exercises",
    "glossary",
    "introduction",
    "overview",
    "preface",
    "prologue",
    "review",
    "summary",
}


class HeadingClassification(TypedDict):
    index: int
    type: SectionType
    confidence: float


def _clamp_confidence(value: object) -> float:
    if isinstance(value, (int, float)):
        return float(min(1.0, max(0.0, value)))
    return 0.0


def _normalize_type(value: object) -> SectionType:
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in _ALLOWED_TYPES:
            return lowered  # type: ignore[return-value]
    return "unknown"


def _extract_json_array(raw: str) -> list[object]:
    stripped = raw.strip()
    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        pass

    start = stripped.find("[")
    end = stripped.rfind("]")
    if start >= 0 and end > start:
        try:
            candidate = json.loads(stripped[start : end + 1])
            if isinstance(candidate, list):
                return candidate
        except json.JSONDecodeError:
            return []
    return []


def _build_classifier_prompt(headings: list[HeadingCandidate]) -> str:
    payload = [{"index": item["index"], "text": item["text"]} for item in headings]
    return (
        "Clasifica los siguientes headings de un libro.\n"
        "Devuelve SOLO un JSON array con objetos de esta forma:\n"
        '[{"index":0,"type":"chapter","confidence":0.9}]\n'
        "Tipos permitidos: front_matter, chapter, section, appendix, bibliography, index, unknown.\n"
        "No agregues explicaciones.\n\n"
        f"Headings:\n{json.dumps(payload, ensure_ascii=True)}"
    )


def is_reference_like_strong(label: str) -> bool:
    stripped = label.strip()
    if not stripped:
        return False

    # Parenthesized years are usually bibliographic/reference markers.
    if re.search(r"\(\s*(?:18|19|20)\d{2}\s*\)", stripped):
        return True

    # Decimal locator chains such as 2.21.2, 4.12,9.2, 2.939-46.
    if re.search(r"\d+\.\d+(?:\.\d+)?(?:[-–]\d+)?", stripped):
        return True

    # Multiple locators separated by commas.
    comma_numeric_tokens = re.findall(r"\d+(?:\.\d+)*(?:[-–]\d+)?", stripped)
    if len(comma_numeric_tokens) >= 2 and "," in stripped:
        return True

    # High density of digits/punctuation relative to text length.
    digits = sum(1 for char in stripped if char.isdigit())
    punct = sum(1 for char in stripped if char in {".", ",", ";", ":", "-", "–", "(", ")"})
    ratio = float(digits + punct) / float(max(1, len(stripped)))
    if ratio >= 0.22 and digits >= 3:
        return True
    return False


def _intrinsic_title_case_section_confidence(label: str) -> float | None:
    stripped = label.strip()
    if not stripped:
        return None
    if is_reference_like_strong(stripped):
        return None
    if re.fullmatch(r"[A-Z]", stripped):
        return None

    words = [token for token in re.split(r"\s+", stripped) if token]
    word_count = len(words)
    lowered = stripped.lower()
    has_digit = any(char.isdigit() for char in stripped)
    if any(keyword in lowered for keyword in _SOFT_SECTION_KEYWORDS):
        return 0.68
    if ":" in stripped and not has_digit and 2 <= word_count <= 10:
        return 0.62
    if not has_digit and 2 <= word_count <= 6:
        return 0.58
    return None


def _deterministic_base_classification(
    headings: list[HeadingCandidate],
) -> dict[int, HeadingClassification]:
    by_index: dict[int, HeadingClassification] = {}
    for heading in headings:
        pattern = heading.get("pattern")
        if not isinstance(pattern, str):
            continue
        section_type = _PATTERN_TO_TYPE.get(pattern)
        if section_type is not None:
            by_index[heading["index"]] = HeadingClassification(
                index=heading["index"],
                type=section_type,
                confidence=_clamp_confidence(max(0.6, heading["score"])),
            )
            continue
        if pattern != "title_case_short":
            continue
        confidence = _intrinsic_title_case_section_confidence(heading["text"])
        if confidence is None:
            continue
        by_index[heading["index"]] = HeadingClassification(
            index=heading["index"],
            type="section",
            confidence=_clamp_confidence(confidence),
        )
    return by_index


def classify_headings(
    headings: list[HeadingCandidate],
    *,
    max_headings_for_llm: int,
    use_llm: bool = True,
) -> tuple[dict[int, HeadingClassification], set[int]]:
    """Classify heading candidates by index, with deterministic fallback."""
    if not headings:
        return {}, set()

    sorted_by_score = sorted(headings, key=lambda item: item["score"], reverse=True)
    selected = sorted_by_score[: max(0, max_headings_for_llm)]
    selected_indexes = {item["index"] for item in selected}
    by_index = _deterministic_base_classification(headings)

    if not use_llm or not selected:
        return by_index, selected_indexes

    prompt = _build_classifier_prompt(selected)
    raw = ask_llm(prompt)
    parsed_items = _extract_json_array(raw)

    for item in parsed_items:
        if not isinstance(item, dict):
            continue
        index = item.get("index")
        if not isinstance(index, int):
            continue
        if index not in selected_indexes:
            continue
        by_index[index] = HeadingClassification(
            index=index,
            type=_normalize_type(item.get("type")),
            confidence=_clamp_confidence(item.get("confidence")),
        )

    return by_index, selected_indexes
