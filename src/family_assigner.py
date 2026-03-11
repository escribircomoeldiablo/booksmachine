"""Assign consolidated concepts into a fixed family catalog."""

from __future__ import annotations

import re

_MIN_PARTIAL_ALIAS_TOKENS = 2
_PARTIAL_MATCH_MIN_CONFIDENCE = 0.8
_HYBRID_RULE_CONFIDENCE = 0.95

_HYBRID_FAMILY_RULES: tuple[tuple[re.Pattern[str], tuple[str, ...]], ...] = (
    (re.compile(r"^(?:kurio|lord kurio of nativity|ruler of nativity|predominator apheta hyleg)$"), ("chart_authorities",)),
    (re.compile(r"^(?:al kadkhudah alcochoden)$"), ("chart_authorities",)),
    (re.compile(r"^(?:almuten|almuten al mubtazz)$"), ("chart_authorities", "dignities")),
    (re.compile(r"^(?:lot of fortune|fortune house|releasing house)$"), ("lots",)),
    (re.compile(r"^(?:derived houses)$"), ("house_systems",)),
    (re.compile(r"^(?:ascendant|mc midheaven|imum coeli ic|nadir)$"), ("chart_angles",)),
    (re.compile(r"^(?:bound lord|triplicity lord)$"), ("dignities",)),
    (re.compile(r"^(?:aspect|testimony|witnessing)$"), ("configuration",)),
)


def _normalize_text(value: str) -> str:
    normalized = value.lower().replace("-", " ")
    normalized = re.sub(r"[^a-z0-9\s]", " ", normalized)
    return " ".join(normalized.split()).strip()


def _tokenize(value: str) -> list[str]:
    return [token for token in _normalize_text(value).split() if token]


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _terminology_fields(payload: dict[str, object]) -> list[str]:
    values: list[str] = []
    field_values = payload.get("terminology", [])
    if isinstance(field_values, list):
        values.extend(value for value in field_values if isinstance(value, str))
    return values


def _family_aliases(family: dict[str, object]) -> list[str]:
    aliases = [str(family.get("label", "")).strip()]
    family_aliases = family.get("aliases", [])
    if isinstance(family_aliases, list):
        aliases.extend(alias for alias in family_aliases if isinstance(alias, str))
    return _dedupe_preserve_order([alias for alias in aliases if alias.strip()])


def _find_exact_matches(concept_label: str, family_index: list[dict[str, object]]) -> list[dict[str, object]]:
    normalized_label = _normalize_text(concept_label)
    matches: list[dict[str, object]] = []
    for family in family_index:
        if normalized_label in family["normalized_aliases"]:
            matches.append(
                {
                    "family_id": family["id"],
                    "family_label": family["label"],
                    "source": "alias_match",
                    "confidence": 1.0,
                }
            )
    return matches


def _alias_in_text(alias: str, text: str) -> bool:
    if not alias or not text:
        return False
    pattern = re.compile(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", re.IGNORECASE)
    return bool(pattern.search(text))


def _controlled_pattern_match(concept_label: str, family: dict[str, object]) -> bool:
    normalized_label = _normalize_text(concept_label)
    patterns = family.get("controlled_patterns", [])
    if not isinstance(patterns, list):
        return False
    for pattern in patterns:
        if not isinstance(pattern, str):
            continue
        normalized_pattern = _normalize_text(pattern)
        if normalized_pattern and _alias_in_text(normalized_pattern, normalized_label):
            return True
    return False


def _find_partial_matches(payload: dict[str, object], family_index: list[dict[str, object]]) -> list[dict[str, object]]:
    concept_label = str(payload.get("concept", "")).strip()
    label_text = _normalize_text(concept_label)
    terminology_fields = [_normalize_text(value) for value in _terminology_fields(payload)]
    matches: list[dict[str, object]] = []

    for family in family_index:
        best_score = 0.0
        for alias in family["normalized_aliases"]:
            alias_tokens = [token for token in alias.split() if token]
            if not alias_tokens:
                continue

            # Single-token aliases are too broad for partial assignment.
            if len(alias_tokens) < _MIN_PARTIAL_ALIAS_TOKENS:
                continue

            if _alias_in_text(alias, label_text):
                best_score = max(best_score, 0.9)
                continue

            if any(_alias_in_text(alias, field_text) for field_text in terminology_fields):
                best_score = max(best_score, 0.9)
                continue

        if _controlled_pattern_match(concept_label, family):
            best_score = max(best_score, 0.8)

        if best_score >= _PARTIAL_MATCH_MIN_CONFIDENCE:
            matches.append(
                {
                    "family_id": family["id"],
                    "family_label": family["label"],
                    "source": "phrase_match_strong" if best_score >= 0.9 else "controlled_pattern_match",
                    "confidence": best_score,
                }
            )

    matches.sort(key=lambda item: (-float(item["confidence"]), str(item["family_id"])))
    return matches[:2]


def _find_hybrid_rule_matches(payload: dict[str, object], family_index: list[dict[str, object]]) -> list[dict[str, object]]:
    concept_label = _normalize_text(str(payload.get("concept", "")).strip())
    if not concept_label:
        return []
    family_labels = {str(item["id"]): str(item["label"]) for item in family_index}
    matches: list[dict[str, object]] = []
    for pattern, family_ids in _HYBRID_FAMILY_RULES:
        if not pattern.match(concept_label):
            continue
        for family_id in family_ids:
            label = family_labels.get(family_id, family_id)
            matches.append(
                {
                    "family_id": family_id,
                    "family_label": label,
                    "source": "hybrid_rule",
                    "confidence": _HYBRID_RULE_CONFIDENCE,
                }
            )
    matches.sort(key=lambda item: (-float(item["confidence"]), str(item["family_id"])))
    return matches


def assign_families(
    concepts: dict[str, dict[str, object]],
    families_catalog: list[dict[str, object]],
) -> dict[str, object]:
    """Assign each concept to zero, one, or two predefined families."""
    family_index: list[dict[str, object]] = []
    for family in families_catalog:
        aliases = _family_aliases(family)
        family_index.append(
            {
                "id": str(family.get("id", "")).strip(),
                "label": str(family.get("label", "")).strip(),
                "normalized_aliases": {_normalize_text(alias) for alias in aliases if alias.strip()},
                "controlled_patterns": [
                    str(pattern).strip()
                    for pattern in family.get("controlled_patterns", [])
                    if isinstance(pattern, str) and str(pattern).strip()
                ],
            }
        )

    grouped_members: dict[str, dict[str, object]] = {}
    concept_assignments: list[dict[str, object]] = []
    unassigned_concepts: list[str] = []

    for concept_name in sorted(concepts):
        payload = concepts[concept_name]
        exact_matches = _find_exact_matches(concept_name, family_index)
        partial_matches = [] if exact_matches else _find_partial_matches(payload, family_index)
        hybrid_matches = _find_hybrid_rule_matches(payload, family_index)
        matches = exact_matches or partial_matches
        combined: list[dict[str, object]] = []
        seen_family_ids: set[str] = set()
        for match in list(matches) + list(hybrid_matches):
            family_id = str(match["family_id"])
            if family_id in seen_family_ids:
                continue
            seen_family_ids.add(family_id)
            combined.append(match)
        combined.sort(key=lambda item: (-float(item["confidence"]), str(item["family_id"])))
        matches = combined[:2]

        if not matches:
            unassigned_concepts.append(concept_name)
            continue

        concept_assignments.append(
            {
                "concept": concept_name,
                "families": [
                    {
                        "family_id": match["family_id"],
                        "source": match["source"],
                        "confidence": match["confidence"],
                    }
                    for match in matches[:2]
                ],
            }
        )

        for match in matches[:2]:
            bucket = grouped_members.setdefault(
                str(match["family_id"]),
                {
                    "family_id": match["family_id"],
                    "label": match["family_label"],
                    "members": [],
                },
            )
            bucket["members"] = _dedupe_preserve_order(list(bucket["members"]) + [concept_name])

    families = sorted(grouped_members.values(), key=lambda item: str(item["family_id"]))
    concept_assignments.sort(key=lambda item: str(item["concept"]))

    return {
        "families": families,
        "concept_assignments": concept_assignments,
        "unassigned_concepts": unassigned_concepts,
    }
