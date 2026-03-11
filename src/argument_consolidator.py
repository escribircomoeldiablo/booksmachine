from __future__ import annotations

from .argument_schema import ARGUMENT_MAP_SCHEMA_VERSION, ArgumentChunkV1


def _normalize_space(value: str) -> str:
    return " ".join(value.split()).strip()


def _comparison_key(value: str) -> str:
    return _normalize_space(value).lower()


def _dedupe_preserve_surface(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        normalized = _normalize_space(item)
        if not normalized:
            continue
        key = _comparison_key(normalized)
        if key in seen:
            continue
        seen.add(key)
        output.append(normalized)
    return output


def build_argument_map(
    records: list[ArgumentChunkV1],
    *,
    source_title: str,
    audit_rows: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    rows = list(audit_rows or [])
    primary_theses = _dedupe_preserve_surface([item for record in records for item in record.theses])
    recurring_claims = _dedupe_preserve_surface([item for record in records for item in record.claims])
    evidence_patterns = _dedupe_preserve_surface([item for record in records for item in record.evidence])
    methods_detected = _dedupe_preserve_surface([item for record in records for item in record.methods])
    authors_or_schools = _dedupe_preserve_surface([item for record in records for item in record.authors_or_schools])
    key_terms = _dedupe_preserve_surface([item for record in records for item in record.key_terms])
    major_debates = _dedupe_preserve_surface([item for record in records for item in record.debates])
    limitations = _dedupe_preserve_surface([item for record in records for item in record.limitations])
    fallback_chunks = sum(
        1 for row in rows if str(row.get("decision")) in {"parse_fallback", "llm_empty", "invalid_payload"}
    )
    empty_chunks = sum(1 for row in rows if str(row.get("decision")) == "empty_legitimate")
    return {
        "map_schema_version": ARGUMENT_MAP_SCHEMA_VERSION,
        "source_title": source_title,
        "chunk_schema_version": records[0].schema_version if records else None,
        "primary_theses": primary_theses,
        "recurring_claims": recurring_claims,
        "evidence_patterns": evidence_patterns,
        "methods_detected": methods_detected,
        "authors_or_schools": authors_or_schools,
        "key_terms": key_terms,
        "major_debates": major_debates,
        "limitations": limitations,
        "source_coverage": {
            "total_chunks": len(records),
            "chunks_with_theses": sum(1 for record in records if record.theses),
            "chunks_with_claims": sum(1 for record in records if record.claims),
            "chunks_with_evidence": sum(1 for record in records if record.evidence),
            "chunks_with_methods": sum(1 for record in records if record.methods),
            "chunks_with_debates": sum(1 for record in records if record.debates),
            "chunks_with_limitations": sum(1 for record in records if record.limitations),
            "fallback_chunks": fallback_chunks,
            "empty_chunks": empty_chunks,
        },
    }
