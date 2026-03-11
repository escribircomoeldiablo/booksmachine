from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BookProfile:
    profile_name: str
    chunk_extraction_mode: str
    structured_artifact_family: str
    enable_procedural: bool
    enable_family_discovery: bool
    enable_taxonomy: bool
    enable_ontology: bool
    enable_argument_map: bool


MANUAL_PROFILE = BookProfile(
    profile_name="manual",
    chunk_extraction_mode="manual",
    structured_artifact_family="knowledge",
    enable_procedural=True,
    enable_family_discovery=True,
    enable_taxonomy=True,
    enable_ontology=True,
    enable_argument_map=False,
)

ARGUMENTATIVE_PROFILE = BookProfile(
    profile_name="argumentative",
    chunk_extraction_mode="argumentative",
    structured_artifact_family="argument",
    enable_procedural=False,
    enable_family_discovery=False,
    enable_taxonomy=False,
    enable_ontology=False,
    enable_argument_map=True,
)


def get_book_profile(value: str) -> BookProfile:
    normalized = value.strip().lower()
    if normalized == "manual":
        return MANUAL_PROFILE
    if normalized == "argumentative":
        return ARGUMENTATIVE_PROFILE
    raise ValueError("profile must be either 'manual' or 'argumentative'")
