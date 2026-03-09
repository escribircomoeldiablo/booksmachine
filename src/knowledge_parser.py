"""Strict parsing and validation for ChunkKnowledgeV1 payloads."""

from __future__ import annotations

import json
from dataclasses import dataclass

from .knowledge_schema import (
    CHUNK_KNOWLEDGE_SCHEMA_VERSION,
    ChunkKnowledgeV1,
    SectionRef,
    make_empty_chunk_knowledge,
)

_ARRAY_FIELDS = {
    "concepts",
    "definitions",
    "technical_rules",
    "procedures",
    "terminology",
    "relationships",
    "examples",
    "ambiguities",
}
_ALLOWED_KEYS = {
    "schema_version",
    "chunk_id",
    "source_fingerprint",
    "section_refs",
    *_ARRAY_FIELDS,
}


@dataclass(slots=True)
class ParseResult:
    record: ChunkKnowledgeV1
    ok: bool
    error: str | None


def _expect_str(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    return value.strip()


def _bridge_object_to_string(field_name: str, item: dict[str, object]) -> str | None:
    # Field-specific bridges with explicit key priority.
    if field_name == "definitions":
        term = item.get("term")
        definition = item.get("definition")
        if isinstance(term, str) and isinstance(definition, str):
            term_text = term.strip()
            def_text = definition.strip()
            if term_text and def_text:
                return f"{term_text}: {def_text}"
            if def_text:
                return def_text
            if term_text:
                return term_text
            return None
        if isinstance(definition, str):
            return definition.strip() or None
        if isinstance(term, str):
            return term.strip() or None
        return None

    if field_name == "examples":
        case = item.get("case")
        description = item.get("description")
        if isinstance(case, str) and isinstance(description, str):
            case_text = case.strip()
            desc_text = description.strip()
            if case_text and desc_text:
                return f"{case_text}: {desc_text}"
        for key in ("example", "text", "scenario", "description", "case"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    if field_name == "relationships":
        source = item.get("source")
        target = item.get("target")
        relation = item.get("relation")
        description = item.get("description")
        if isinstance(source, str) and isinstance(target, str):
            if isinstance(relation, str) and relation.strip():
                return f"{source.strip()} -> {target.strip()} ({relation.strip()})"
            if isinstance(description, str) and description.strip():
                return f"{source.strip()} -> {target.strip()}: {description.strip()}"
            return f"{source.strip()} -> {target.strip()}"
        if isinstance(description, str) and description.strip():
            return description.strip()

    # Conservative generic bridge for unexpected object shapes:
    # keep only non-empty string scalar values, joined in key order.
    scalar_pairs: list[tuple[str, str]] = []
    for key in sorted(item.keys()):
        value = item.get(key)
        if isinstance(value, str):
            normalized = value.strip()
            if normalized:
                scalar_pairs.append((key, normalized))
    if not scalar_pairs:
        return None
    if len(scalar_pairs) == 1:
        return scalar_pairs[0][1]
    return "; ".join(f"{key}: {value}" for key, value in scalar_pairs)


def _normalize_string_list(record: dict[str, object], field_name: str) -> list[str]:
    if field_name not in record:
        return []
    value = record[field_name]
    if value is None:
        raise ValueError(f"{field_name} must be an array, got null")
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be an array")
    normalized: list[str] = []
    for idx, item in enumerate(value):
        text: str
        if isinstance(item, str):
            text = item.strip()
        elif isinstance(item, dict):
            bridged = _bridge_object_to_string(field_name, item)
            if bridged is None:
                raise ValueError(f"{field_name}[{idx}] must be a string")
            text = bridged
        else:
            raise ValueError(f"{field_name}[{idx}] must be a string")
        if text:
            normalized.append(text)
    return normalized


def _normalize_section_refs(value: object) -> list[SectionRef]:
    if value is None:
        raise ValueError("section_refs must be an array, got null")
    if not isinstance(value, list):
        raise ValueError("section_refs must be an array")
    refs: list[SectionRef] = []
    for idx, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(f"section_refs[{idx}] must be an object")
        keys = set(item.keys())
        required = {"label", "type", "start_char", "end_char"}
        if keys != required:
            missing = sorted(required - keys)
            extras = sorted(keys - required)
            details: list[str] = []
            if missing:
                details.append(f"missing={missing}")
            if extras:
                details.append(f"extra={extras}")
            joined = ", ".join(details)
            raise ValueError(f"section_refs[{idx}] invalid keys ({joined})")
        label = _expect_str(item["label"], f"section_refs[{idx}].label")
        section_type = _expect_str(item["type"], f"section_refs[{idx}].type")
        start_char = item["start_char"]
        end_char = item["end_char"]
        if not isinstance(start_char, int):
            raise ValueError(f"section_refs[{idx}].start_char must be int")
        if not isinstance(end_char, int):
            raise ValueError(f"section_refs[{idx}].end_char must be int")
        refs.append(
            SectionRef(
                label=label,
                type=section_type,
                start_char=start_char,
                end_char=end_char,
            )
        )
    return refs


def validate_chunk_knowledge(record: dict[str, object]) -> ChunkKnowledgeV1:
    """Validate a parsed dictionary and return a canonical ChunkKnowledgeV1."""
    keys = set(record.keys())
    extras = sorted(keys - _ALLOWED_KEYS)
    if extras:
        raise ValueError(f"Unexpected keys in chunk knowledge payload: {extras}")

    schema_version = record.get("schema_version")
    if schema_version != CHUNK_KNOWLEDGE_SCHEMA_VERSION:
        raise ValueError(
            f"schema_version must be '{CHUNK_KNOWLEDGE_SCHEMA_VERSION}', got {schema_version!r}"
        )

    chunk_id = _expect_str(record.get("chunk_id"), "chunk_id")
    source_fingerprint = _expect_str(record.get("source_fingerprint"), "source_fingerprint")
    section_refs = _normalize_section_refs(record.get("section_refs", []))

    return ChunkKnowledgeV1(
        schema_version=CHUNK_KNOWLEDGE_SCHEMA_VERSION,
        chunk_id=chunk_id,
        source_fingerprint=source_fingerprint,
        section_refs=section_refs,
        concepts=_normalize_string_list(record, "concepts"),
        definitions=_normalize_string_list(record, "definitions"),
        technical_rules=_normalize_string_list(record, "technical_rules"),
        procedures=_normalize_string_list(record, "procedures"),
        terminology=_normalize_string_list(record, "terminology"),
        relationships=_normalize_string_list(record, "relationships"),
        examples=_normalize_string_list(record, "examples"),
        ambiguities=_normalize_string_list(record, "ambiguities"),
    )


def parse_chunk_knowledge_json(
    raw_text: str,
    *,
    chunk_id: str,
    source_fingerprint: str,
    section_refs: list[SectionRef] | None = None,
) -> ParseResult:
    """Parse strict JSON and return validated record or fallback with explicit error."""
    fallback = make_empty_chunk_knowledge(
        chunk_id=chunk_id,
        source_fingerprint=source_fingerprint,
        section_refs=section_refs,
    )
    if not raw_text.strip():
        return ParseResult(record=fallback, ok=False, error="Empty LLM output")

    try:
        parsed = json.loads(raw_text)
        if not isinstance(parsed, dict):
            raise ValueError("Root JSON value must be an object")
        parsed.setdefault("chunk_id", chunk_id)
        parsed.setdefault("source_fingerprint", source_fingerprint)
        parsed.setdefault(
            "section_refs",
            [
                {
                    "label": ref.label,
                    "type": ref.type,
                    "start_char": ref.start_char,
                    "end_char": ref.end_char,
                }
                for ref in (section_refs or [])
            ],
        )
        for field_name in _ARRAY_FIELDS:
            if field_name not in parsed:
                parsed[field_name] = []
        if "schema_version" not in parsed:
            parsed["schema_version"] = CHUNK_KNOWLEDGE_SCHEMA_VERSION
        validated = validate_chunk_knowledge(parsed)
        return ParseResult(record=validated, ok=True, error=None)
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        return ParseResult(record=fallback, ok=False, error=str(exc))
