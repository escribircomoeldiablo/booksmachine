"""Prompt construction and chunk summarization helpers."""

from __future__ import annotations

from .ai_client import ask_llm


def _output_style(output_language: str) -> str:
    if output_language == "original":
        return (
            "Escribe la respuesta en el idioma original del fragmento y evita traducir "
            "terminos salvo que sea estrictamente necesario para claridad."
        )
    return (
        "Escribe la respuesta en espanol claro y natural. Conserva sin traducir palabras "
        "en latin o terminos que por contexto deban quedar en su idioma original."
    )


def build_summary_prompt(chunk_text: str, output_language: str = "es") -> str:
    """Build a structured technical-summary prompt for one chunk."""
    return (
        "Eres un asistente de lectura tecnica. Analiza el fragmento de texto y produce "
        "un resumen estructurado y conciso.\n\n"
        f"{_output_style(output_language)}\n\n"
        "Devuelve puntos bajo estas secciones:\n"
        "- Conceptos principales\n"
        "- Definiciones\n"
        "- Principios\n"
        "- Reglas importantes\n\n"
        "Manten el contenido factual, claro y basado solo en el texto proporcionado.\n\n"
        "Fragmento de texto:\n"
        f"{chunk_text}"
    )


def summarize_chunk(chunk_text: str, output_language: str = "es") -> str:
    """Summarize one text chunk using the LLM client."""
    prompt = build_summary_prompt(chunk_text, output_language=output_language)
    return ask_llm(prompt)
