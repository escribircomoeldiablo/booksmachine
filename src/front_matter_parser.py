"""Strict parsing and validation for front matter outline payloads."""

from __future__ import annotations

import json
from dataclasses import dataclass

from .front_matter_schema import (
    FRONT_MATTER_OUTLINE_SCHEMA_VERSION,
    CoreConceptExpected,
    FamilyCandidate,
    FrontMatterOutlineV1,
    FrontMatterSource,
    NormalizationHint,
    ProvisionalTaxonomyLink,
    make_empty_front_matter_outline,
)

_ALLOWED_SOURCE_STRATEGIES = {"document_map", "early_headings", "initial_excerpt", "mixed"}
_ALLOWED_PRIORITIES = {"high", "medium", "low"}
_ALLOWED_KEYS = {
    "schema_version",
    "book_title",
    "source",
    "family_candidates",
    "core_concepts_expected",
    "provisional_taxonomy",
    "normalization_hints",
    "confidence_notes",
}


@dataclass(slots=True)
class ParseResult:
    record: FrontMatterOutlineV1
    ok: bool
    error: str | None


def _extract_json_block(raw_text: str) -> str:
    stripped = raw_text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3:
            stripped = "\n".join(lines[1:-1]).strip()

    start = stripped.find("{")
    if start < 0:
        raise ValueError("Front matter outline response did not contain a JSON object")

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(stripped)):
        char = stripped[index]
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return stripped[start : index + 1]

    raise ValueError("Front matter outline response contained incomplete JSON")


def _expect_str(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    return value.strip()


def _expect_bool(value: object, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean")
    return value


def _clamp_confidence(value: object, field_name: str) -> float:
    if not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a number")
    return float(min(1.0, max(0.0, value)))


def _normalize_string_list(value: object, field_name: str) -> list[str]:
    if value is None:
        raise ValueError(f"{field_name} must be an array, got null")
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be an array")
    output: list[str] = []
    for idx, item in enumerate(value):
        text = _expect_str(item, f"{field_name}[{idx}]")
        if text:
            output.append(text)
    return output


def _normalize_source(value: object) -> FrontMatterSource:
    if not isinstance(value, dict):
        raise ValueError("source must be an object")
    keys = set(value.keys())
    required = {"has_toc", "has_introduction", "has_preface", "strategy"}
    extras = sorted(keys - required)
    missing = sorted(required - keys)
    if extras or missing:
        details: list[str] = []
        if missing:
            details.append(f"missing={missing}")
        if extras:
            details.append(f"extra={extras}")
        raise ValueError(f"source invalid keys ({', '.join(details)})")
    strategy = _expect_str(value.get("strategy"), "source.strategy").lower()
    if strategy not in _ALLOWED_SOURCE_STRATEGIES:
        raise ValueError(f"source.strategy must be one of {sorted(_ALLOWED_SOURCE_STRATEGIES)}")
    return FrontMatterSource(
        has_toc=_expect_bool(value.get("has_toc"), "source.has_toc"),
        has_introduction=_expect_bool(value.get("has_introduction"), "source.has_introduction"),
        has_preface=_expect_bool(value.get("has_preface"), "source.has_preface"),
        strategy=strategy,  # type: ignore[arg-type]
    )


def _normalize_family_candidates(value: object) -> list[FamilyCandidate]:
    if value is None:
        raise ValueError("family_candidates must be an array, got null")
    if not isinstance(value, list):
        raise ValueError("family_candidates must be an array")
    output: list[FamilyCandidate] = []
    for idx, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(f"family_candidates[{idx}] must be an object")
        status = _expect_str(item.get("status", "candidate"), f"family_candidates[{idx}].status").lower()
        if status != "candidate":
            raise ValueError(f"family_candidates[{idx}].status must be 'candidate'")
        output.append(
            FamilyCandidate(
                name=_expect_str(item.get("name"), f"family_candidates[{idx}].name"),
                aliases=_normalize_string_list(item.get("aliases", []), f"family_candidates[{idx}].aliases"),
                evidence=_normalize_string_list(item.get("evidence", []), f"family_candidates[{idx}].evidence"),
                confidence=_clamp_confidence(item.get("confidence", 0.0), f"family_candidates[{idx}].confidence"),
                status="candidate",
            )
        )
    return output


def _normalize_core_concepts(value: object) -> list[CoreConceptExpected]:
    if value is None:
        raise ValueError("core_concepts_expected must be an array, got null")
    if not isinstance(value, list):
        raise ValueError("core_concepts_expected must be an array")
    output: list[CoreConceptExpected] = []
    for idx, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(f"core_concepts_expected[{idx}] must be an object")
        priority = _expect_str(item.get("priority", "medium"), f"core_concepts_expected[{idx}].priority").lower()
        if priority not in _ALLOWED_PRIORITIES:
            raise ValueError(f"core_concepts_expected[{idx}].priority must be one of {sorted(_ALLOWED_PRIORITIES)}")
        output.append(
            CoreConceptExpected(
                name=_expect_str(item.get("name"), f"core_concepts_expected[{idx}].name"),
                evidence=_normalize_string_list(item.get("evidence", []), f"core_concepts_expected[{idx}].evidence"),
                priority=priority,  # type: ignore[arg-type]
            )
        )
    return output


def _normalize_taxonomy(value: object) -> list[ProvisionalTaxonomyLink]:
    if value is None:
        raise ValueError("provisional_taxonomy must be an array, got null")
    if not isinstance(value, list):
        raise ValueError("provisional_taxonomy must be an array")
    output: list[ProvisionalTaxonomyLink] = []
    for idx, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(f"provisional_taxonomy[{idx}] must be an object")
        output.append(
            ProvisionalTaxonomyLink(
                parent=_expect_str(item.get("parent"), f"provisional_taxonomy[{idx}].parent"),
                child=_expect_str(item.get("child"), f"provisional_taxonomy[{idx}].child"),
                relation_type=_expect_str(item.get("relation_type"), f"provisional_taxonomy[{idx}].relation_type"),
                confidence=_clamp_confidence(item.get("confidence", 0.0), f"provisional_taxonomy[{idx}].confidence"),
            )
        )
    return output


def _normalize_hints(value: object) -> list[NormalizationHint]:
    if value is None:
        raise ValueError("normalization_hints must be an array, got null")
    if not isinstance(value, list):
        raise ValueError("normalization_hints must be an array")
    output: list[NormalizationHint] = []
    for idx, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(f"normalization_hints[{idx}] must be an object")
        output.append(
            NormalizationHint(
                canonical=_expect_str(item.get("canonical"), f"normalization_hints[{idx}].canonical"),
                variants=_normalize_string_list(item.get("variants", []), f"normalization_hints[{idx}].variants"),
            )
        )
    return output


def validate_front_matter_outline(record: dict[str, object]) -> FrontMatterOutlineV1:
    keys = set(record.keys())
    extras = sorted(keys - _ALLOWED_KEYS)
    if extras:
        raise ValueError(f"Unexpected keys in front matter outline payload: {extras}")
    schema_version = record.get("schema_version")
    if schema_version != FRONT_MATTER_OUTLINE_SCHEMA_VERSION:
        raise ValueError(
            f"schema_version must be '{FRONT_MATTER_OUTLINE_SCHEMA_VERSION}', got {schema_version!r}"
        )
    return FrontMatterOutlineV1(
        schema_version=FRONT_MATTER_OUTLINE_SCHEMA_VERSION,
        book_title=_expect_str(record.get("book_title"), "book_title"),
        source=_normalize_source(record.get("source")),
        family_candidates=_normalize_family_candidates(record.get("family_candidates", [])),
        core_concepts_expected=_normalize_core_concepts(record.get("core_concepts_expected", [])),
        provisional_taxonomy=_normalize_taxonomy(record.get("provisional_taxonomy", [])),
        normalization_hints=_normalize_hints(record.get("normalization_hints", [])),
        confidence_notes=_normalize_string_list(record.get("confidence_notes", []), "confidence_notes"),
    )


def parse_front_matter_outline_json(
    raw_text: str,
    *,
    book_title: str,
    source: FrontMatterSource,
    fallback_notes: list[str] | None = None,
) -> ParseResult:
    fallback = make_empty_front_matter_outline(
        book_title=book_title,
        source=source,
        confidence_notes=fallback_notes or [],
    )
    if not raw_text.strip():
        return ParseResult(record=fallback, ok=False, error="Empty LLM output")
    try:
        parsed = json.loads(_extract_json_block(raw_text))
        if not isinstance(parsed, dict):
            raise ValueError("Root JSON value must be an object")
        parsed["book_title"] = book_title
        parsed.setdefault(
            "source",
            {
                "has_toc": source.has_toc,
                "has_introduction": source.has_introduction,
                "has_preface": source.has_preface,
                "strategy": source.strategy,
            },
        )
        parsed.setdefault("schema_version", FRONT_MATTER_OUTLINE_SCHEMA_VERSION)
        parsed.setdefault("family_candidates", [])
        parsed.setdefault("core_concepts_expected", [])
        parsed.setdefault("provisional_taxonomy", [])
        parsed.setdefault("normalization_hints", [])
        parsed.setdefault("confidence_notes", [])
        validated = validate_front_matter_outline(parsed)
        return ParseResult(record=validated, ok=True, error=None)
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        notes = list(fallback.confidence_notes)
        notes.append(f"parse_fallback: {exc}")
        fallback.confidence_notes = notes
        return ParseResult(record=fallback, ok=False, error=str(exc))
