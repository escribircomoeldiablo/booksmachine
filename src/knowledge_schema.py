"""Canonical schema for chunk-level technical knowledge extraction."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

CHUNK_KNOWLEDGE_SCHEMA_VERSION = "1.0.0"


@dataclass(slots=True)
class SectionRef:
    label: str
    type: str
    start_char: int
    end_char: int


@dataclass(slots=True)
class ChunkKnowledgeV1:
    schema_version: str
    chunk_id: str
    source_fingerprint: str
    section_refs: list[SectionRef] = field(default_factory=list)
    concepts: list[str] = field(default_factory=list)
    definitions: list[str] = field(default_factory=list)
    technical_rules: list[str] = field(default_factory=list)
    procedures: list[str] = field(default_factory=list)
    terminology: list[str] = field(default_factory=list)
    relationships: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    ambiguities: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        """Serialize to a plain dict for JSONL persistence."""
        payload = asdict(self)
        payload["schema_version"] = str(payload["schema_version"])
        return payload


def make_empty_chunk_knowledge(
    *,
    chunk_id: str,
    source_fingerprint: str,
    section_refs: list[SectionRef] | None = None,
) -> ChunkKnowledgeV1:
    """Return a valid empty knowledge record for controlled fallback."""
    return ChunkKnowledgeV1(
        schema_version=CHUNK_KNOWLEDGE_SCHEMA_VERSION,
        chunk_id=chunk_id,
        source_fingerprint=source_fingerprint,
        section_refs=list(section_refs or []),
        concepts=[],
        definitions=[],
        technical_rules=[],
        procedures=[],
        terminology=[],
        relationships=[],
        examples=[],
        ambiguities=[],
    )
