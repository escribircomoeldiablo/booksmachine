"""Deterministic validation for LLM-proposed family candidates."""

from __future__ import annotations


_GENERIC_LABELS = {
    "thing",
    "things",
    "concept",
    "concepts",
    "category",
    "categories",
    "relation",
    "relations",
    "condition",
    "conditions",
    "group",
    "groups",
}
_GENERIC_LABEL_TOKENS = {
    "concept",
    "concepts",
    "property",
    "properties",
    "term",
    "terms",
    "related",
    "misc",
    "miscellaneous",
    "general",
}
_PROTECTED_BASE_CONCEPTS = {
    "angle",
    "angularity",
    "benefic",
    "malefic",
    "gender",
    "hour",
    "joy",
    "house system",
}


def _normalize_text(value: str) -> str:
    return " ".join(value.lower().replace("-", " ").split()).strip()


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _existing_family_surfaces(
    existing_catalog: list[dict[str, object]] | None,
    existing_families: dict[str, object] | None,
) -> set[str]:
    surfaces: set[str] = set()
    for family in existing_catalog or []:
        label = str(family.get("label", "")).strip()
        if label:
            surfaces.add(_normalize_text(label))
        aliases = family.get("aliases", [])
        if isinstance(aliases, list):
            for alias in aliases:
                if isinstance(alias, str) and alias.strip():
                    surfaces.add(_normalize_text(alias))

    for family in (existing_families or {}).get("families", []):
        if not isinstance(family, dict):
            continue
        label = str(family.get("label", "")).strip()
        if label:
            surfaces.add(_normalize_text(label))
    return surfaces


def _label_is_too_generic(label: str) -> bool:
    normalized = _normalize_text(label)
    if normalized in _GENERIC_LABELS:
        return True
    tokens = set(normalized.split())
    return bool(tokens.intersection(_GENERIC_LABEL_TOKENS))


def validate_candidate_families(
    raw_payload: dict[str, object],
    *,
    unassigned_concepts: list[str],
    existing_catalog: list[dict[str, object]] | None = None,
    existing_families: dict[str, object] | None = None,
    minimum_family_size: int = 3,
    small_family_allowlist: set[str] | None = None,
) -> dict[str, object]:
    """Validate and normalize candidate families proposed by discovery."""
    known_concepts = {concept_name for concept_name in unassigned_concepts if isinstance(concept_name, str)}
    accepted: list[dict[str, object]] = []
    rejected: list[dict[str, object]] = []
    assigned_members: set[str] = set()
    family_surfaces = _existing_family_surfaces(existing_catalog, existing_families)
    allow_small = {_normalize_text(label) for label in (small_family_allowlist or set())}

    raw_candidates = raw_payload.get("candidate_families", [])
    if not isinstance(raw_candidates, list):
        raw_candidates = []

    for item in raw_candidates:
        if not isinstance(item, dict):
            continue
        family_label = str(item.get("family_label", "")).strip()
        normalized_label = _normalize_text(family_label)
        members = item.get("members", [])
        rationale = str(item.get("rationale", "")).strip()
        reasons: list[str] = []

        if not family_label:
            rejected.append({"family_label": family_label, "members": [], "reasons": ["missing_family_label"]})
            continue
        if _label_is_too_generic(family_label):
            reasons.append("label_too_generic")
        if normalized_label in family_surfaces:
            reasons.append("possible_merge_with_existing_family")

        if not isinstance(members, list):
            rejected.append({"family_label": family_label, "members": [], "reasons": reasons + ["members_not_a_list"]})
            continue

        normalized_members = [member.strip() for member in members if isinstance(member, str) and member.strip()]
        deduped_members = _dedupe_preserve_order(normalized_members)
        invalid_members = [member for member in deduped_members if member not in known_concepts]
        if invalid_members:
            reasons.append("contains_unknown_members")
        candidate_members = [member for member in deduped_members if member in known_concepts]
        protected_members = [member for member in candidate_members if _normalize_text(member) in _PROTECTED_BASE_CONCEPTS]
        if protected_members:
            reasons.append("contains_protected_base_concepts")
        non_colliding_members = [member for member in candidate_members if member not in assigned_members]
        if len(non_colliding_members) < len(candidate_members):
            reasons.append("member_collision_across_candidates")

        final_members = non_colliding_members
        if len(final_members) < minimum_family_size and normalized_label not in allow_small:
            reasons.append("family_too_small")
        if not final_members:
            reasons.append("no_coverage_gain")

        if reasons:
            rejected.append(
                {
                    "family_label": family_label,
                    "members": final_members,
                    "reasons": _dedupe_preserve_order(reasons),
                }
            )
            continue

        assigned_members.update(final_members)
        accepted.append(
            {
                "family_label": family_label,
                "members": final_members,
                "rationale": rationale,
                "promotion_hint": "review_for_domain_catalog",
                "validation": {
                    "accepted": True,
                    "reasons": ["member_count_ok", "all_members_known", "non_colliding"],
                },
            }
        )

    left_unclustered = [concept_name for concept_name in unassigned_concepts if concept_name not in assigned_members]
    return {
        "candidate_families": accepted,
        "rejected_candidates": rejected,
        "left_unclustered": left_unclustered,
        "summary": {
            "input_unassigned_count": len(unassigned_concepts),
            "candidate_count_raw": len(raw_candidates),
            "candidate_count_accepted": len(accepted),
            "left_unclustered_count": len(left_unclustered),
        },
        "discovery_error": raw_payload.get("discovery_error"),
    }
