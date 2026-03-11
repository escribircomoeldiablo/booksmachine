"""Strict parsing and validation for argumentative chunk extraction payloads."""

from __future__ import annotations

import json
from dataclasses import dataclass

from .argument_schema import ARGUMENT_CHUNK_SCHEMA_VERSION, ArgumentChunkV1, make_empty_argument_chunk
from .knowledge_schema import SectionRef

_ARRAY_FIELDS = (
    "theses",
    "claims",
    "evidence",
    "methods",
    "authors_or_schools",
    "key_terms",
    "debates",
    "limitations",
)
_ALLOWED_KEYS = {
    "schema_version",
    "chunk_id",
    "source_fingerprint",
    "section_refs",
    *_ARRAY_FIELDS,
}


@dataclass(slots=True)
class ParseResult:
    record: ArgumentChunkV1
    ok: bool
    error: str | None
    error_kind: str | None


def _extract_json_block(raw_text: str) -> str:
    stripped = raw_text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3:
            stripped = "\n".join(lines[1:-1]).strip()

    start = stripped.find("{")
    if start < 0:
        raise ValueError("Argument extraction response did not contain a JSON object")

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

    raise ValueError("Argument extraction response contained incomplete JSON")


def _expect_str(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    return value.strip()


def _normalize_string_list(value: object, field_name: str) -> list[str]:
    if value is None:
        raise ValueError(f"{field_name} must be an array, got null")
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be an array")
    normalized: list[str] = []
    for idx, item in enumerate(value):
        text = _expect_str(item, f"{field_name}[{idx}]")
        if text:
            normalized.append(" ".join(text.split()))
    return normalized


def validate_argument_chunk_record(
    record: dict[str, object],
    *,
    chunk_id: str,
    source_fingerprint: str,
    section_refs: list[SectionRef],
) -> ArgumentChunkV1:
    extras = sorted(set(record.keys()) - _ALLOWED_KEYS)
    if extras:
        raise ValueError(f"Unexpected keys in argument payload: {extras}")
    schema_version = record.get("schema_version")
    if schema_version not in {None, ARGUMENT_CHUNK_SCHEMA_VERSION}:
        raise ValueError(
            f"schema_version must be '{ARGUMENT_CHUNK_SCHEMA_VERSION}', got {schema_version!r}"
        )
    return ArgumentChunkV1(
        schema_version=ARGUMENT_CHUNK_SCHEMA_VERSION,
        chunk_id=chunk_id,
        source_fingerprint=source_fingerprint,
        section_refs=list(section_refs),
        theses=_normalize_string_list(record.get("theses", []), "theses"),
        claims=_normalize_string_list(record.get("claims", []), "claims"),
        evidence=_normalize_string_list(record.get("evidence", []), "evidence"),
        methods=_normalize_string_list(record.get("methods", []), "methods"),
        authors_or_schools=_normalize_string_list(record.get("authors_or_schools", []), "authors_or_schools"),
        key_terms=_normalize_string_list(record.get("key_terms", []), "key_terms"),
        debates=_normalize_string_list(record.get("debates", []), "debates"),
        limitations=_normalize_string_list(record.get("limitations", []), "limitations"),
    )


def parse_argument_chunk_json(
    raw_text: str,
    *,
    chunk_id: str,
    source_fingerprint: str,
    section_refs: list[SectionRef],
) -> ParseResult:
    fallback = make_empty_argument_chunk(
        chunk_id=chunk_id,
        source_fingerprint=source_fingerprint,
        section_refs=section_refs,
    )
    if not raw_text.strip():
        return ParseResult(record=fallback, ok=False, error="Empty LLM output", error_kind="parse_fallback")
    try:
        parsed = json.loads(_extract_json_block(raw_text))
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        return ParseResult(record=fallback, ok=False, error=str(exc), error_kind="parse_fallback")
    if not isinstance(parsed, dict):
        return ParseResult(
            record=fallback,
            ok=False,
            error="Root JSON value must be an object",
            error_kind="invalid_payload",
        )
    try:
        validated = validate_argument_chunk_record(
            parsed,
            chunk_id=chunk_id,
            source_fingerprint=source_fingerprint,
            section_refs=section_refs,
        )
        return ParseResult(record=validated, ok=True, error=None, error_kind=None)
    except (ValueError, TypeError) as exc:
        return ParseResult(record=fallback, ok=False, error=str(exc), error_kind="invalid_payload")
