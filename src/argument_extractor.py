"""Chunk-level structured argumentative extraction."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .ai_client import ask_llm
from .argument_parser import parse_argument_chunk_json
from .argument_schema import ArgumentChunkV1
from .knowledge_schema import SectionRef

_PROMPT_TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "prompts" / "argument_extraction.txt"


@dataclass(slots=True)
class ExtractionResult:
    record: ArgumentChunkV1
    parse_error: str | None
    used_fallback: bool
    llm_response_present: bool
    error_kind: str | None


def _load_template() -> str:
    return _PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")


def get_argument_prompt_hash() -> str:
    import hashlib

    return hashlib.sha256(_load_template().encode("utf-8")).hexdigest()


def build_argument_prompt(
    *,
    chunk_text: str,
    chunk_id: str,
    source_fingerprint: str,
    section_refs_json: str,
    knowledge_language: str = "original",
) -> str:
    template = _load_template()
    if knowledge_language == "es":
        language_instruction = (
            "Escribe la salida estructurada en espanol tecnico claro. Conserva sin traducir "
            "terminos o nombres propios cuando traducir degrade precision."
        )
    else:
        language_instruction = (
            "Escribe la salida estructurada en el idioma original dominante del fragmento. "
            "No traduzcas terminos salvo necesidad de claridad."
        )
    return template.format(
        chunk_text=chunk_text,
        chunk_id=chunk_id,
        source_fingerprint=source_fingerprint,
        section_refs_json=section_refs_json,
        language_instruction=language_instruction,
    )


def _format_section_refs(section_refs: list[SectionRef]) -> str:
    import json

    payload = [
        {
            "label": ref.label,
            "type": ref.type,
            "start_char": ref.start_char,
            "end_char": ref.end_char,
        }
        for ref in section_refs
    ]
    return json.dumps(payload, ensure_ascii=False)


def extract_argument_chunk(
    *,
    chunk_text: str,
    chunk_id: str,
    source_fingerprint: str,
    section_refs: list[SectionRef] | None = None,
    knowledge_language: str = "original",
) -> ExtractionResult:
    refs = list(section_refs or [])
    prompt = build_argument_prompt(
        chunk_text=chunk_text,
        chunk_id=chunk_id,
        source_fingerprint=source_fingerprint,
        section_refs_json=_format_section_refs(refs),
        knowledge_language=knowledge_language,
    )
    try:
        raw = ask_llm(prompt)
    except Exception as exc:
        parsed = parse_argument_chunk_json(
            "",
            chunk_id=chunk_id,
            source_fingerprint=source_fingerprint,
            section_refs=refs,
        )
        return ExtractionResult(
            record=parsed.record,
            parse_error=str(exc),
            used_fallback=True,
            llm_response_present=False,
            error_kind="llm_empty",
        )
    raw_text = raw if isinstance(raw, str) else ""
    if not raw_text.strip():
        parsed = parse_argument_chunk_json(
            "",
            chunk_id=chunk_id,
            source_fingerprint=source_fingerprint,
            section_refs=refs,
        )
        return ExtractionResult(
            record=parsed.record,
            parse_error=parsed.error,
            used_fallback=True,
            llm_response_present=False,
            error_kind="llm_empty",
        )
    parsed = parse_argument_chunk_json(
        raw_text,
        chunk_id=chunk_id,
        source_fingerprint=source_fingerprint,
        section_refs=refs,
    )
    return ExtractionResult(
        record=parsed.record,
        parse_error=parsed.error,
        used_fallback=not parsed.ok,
        llm_response_present=True,
        error_kind=parsed.error_kind,
    )
