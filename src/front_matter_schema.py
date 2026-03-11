"""Canonical schema for front matter structural hypothesis artifacts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

FRONT_MATTER_OUTLINE_SCHEMA_VERSION = "1.0.0"

SourceStrategy = Literal["document_map", "early_headings", "initial_excerpt", "mixed"]
CandidateStatus = Literal["candidate"]
ConceptPriority = Literal["high", "medium", "low"]


@dataclass(slots=True)
class FrontMatterSource:
    has_toc: bool = False
    has_introduction: bool = False
    has_preface: bool = False
    strategy: SourceStrategy = "initial_excerpt"


@dataclass(slots=True)
class FamilyCandidate:
    name: str
    aliases: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    confidence: float = 0.0
    status: CandidateStatus = "candidate"


@dataclass(slots=True)
class CoreConceptExpected:
    name: str
    evidence: list[str] = field(default_factory=list)
    priority: ConceptPriority = "medium"


@dataclass(slots=True)
class ProvisionalTaxonomyLink:
    parent: str
    child: str
    relation_type: str
    confidence: float = 0.0


@dataclass(slots=True)
class NormalizationHint:
    canonical: str
    variants: list[str] = field(default_factory=list)


@dataclass(slots=True)
class FrontMatterOutlineV1:
    schema_version: str
    book_title: str
    source: FrontMatterSource
    family_candidates: list[FamilyCandidate] = field(default_factory=list)
    core_concepts_expected: list[CoreConceptExpected] = field(default_factory=list)
    provisional_taxonomy: list[ProvisionalTaxonomyLink] = field(default_factory=list)
    normalization_hints: list[NormalizationHint] = field(default_factory=list)
    confidence_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["schema_version"] = str(payload["schema_version"])
        return payload


def make_empty_front_matter_outline(
    *,
    book_title: str,
    source: FrontMatterSource | None = None,
    confidence_notes: list[str] | None = None,
) -> FrontMatterOutlineV1:
    return FrontMatterOutlineV1(
        schema_version=FRONT_MATTER_OUTLINE_SCHEMA_VERSION,
        book_title=book_title.strip(),
        source=source or FrontMatterSource(),
        family_candidates=[],
        core_concepts_expected=[],
        provisional_taxonomy=[],
        normalization_hints=[],
        confidence_notes=list(confidence_notes or []),
    )
