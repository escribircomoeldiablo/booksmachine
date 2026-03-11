from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .knowledge_schema import SectionRef

ARGUMENT_CHUNK_SCHEMA_VERSION = "1.0.0"
ARGUMENT_MAP_SCHEMA_VERSION = "1.0.0"


@dataclass(slots=True)
class ArgumentChunkV1:
    schema_version: str
    chunk_id: str
    source_fingerprint: str
    section_refs: list[SectionRef] = field(default_factory=list)
    theses: list[str] = field(default_factory=list)
    claims: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    methods: list[str] = field(default_factory=list)
    authors_or_schools: list[str] = field(default_factory=list)
    key_terms: list[str] = field(default_factory=list)
    debates: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["schema_version"] = str(payload["schema_version"])
        return payload


def make_empty_argument_chunk(
    *,
    chunk_id: str,
    source_fingerprint: str,
    section_refs: list[SectionRef] | None = None,
) -> ArgumentChunkV1:
    return ArgumentChunkV1(
        schema_version=ARGUMENT_CHUNK_SCHEMA_VERSION,
        chunk_id=chunk_id,
        source_fingerprint=source_fingerprint,
        section_refs=list(section_refs or []),
        theses=[],
        claims=[],
        evidence=[],
        methods=[],
        authors_or_schools=[],
        key_terms=[],
        debates=[],
        limitations=[],
    )
