"""Deterministic extractability precheck for chunk-level knowledge extraction."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .config import (
    KNOWLEDGE_PRECHECK_HARD_FOOTNOTE_DENSITY,
    KNOWLEDGE_PRECHECK_HARD_OCR_NOISE_RATIO,
    KNOWLEDGE_PRECHECK_HARD_SHORT_LINE_RATIO,
    KNOWLEDGE_PRECHECK_NON_DOCTRINAL_SECTION_REF_NOISE_RATIO,
    KNOWLEDGE_PRECHECK_TYPE_CONFLICT_RATIO,
)
from .knowledge_schema import SectionRef

DECISION_EXTRACT = "extract"
DECISION_EXTRACT_DEGRADED = "extract_degraded"
DECISION_SKIP = "skip"

DOCTRINAL_TEXT = "doctrinal_text"
GLOSSARY = "glossary"
BIBLIOGRAPHY = "bibliography"
EXERCISES = "exercises"
CAPTIONS_TABLES_CHARTS = "captions_tables_charts"
FRONT_MATTER = "front_matter"
BACK_MATTER = "back_matter"
MIXED = "mixed"

NON_DOCTRINAL_TYPES = {
    GLOSSARY,
    BIBLIOGRAPHY,
    EXERCISES,
    CAPTIONS_TABLES_CHARTS,
    FRONT_MATTER,
    BACK_MATTER,
}

_RE_LETTER = re.compile(r"[A-Za-z]")
_RE_WORD = re.compile(r"\b\w+\b")
_RE_FOOTNOTE_LINE = re.compile(r"^\s*\d{1,3}[\)\.]?\s+[^\n]{3,180}$", re.MULTILINE)
_RE_CITATION_LOCATOR = re.compile(
    r"(?:\b(?:p|pp|vol|ch|sec)\.?\s*\d+|\b\d{1,4}(?:[-–]\d{1,4})?\b|[A-Z][a-z]+,\s*\d{4})"
)
_RE_OCR_SYMBOLS = re.compile(r"[\^£®§¤¢¥©°¬¶]+")
_RE_SHORT_LABEL_NOISE = re.compile(r"^[\W_]{1,6}$")
_RE_INDEX_STYLE = re.compile(
    r".+(?:\s|,)\d+(?:[-–]\d+)?(?:\s*,\s*\d+(?:[-–]\d+)?)*\.?$"
)
_RE_GLOSSARY_LINE = re.compile(r"^\s*[A-Za-z][^:\n]{1,40}:\s+.{8,}$", re.MULTILINE)
_RE_LIST_LINE = re.compile(r"^\s*(?:[-*•]|\d+[\)\.])\s+.{3,}$", re.MULTILINE)


@dataclass(slots=True)
class PrecheckResult:
    decision: str
    reason_codes: list[str]
    signals: dict[str, float | int | bool]
    chunk_type: str
    type_score: float
    dominant_signals: list[str]
    mixed_reason: str | None
    confidence_profile: str


def _safe_ratio(num: float, den: float) -> float:
    if den <= 0.0:
        return 0.0
    return float(num) / float(den)


def _is_noisy_label(label: str) -> bool:
    text = " ".join(label.split()).strip()
    if not text:
        return True
    if _RE_SHORT_LABEL_NOISE.match(text):
        return True
    if _RE_OCR_SYMBOLS.search(text):
        return True
    lowered = text.lower()
    if lowered in {"unknown", "section"}:
        return True
    if _RE_INDEX_STYLE.match(text):
        return True
    if len(text) <= 3 and not any(ch.isalpha() for ch in text):
        return True
    return False


def _signals(chunk_text: str, section_refs: list[SectionRef]) -> dict[str, float | int | bool]:
    text = chunk_text or ""
    stripped = text.strip()
    text_len = len(text)
    letters = len(_RE_LETTER.findall(text))
    digits = sum(1 for ch in text if ch.isdigit())
    spaces = sum(1 for ch in text if ch.isspace())
    symbols = max(0, text_len - letters - digits - spaces)
    words = _RE_WORD.findall(text)
    word_count = len(words)
    lines = [line for line in text.splitlines() if line.strip()]
    short_lines = [line for line in lines if len(line.strip()) <= 40]
    footnote_like_lines = len(_RE_FOOTNOTE_LINE.findall(text))
    citation_locators = len(_RE_CITATION_LOCATOR.findall(text))
    ocr_noise_hits = len(_RE_OCR_SYMBOLS.findall(text))
    glossary_lines = len(_RE_GLOSSARY_LINE.findall(text))
    list_lines = len(_RE_LIST_LINE.findall(text))
    unknown_ref_count = sum(1 for ref in section_refs if ref.type == "unknown")
    noisy_label_count = sum(1 for ref in section_refs if _is_noisy_label(ref.label))
    heading_like_ref_count = sum(1 for ref in section_refs if len(ref.label.strip().split()) <= 6)

    line_count = len(lines)
    line_short_ratio = _safe_ratio(len(short_lines), max(1, line_count))
    footnote_density = _safe_ratio(footnote_like_lines, max(1, line_count))
    citation_locator_density = _safe_ratio(citation_locators, max(1, word_count))
    ocr_noise_ratio = _safe_ratio(ocr_noise_hits, max(1, text_len))
    heading_body_ratio = _safe_ratio(heading_like_ref_count, max(1, len(section_refs)))
    section_ref_noise_ratio = _safe_ratio(noisy_label_count, max(1, len(section_refs)))

    return {
        "text_len": text_len,
        "word_count": word_count,
        "line_count": line_count,
        "line_short_ratio": line_short_ratio,
        "digit_ratio": _safe_ratio(digits, max(1, text_len)),
        "symbol_ratio": _safe_ratio(symbols, max(1, text_len)),
        "letter_ratio": _safe_ratio(letters, max(1, text_len)),
        "footnote_density": footnote_density,
        "citation_locator_density": citation_locator_density,
        "ocr_noise_ratio": ocr_noise_ratio,
        "heading_body_ratio": heading_body_ratio,
        "section_ref_noise_ratio": section_ref_noise_ratio,
        "unknown_ref_ratio": _safe_ratio(unknown_ref_count, max(1, len(section_refs))),
        "glossary_line_density": _safe_ratio(glossary_lines, max(1, line_count)),
        "list_line_density": _safe_ratio(list_lines, max(1, line_count)),
        "is_blank": not bool(stripped),
    }


def _type_scores(
    chunk_text: str,
    section_refs: list[SectionRef],
    signals: dict[str, float | int | bool],
) -> dict[str, float]:
    lowered = chunk_text.lower()
    labels = " ".join(ref.label.lower() for ref in section_refs)

    bibliography_score = 0.0
    if any(word in lowered for word in ("bibliography", "sources", "references", "works cited", "index")):
        bibliography_score += 0.45
    bibliography_score += min(0.35, float(signals["citation_locator_density"]) * 4.0)
    bibliography_score += min(0.20, float(signals["footnote_density"]) * 2.0)
    if any(word in labels for word in ("bibliography", "references", "sources")):
        bibliography_score += 0.25

    glossary_score = 0.0
    if any(word in lowered for word in ("glossary", "definitions", "terms")):
        glossary_score += 0.40
    glossary_score += min(0.45, float(signals["glossary_line_density"]) * 2.5)
    if re.search(r"\b[A-Za-z][A-Za-z\s]{1,30}\s*:\s+.{8,}", chunk_text):
        glossary_score += 0.20

    exercises_score = 0.0
    if any(word in lowered for word in ("exercise", "step", "practice", "assignment")):
        exercises_score += 0.45
    exercises_score += min(0.35, float(signals["list_line_density"]) * 2.0)
    if re.search(r"\bstep\s+\w+", lowered):
        exercises_score += 0.20

    captions_score = 0.0
    captions_score += min(0.35, float(signals["line_short_ratio"]) * 0.8)
    captions_score += min(0.25, float(signals["symbol_ratio"]) * 1.8)
    captions_score += min(0.20, float(signals["digit_ratio"]) * 1.6)
    if any(word in lowered for word in ("chart", "figure", "table")):
        captions_score += 0.30

    front_score = 0.0
    if any(word in lowered for word in ("copyright", "isbn", "contents", "preface", "by ")):
        front_score += 0.55
    if any(word in labels for word in ("front_matter", "contents", "preface")):
        front_score += 0.30

    back_score = 0.0
    if any(word in lowered for word in ("appendix", "glossary", "bibliography", "index", "sources")):
        back_score += 0.45
    if any(word in labels for word in ("bibliography", "index", "back_matter", "glossary")):
        back_score += 0.35

    doctrinal_score = 0.0
    if int(signals["word_count"]) >= 100:
        doctrinal_score += 0.35
    if float(signals["line_short_ratio"]) <= 0.45:
        doctrinal_score += 0.25
    if float(signals["citation_locator_density"]) <= 0.06:
        doctrinal_score += 0.15
    if float(signals["section_ref_noise_ratio"]) <= 0.40:
        doctrinal_score += 0.10
    if float(signals["ocr_noise_ratio"]) <= 0.003:
        doctrinal_score += 0.15

    return {
        DOCTRINAL_TEXT: min(doctrinal_score, 1.0),
        GLOSSARY: min(glossary_score, 1.0),
        BIBLIOGRAPHY: min(bibliography_score, 1.0),
        EXERCISES: min(exercises_score, 1.0),
        CAPTIONS_TABLES_CHARTS: min(captions_score, 1.0),
        FRONT_MATTER: min(front_score, 1.0),
        BACK_MATTER: min(back_score, 1.0),
    }


def _classify_chunk_type(
    chunk_text: str,
    section_refs: list[SectionRef],
    signals: dict[str, float | int | bool],
) -> tuple[str, float, list[str], str | None, float]:
    scores = _type_scores(chunk_text, section_refs, signals)
    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    top_type, top_score = ordered[0]
    second_type, second_score = ordered[1]

    incompatible_pair = (top_type in NON_DOCTRINAL_TYPES and second_type == DOCTRINAL_TEXT) or (
        top_type == DOCTRINAL_TEXT and second_type in NON_DOCTRINAL_TYPES
    )
    mixed_reason: str | None = None
    if top_score >= 0.50 and second_score >= 0.50 and abs(top_score - second_score) <= 0.15 and incompatible_pair:
        mixed_reason = f"{top_type}+{second_type}"
        return MIXED, top_score, [top_type, second_type], mixed_reason, second_score

    dominant_signals = [f"{name}:{value:.2f}" for name, value in ordered[:2]]
    conflict_score = max(0.0, min(1.0, second_score / max(0.01, top_score)))
    return top_type, top_score, dominant_signals, mixed_reason, conflict_score


def precheck_chunk_extractability(
    *,
    chunk_text: str,
    section_refs: list[SectionRef],
    review_default: str = DECISION_EXTRACT,
) -> PrecheckResult:
    """Return deterministic precheck decision for chunk extraction."""
    del review_default

    signals = _signals(chunk_text, section_refs)
    chunk_type, type_score, dominant_signals, mixed_reason, conflict_score = _classify_chunk_type(
        chunk_text, section_refs, signals
    )
    signals["type_conflict_score"] = conflict_score

    reasons: list[str] = []
    if bool(signals["is_blank"]):
        reasons.append("blank_text")
    if int(signals["word_count"]) < 18:
        reasons.append("very_short")
    if float(signals["ocr_noise_ratio"]) >= 0.006:
        reasons.append("high_ocr_noise")
    if float(signals["footnote_density"]) >= 0.35:
        reasons.append("footnote_dense")
    if float(signals["section_ref_noise_ratio"]) >= 0.75:
        reasons.append("section_refs_noisy")
    if float(signals["symbol_ratio"]) >= 0.24:
        reasons.append("high_symbol_ratio")
    if chunk_type in NON_DOCTRINAL_TYPES:
        reasons.append(f"non_doctrinal_type:{chunk_type}")
    if chunk_type == MIXED:
        reasons.append("mixed_incompatible_types")
    if float(signals["type_conflict_score"]) >= 0.75:
        reasons.append("high_type_conflict")

    hard_contamination = (
        bool(signals["is_blank"])
        or int(signals["word_count"]) < 10
        or float(signals["ocr_noise_ratio"]) >= KNOWLEDGE_PRECHECK_HARD_OCR_NOISE_RATIO
        or (
            float(signals["footnote_density"]) >= KNOWLEDGE_PRECHECK_HARD_FOOTNOTE_DENSITY
            and float(signals["line_short_ratio"]) >= KNOWLEDGE_PRECHECK_HARD_SHORT_LINE_RATIO
        )
    )
    if hard_contamination:
        decision = DECISION_SKIP
        confidence_profile = "contaminated"
    elif (
        chunk_type in NON_DOCTRINAL_TYPES
        or chunk_type == MIXED
        or float(signals["type_conflict_score"]) >= KNOWLEDGE_PRECHECK_TYPE_CONFLICT_RATIO
        or float(signals["section_ref_noise_ratio"]) >= KNOWLEDGE_PRECHECK_NON_DOCTRINAL_SECTION_REF_NOISE_RATIO
    ):
        decision = DECISION_EXTRACT_DEGRADED
        confidence_profile = "low"
    else:
        decision = DECISION_EXTRACT
        if type_score >= 0.70 and float(signals["section_ref_noise_ratio"]) <= 0.35:
            confidence_profile = "high"
        elif type_score >= 0.55:
            confidence_profile = "medium"
        else:
            confidence_profile = "low"

    return PrecheckResult(
        decision=decision,
        reason_codes=reasons,
        signals=signals,
        chunk_type=chunk_type,
        type_score=type_score,
        dominant_signals=dominant_signals,
        mixed_reason=mixed_reason,
        confidence_profile=confidence_profile,
    )
