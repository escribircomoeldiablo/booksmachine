"""Minimal LLM client wrapper for summary generation."""

from __future__ import annotations

import time

from .config import (
    MODEL_NAME,
    OPENAI_API_KEY,
    OPENAI_MAX_RETRIES,
    OPENAI_RETRY_BACKOFF_SECONDS,
    OPENAI_TIMEOUT_SECONDS,
)

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
    return OpenAI(api_key=OPENAI_API_KEY, timeout=OPENAI_TIMEOUT_SECONDS)  # type: ignore[misc]


def _request_with_retry(client: OpenAI, prompt: str) -> str:  # type: ignore[valid-type]
    last_error: Exception | None = None
    max_retries = max(1, OPENAI_MAX_RETRIES)
    backoff_base = max(0.1, OPENAI_RETRY_BACKOFF_SECONDS)

    for attempt in range(1, max_retries + 1):
        try:
            response = client.responses.create(model=MODEL_NAME, input=prompt)
            text = (response.output_text or "").strip()
            if not text:
                raise RuntimeError("LLM returned an empty response.")
            return text
        except Exception as exc:  # pragma: no cover
            last_error = exc
            if attempt < max_retries:
                time.sleep(backoff_base * (2 ** (attempt - 1)))

    raise RuntimeError(f"LLM request failed after {max_retries} attempts: {last_error}")


def ask_llm(prompt: str) -> str:
    """Send a prompt to the LLM and return plain text output."""
    _validate_prereqs()
    client = _build_client()
    return _request_with_retry(client, prompt)
