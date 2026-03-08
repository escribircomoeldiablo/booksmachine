"""Prompt construction and chunk summarization helpers."""

from __future__ import annotations

from .ai_client import ask_llm


def build_summary_prompt(chunk_text: str) -> str:
    """Build a structured technical-summary prompt for one chunk."""
    return (
        "Eres un asistente de lectura tecnica. Analiza el fragmento de texto y produce "
        "un resumen estructurado y conciso en espanol.\n\n"
        "Devuelve puntos bajo estas secciones:\n"
        "- Conceptos principales\n"
        "- Definiciones\n"
        "- Principios\n"
        "- Reglas importantes\n\n"
        "Manten el contenido factual, claro y basado solo en el texto proporcionado.\n\n"
        "Si aparecen palabras en latin o terminos que por contexto deban quedar en su idioma "
        "original, conservalos sin traducir.\n\n"
        "Fragmento de texto:\n"
        f"{chunk_text}"
    )


def summarize_chunk(chunk_text: str) -> str:
    """Summarize one text chunk using the LLM client."""
    prompt = build_summary_prompt(chunk_text)
    return ask_llm(prompt)
