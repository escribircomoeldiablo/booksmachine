"""Prompt construction and chunk summarization helpers."""

from __future__ import annotations

from .ai_client import ask_llm


def build_summary_prompt(chunk_text: str) -> str:
    """Build a structured technical-summary prompt for one chunk."""
    return (
        "You are a technical reading assistant. Analyze the text chunk and produce "
        "a concise structured summary.\n\n"
        "Return bullet points under these sections:\n"
        "- Main concepts\n"
        "- Definitions\n"
        "- Principles\n"
        "- Important rules\n\n"
        "Keep it factual, clear, and based only on the provided text.\n\n"
        "Text chunk:\n"
        f"{chunk_text}"
    )


def summarize_chunk(chunk_text: str) -> str:
    """Summarize one text chunk using the LLM client."""
    prompt = build_summary_prompt(chunk_text)
    return ask_llm(prompt)
