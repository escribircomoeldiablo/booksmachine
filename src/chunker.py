"""Split long text into deterministic overlapping chunks."""

from __future__ import annotations


def _validate(chunk_size: int, overlap: int) -> None:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")
    if overlap < 0:
        raise ValueError("overlap must be 0 or greater")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")


def _find_split_point(text: str, start: int, target_end: int) -> int:
    window = text[start:target_end]
    search_from = max(0, len(window) - 300)
    tail = window[search_from:]

    best_local = -1
    for marker in (". ", "\n", " "):
        idx = tail.rfind(marker)
        if idx > best_local:
            best_local = idx + len(marker)

    if best_local <= 0:
        return target_end

    return start + search_from + best_local


def split_into_chunks(
    text: str,
    chunk_size: int = 1800,
    overlap: int = 200,
) -> list[str]:
    """Split text into ordered chunks using character windows with overlap."""
    _validate(chunk_size, overlap)

    normalized = text.strip()
    if not normalized:
        return []

    text_len = len(normalized)
    if text_len <= chunk_size:
        return [normalized]

    chunks: list[str] = []
    start = 0

    while start < text_len:
        target_end = min(start + chunk_size, text_len)
        end = _find_split_point(normalized, start, target_end)
        if end <= start:
            end = target_end

        in_terminal_window = target_end == text_len
        candidate_start = end - overlap
        if in_terminal_window and end < text_len and candidate_start <= start:
            end = text_len
        elif in_terminal_window and end < text_len:
            remaining = text_len - end
            if remaining <= overlap:
                end = text_len

        piece = normalized[start:end].strip()
        if piece:
            chunks.append(piece)

        if end >= text_len:
            break

        candidate_start = max(0, end - overlap)
        next_start = max(candidate_start, start + 1)
        start = min(next_start, text_len)

    return chunks
