from __future__ import annotations

from .argument_schema import ArgumentChunkV1


def _header(label_es: str, label_original: str, output_language: str) -> str:
    return label_original if output_language == "original" else label_es


def render_argument_chunk_summary(
    argument_chunk: ArgumentChunkV1,
    output_language: str = "es",
) -> str:
    sections = (
        (_header("TESIS", "THESES", output_language), argument_chunk.theses),
        (_header("CLAIMS", "CLAIMS", output_language), argument_chunk.claims),
        (_header("EVIDENCIA", "EVIDENCE", output_language), argument_chunk.evidence),
        (_header("METODOS", "METHODS", output_language), argument_chunk.methods),
        (_header("DEBATES", "DEBATES", output_language), argument_chunk.debates),
        (_header("LIMITACIONES", "LIMITATIONS", output_language), argument_chunk.limitations),
        (_header("AUTORES O ESCUELAS", "AUTHORS OR SCHOOLS", output_language), argument_chunk.authors_or_schools),
        (_header("TERMINOS CLAVE", "KEY TERMS", output_language), argument_chunk.key_terms),
    )
    lines: list[str] = []
    for title, items in sections:
        if not items:
            continue
        lines.append(title)
        lines.extend(f"- {item}" for item in items)
        lines.append("")
    if not lines:
        return _header("SIN ESTRUCTURA ARGUMENTAL CLARA", "NO CLEAR ARGUMENTATIVE STRUCTURE", output_language)
    return "\n".join(lines[:-1])


def render_argument_block_input(
    argument_chunks: list[ArgumentChunkV1],
    output_language: str = "es",
) -> list[str]:
    return [render_argument_chunk_summary(chunk, output_language=output_language) for chunk in argument_chunks]
