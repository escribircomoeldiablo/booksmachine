"""Typed records for structural chunking."""

from __future__ import annotations

from typing import TypedDict


class ChunkRecord(TypedDict):
    chunk_index: int
    chunk_id: str
    section_id: str
    section_index: int
    start_char: int
    end_char: int
    start_page: int | None
    end_page: int | None
    text: str


class ChunkStats(TypedDict):
    total_chunks: int
    avg_chunk_size: float
    sections_consumed: int
    sections_split: int
    sections_merged: int


class ChunkSet(TypedDict):
    chunks: list[ChunkRecord]
    stats: ChunkStats
