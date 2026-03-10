"""Chunk-level structured technical knowledge extraction."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .ai_client import ask_llm
from .knowledge_normalize import normalize_chunk_knowledge
from .knowledge_parser import parse_chunk_knowledge_json
from .knowledge_schema import ChunkKnowledgeV1, SectionRef

_PROMPT_TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "prompts" / "chunk_knowledge_extraction.txt"


@dataclass(slots=True)
class ExtractionResult:
    record: ChunkKnowledgeV1
    parse_error: str | None
    used_fallback: bool


def _load_template() -> str:
    return _PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")


def _format_section_refs(section_refs: list[SectionRef]) -> str:
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


def build_chunk_knowledge_prompt(
    *,
    chunk_text: str,
    chunk_id: str,
    source_fingerprint: str,
    section_refs: list[SectionRef],
    knowledge_language: str = "original",
) -> str:
    if knowledge_language == "es":
        language_instruction = (
            "Escribe los campos textuales en espanol tecnico claro. Conserva sin traducir "
            "terminos latinos y nombres tecnicos originales cuando la traduccion degrade precision."
        )
    else:
        language_instruction = (
            "Escribe los campos textuales en el idioma original del fragmento. No traduzcas "
            "terminos tecnicos salvo que sea imprescindible para desambiguar."
        )
    template = _load_template()
    return template.format(
        chunk_text=chunk_text,
        chunk_id=chunk_id,
        source_fingerprint=source_fingerprint,
        section_refs_json=_format_section_refs(section_refs),
        language_instruction=language_instruction,
    )


def extract_chunk_knowledge(
    *,
    chunk_text: str,
    chunk_id: str,
    source_fingerprint: str,
    section_refs: list[SectionRef] | None = None,
    knowledge_language: str = "original",
) -> ExtractionResult:
    """Extract and validate ChunkKnowledgeV1 from a chunk."""
    refs = list(section_refs or [])
    prompt = build_chunk_knowledge_prompt(
        chunk_text=chunk_text,
        chunk_id=chunk_id,
        source_fingerprint=source_fingerprint,
        section_refs=refs,
        knowledge_language=knowledge_language,
    )
    raw = ask_llm(prompt)
    parsed = parse_chunk_knowledge_json(
        raw,
        chunk_id=chunk_id,
        source_fingerprint=source_fingerprint,
        section_refs=refs,
    )
    normalized = normalize_chunk_knowledge(parsed.record)
    return ExtractionResult(
        record=normalized,
        parse_error=parsed.error,
        used_fallback=not parsed.ok,
    )


def chunk_knowledge_to_summary_text(record: ChunkKnowledgeV1, *, output_language: str = "es") -> str:
    """Render structured knowledge as minimal readable synthesis input."""

    def _lines(title: str, items: list[str]) -> list[str]:
        if not items:
            return [title, "- (empty)"]
        return [title, *[f"- {item}" for item in items]]

    headers = {
        "concepts": "CONCEPTOS" if output_language == "es" else "CONCEPTS",
        "definitions": "DEFINICIONES" if output_language == "es" else "DEFINITIONS",
        "rules": "REGLAS" if output_language == "es" else "RULES",
        "procedures": "PROCEDIMIENTOS" if output_language == "es" else "PROCEDURES",
        "terminology": "TERMINOLOGIA" if output_language == "es" else "TERMINOLOGY",
        "procedure_steps": "PASOS DEL PROCEDIMIENTO" if output_language == "es" else "PROCEDURE STEPS",
        "decision_rules": "REGLAS DE DECISION" if output_language == "es" else "DECISION RULES",
        "preconditions": "PRECONDICIONES" if output_language == "es" else "PRECONDITIONS",
        "exceptions": "EXCEPCIONES" if output_language == "es" else "EXCEPTIONS",
        "author_variants": "VARIANTES POR AUTOR" if output_language == "es" else "AUTHOR VARIANTS",
        "procedure_outputs": "SALIDAS DEL PROCEDIMIENTO" if output_language == "es" else "PROCEDURE OUTPUTS",
        "relationships": "RELACIONES" if output_language == "es" else "RELATIONSHIPS",
        "examples": "EJEMPLOS" if output_language == "es" else "EXAMPLES",
        "ambiguities": "AMBIGUEDADES" if output_language == "es" else "AMBIGUITIES",
    }

    lines: list[str] = []
    lines.extend(_lines(headers["concepts"], record.concepts))
    lines.append("")
    lines.extend(_lines(headers["definitions"], record.definitions))
    lines.append("")
    lines.extend(_lines(headers["rules"], record.technical_rules))
    lines.append("")
    lines.extend(_lines(headers["procedures"], record.procedures))
    lines.append("")
    lines.extend(
        _lines(
            headers["procedure_steps"],
            [f"{item.order}. {item.text}" for item in sorted(record.procedure_steps, key=lambda step: (step.order, step.id))],
        )
    )
    lines.append("")
    lines.extend(
        _lines(
            headers["decision_rules"],
            [
                f"if {item.condition} -> {item.outcome}"
                + (f" [steps: {', '.join(item.related_steps)}]" if item.related_steps else "")
                for item in record.decision_rules
            ],
        )
    )
    lines.append("")
    lines.extend(
        _lines(
            headers["preconditions"],
            [
                item.text + (f" [scope: {item.scope}]" if item.scope else "") + (f" [steps: {', '.join(item.related_steps)}]" if item.related_steps else "")
                for item in record.preconditions
            ],
        )
    )
    lines.append("")
    lines.extend(
        _lines(
            headers["exceptions"],
            [
                item.text + (f" [scope: {item.scope}]" if item.scope else "") + (f" [steps: {', '.join(item.related_steps)}]" if item.related_steps else "")
                for item in record.exceptions
            ],
        )
    )
    lines.append("")
    lines.extend(
        _lines(
            headers["author_variants"],
            [
                f"{item.author} [{item.kind}]: {item.text}"
                + (f" [steps: {', '.join(item.related_steps)}]" if item.related_steps else "")
                for item in record.author_variants
            ],
        )
    )
    lines.append("")
    lines.extend(_lines(headers["procedure_outputs"], [item.text for item in record.procedure_outputs]))
    lines.append("")
    lines.extend(_lines(headers["terminology"], record.terminology))
    lines.append("")
    lines.extend(_lines(headers["relationships"], record.relationships))
    lines.append("")
    lines.extend(_lines(headers["examples"], record.examples))
    lines.append("")
    lines.extend(_lines(headers["ambiguities"], record.ambiguities))
    return "\n".join(lines)
