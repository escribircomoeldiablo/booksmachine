"""Minimal LLM client wrapper for summary generation."""

from __future__ import annotations

import time

from .config import MODEL_NAME, OPENAI_API_KEY

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None  # type: ignore[assignment]


def _validate_prereqs() -> None:
    if not OPENAI_API_KEY:
        raise RuntimeError("Missing OPENAI_API_KEY environment variable.")

    if OpenAI is None:
        raise RuntimeError(
            "OpenAI SDK is not installed. Install dependency 'openai' to continue."
        )


def _build_client() -> OpenAI:  # type: ignore[valid-type]
    return OpenAI(api_key=OPENAI_API_KEY, timeout=20.0)  # type: ignore[misc]


def _request_with_retry(client: OpenAI, prompt: str) -> str:  # type: ignore[valid-type]
    last_error: Exception | None = None

    for attempt in range(1, 4):
        try:
            response = client.responses.create(model=MODEL_NAME, input=prompt)
            text = (response.output_text or "").strip()
            if not text:
                raise RuntimeError("LLM returned an empty response.")
            return text
        except Exception as exc:  # pragma: no cover
            last_error = exc
            if attempt < 3:
                time.sleep(0.8 * attempt)

    raise RuntimeError(f"LLM request failed after 3 attempts: {last_error}")


def ask_llm(prompt: str) -> str:
    """Send a prompt to the LLM and return plain text output."""
    _validate_prereqs()
    client = _build_client()
    return _request_with_retry(client, prompt)
