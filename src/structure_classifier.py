"""LLM-assisted heading classification with stable index-based reconciliation."""

from __future__ import annotations

import json
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

    if not use_llm or not selected:
        return {}, selected_indexes

    prompt = _build_classifier_prompt(selected)
    raw = ask_llm(prompt)
    parsed_items = _extract_json_array(raw)

    by_index: dict[int, HeadingClassification] = {}
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
