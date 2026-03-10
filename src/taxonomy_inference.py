"""Deterministic taxonomy link inference from canonical concept payloads."""

from __future__ import annotations

import re

_DEFINITION_HEAD_RE = re.compile(r"^\s*([^:]+):\s+.+$")
_NORMALIZE_SPACE_RE = re.compile(r"\s+")
_PARENT_CLASSIFICATION_HINTS: tuple[str, ...] = (
    "classification",
    "classifications",
    "angularity",
    "favorability",
    "division",
    "divisions",
    "type",
    "types",
)
_NON_TAXONOMIC_PARENT_SUFFIXES: tuple[str, ...] = (
    "system",
    "systems",
    "degree",
    "degrees",
)
_UNSAFE_HEAD_TOKENS: tuple[str, ...] = (
    "system",
    "systems",
)
_SPECIFIC_POSITION_MARKERS: tuple[str, ...] = (
    "first house",
    "second house",
    "third house",
    "fourth house",
    "fifth house",
    "sixth house",
    "seventh house",
    "eighth house",
    "ninth house",
    "tenth house",
    "eleventh house",
    "twelfth house",
    "mc degree",
    "ascendant degree",
)
_IGNORABLE_TOKENS: frozenset[str] = frozenset({"of", "the", "a", "an", "in"})
_HOUSE_AXIS_GROUPS: tuple[frozenset[str], ...] = (
    frozenset({"angular", "succedent", "cadent"}),
    frozenset({"benefic", "malefic"}),
)
_CLASSIFICATION_MARKERS: tuple[str, ...] = (
    " include",
    " includes",
    " including",
    " consists of",
    " comprise",
    " comprises",
    " are the",
    " are classified as",
    " are classified into",
    " are divided into",
    " belong to",
)
_EXPLICIT_TAXONOMY_FAMILIES: dict[str, dict[str, object]] = {
    "angularity of house": {
        "children": ("angular houses", "succedent houses", "cadent houses"),
        "min_children": 3,
    },
    "house angularity": {
        "children": ("angular houses", "succedent houses", "cadent houses"),
        "min_children": 3,
    },
    "angularity": {
        "children": ("angular houses", "succedent houses", "cadent houses"),
        "min_children": 3,
    },
    "favorability of house": {
        "children": ("benefic houses", "malefic houses"),
        "min_children": 2,
    },
    "house classification": {
        "children": ("angular houses", "succedent houses", "cadent houses"),
        "min_children": 3,
    },
}


def _normalize_text(value: str) -> str:
    return _NORMALIZE_SPACE_RE.sub(" ", value.lower()).strip()


def _contains_exact_term(value: str, term: str) -> bool:
    pattern = re.compile(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", re.IGNORECASE)
    return bool(pattern.search(value))


def _definition_head(value: str) -> str | None:
    match = _DEFINITION_HEAD_RE.match(value)
    if not match:
        return None
    return _normalize_text(match.group(1))


def _looks_taxonomic_parent(value: str) -> bool:
    normalized = _normalize_text(value)
    if " and " in normalized or " or " in normalized:
        return False
    if any(marker in normalized for marker in _SPECIFIC_POSITION_MARKERS):
        return False
    if normalized.endswith(_NON_TAXONOMIC_PARENT_SUFFIXES):
        return False
    return any(hint in normalized for hint in _PARENT_CLASSIFICATION_HINTS)


def _supports_multi_child_taxonomy(value: str) -> bool:
    normalized = _normalize_text(value)
    if " and " in normalized or " or " in normalized:
        return False
    if any(marker in normalized for marker in _SPECIFIC_POSITION_MARKERS):
        return False
    if "house" not in normalized and "houses" not in normalized:
        return False
    return not normalized.endswith(_NON_TAXONOMIC_PARENT_SUFFIXES)


def _relationship_supports_taxonomy(value: str, child: str) -> bool:
    normalized = _normalize_text(value)
    if not _contains_exact_term(normalized, child):
        return False
    if " but " in normalized or " versus " in normalized or " vs " in normalized:
        return False
    return any(marker in normalized for marker in _CLASSIFICATION_MARKERS)


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _tokenize(value: str) -> list[str]:
    return [token for token in _normalize_text(value).split() if token]


def _signature_tokens(value: str) -> tuple[str, ...]:
    return tuple(token for token in _tokenize(value) if token not in _IGNORABLE_TOKENS)


def _family_sort_key(child_names: list[str]) -> tuple[int, int, str, tuple[str, ...]]:
    shared_head = _shared_head_token(child_names) or ""
    structural_support = 0
    for child_name in child_names:
        tokens = _signature_tokens(child_name)
        structural_support += len(tokens)
    return (
        -len(child_names),
        -structural_support,
        shared_head,
        tuple(sorted(child_names)),
    )


def _shared_head_token(child_names: list[str]) -> str | None:
    tokenized = [_signature_tokens(child_name) for child_name in child_names]
    if not tokenized or any(not tokens for tokens in tokenized):
        return None
    head = tokenized[0][-1]
    if any(tokens[-1] != head for tokens in tokenized[1:]):
        return None
    return head


def _parallel_child_forms(child_names: list[str]) -> bool:
    tokenized = [_signature_tokens(child_name) for child_name in child_names]
    if not tokenized or any(len(tokens) < 2 for tokens in tokenized):
        return False
    lengths = {len(tokens) for tokens in tokenized}
    if len(lengths) != 1:
        return False
    head = tokenized[0][-1]
    if any(tokens[-1] != head for tokens in tokenized[1:]):
        return False
    return True


def _violates_house_axis_safeguard(child_names: list[str], *, head: str) -> bool:
    if head != "houses":
        return False
    modifiers = {tokens[0] for tokens in (_signature_tokens(child_name) for child_name in child_names) if len(tokens) >= 2}
    active_groups = 0
    for group in _HOUSE_AXIS_GROUPS:
        if modifiers & group:
            active_groups += 1
    return active_groups > 1


def _select_coherent_family(links: list[dict[str, object]]) -> list[dict[str, object]]:
    families: dict[tuple[str, int], list[dict[str, object]]] = {}
    for link in links:
        child_name = str(link["child"])
        signature = _signature_tokens(child_name)
        if len(signature) < 2:
            continue
        family_key = (signature[-1], len(signature))
        families.setdefault(family_key, []).append(link)

    coherent_families: list[list[dict[str, object]]] = []
    for family_links in families.values():
        child_names = [str(link["child"]) for link in family_links]
        head = _shared_head_token(child_names)
        if head is None or head in _UNSAFE_HEAD_TOKENS:
            continue
        if not _parallel_child_forms(child_names):
            continue
        unique_children = {str(link["child"]) for link in family_links}
        if len(unique_children) < 2:
            continue
        if _violates_house_axis_safeguard(sorted(unique_children), head=head):
            continue
        coherent_families.append(sorted(family_links, key=lambda item: str(item["child"])))

    if not coherent_families:
        return []

    coherent_families.sort(key=lambda family: _family_sort_key([str(link["child"]) for link in family]))
    return coherent_families[0]


def _new_candidate(
    *,
    parent: str,
    child: str,
    source_chunks: list[int],
) -> dict[str, object]:
    return {
        "parent": parent,
        "child": child,
        "signals": [],
        "evidence": [],
        "source_chunks": list(source_chunks),
    }


def _source_chunk_set(payload: dict[str, object]) -> set[int]:
    chunks: set[int] = set()
    for chunk in payload.get("source_chunks", []):
        try:
            chunks.add(int(chunk))
        except (TypeError, ValueError):
            continue
    return chunks


def _terminology_supports_structural_family(
    parent_payload: dict[str, object],
    *,
    child_name: str,
) -> list[str]:
    evidence: list[str] = []
    for term in parent_payload.get("terminology", []):
        if not isinstance(term, str):
            continue
        if _contains_exact_term(_normalize_text(term), child_name):
            evidence.append(term)
    return _dedupe_preserve_order(evidence)


def _candidate_sort_key(candidate: dict[str, object]) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    return (
        str(candidate["child"]),
        tuple(str(signal) for signal in candidate["signals"]),
        tuple(str(evidence) for evidence in candidate["evidence"]),
    )


def _family_rejection_reason(
    *,
    parent_name: str,
    family_links: list[dict[str, object]],
    parent_candidates: list[dict[str, object]],
) -> str | None:
    parent_child_count = len({str(candidate["child"]) for candidate in parent_candidates})
    parent_taxonomic = _looks_taxonomic_parent(parent_name)
    parent_multi_child = _supports_multi_child_taxonomy(parent_name)
    relationship_supported = any("relationship_pattern" in link["signals"] for link in family_links)
    if not parent_taxonomic and not (parent_multi_child and parent_child_count >= 2):
        return "parent_not_taxonomic"

    unique_children = sorted({str(link["child"]) for link in family_links})
    if len(unique_children) < 2:
        return "family_single_child"

    head = _shared_head_token(unique_children)
    if head is None:
        if any(len(_signature_tokens(child_name)) < 2 for child_name in unique_children):
            return "child_signature_too_short"
        return "family_no_shared_head"
    if head in _UNSAFE_HEAD_TOKENS:
        return "family_unsafe_head"
    if not _parallel_child_forms(unique_children):
        return "family_non_parallel"
    if _violates_house_axis_safeguard(unique_children, head=head):
        return "family_mixed_axes"

    if parent_taxonomic:
        if relationship_supported or parent_child_count >= 2:
            return None
        return "parent_insufficient_support"
    return None


def _build_candidate_audit_row(
    candidate: dict[str, object],
    *,
    decision: str,
    rejection_reason: str | None = None,
    acceptance_reason: str | None = None,
) -> dict[str, object]:
    row = {
        "parent": str(candidate["parent"]),
        "child": str(candidate["child"]),
        "signals": list(candidate["signals"]),
        "evidence": list(candidate["evidence"]),
        "source_chunks": list(candidate["source_chunks"]),
        "decision": decision,
    }
    if rejection_reason is not None:
        row["rejection_reason"] = rejection_reason
    if acceptance_reason is not None:
        row["acceptance_reason"] = acceptance_reason
    return row


def _explicit_family_reason(
    *,
    parent_name: str,
    family_links: list[dict[str, object]],
    parent_candidates: list[dict[str, object]],
) -> str | None:
    spec = _EXPLICIT_TAXONOMY_FAMILIES.get(parent_name)
    if spec is None:
        return None

    allowed_children = {str(child) for child in spec["children"]}
    family_children = {str(link["child"]) for link in family_links}
    parent_children = {str(candidate["child"]) for candidate in parent_candidates}
    if not family_children <= allowed_children:
        return None
    if not parent_children <= allowed_children:
        return None
    if len(family_children) < int(spec["min_children"]):
        return None
    if all("structural_family_pattern" in link["signals"] for link in family_links):
        return "structural_family_pattern"
    if not all(
        any(signal in {"definition_head", "relationship_pattern"} for signal in link["signals"])
        for link in family_links
    ):
        return None
    return "explicit_family_pattern"


def _infer_taxonomy(concepts: dict[str, dict[str, object]]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    known_concepts = set(concepts)
    inferred_candidates: dict[tuple[str, str], dict[str, object]] = {}

    for parent_name in sorted(concepts):
        payload = concepts[parent_name]
        source_chunks = sorted(set(int(chunk) for chunk in payload.get("source_chunks", [])))
        parent_is_taxonomic = _looks_taxonomic_parent(parent_name)

        for definition in payload.get("definitions", []):
            if not isinstance(definition, str):
                continue
            child_name = _definition_head(definition)
            if not child_name or child_name == parent_name or child_name not in known_concepts:
                continue
            link = inferred_candidates.setdefault(
                (parent_name, child_name),
                _new_candidate(parent=parent_name, child=child_name, source_chunks=source_chunks),
            )
            link["signals"] = _dedupe_preserve_order(list(link["signals"]) + ["definition_head"])
            link["evidence"] = _dedupe_preserve_order(list(link["evidence"]) + [definition])
            link["source_chunks"] = sorted(set(list(link["source_chunks"]) + source_chunks))

        for relationship in payload.get("relationships", []):
            if not isinstance(relationship, str):
                continue
            if not parent_is_taxonomic:
                continue
            for child_name in sorted(known_concepts):
                if child_name == parent_name:
                    continue
                if not _relationship_supports_taxonomy(relationship, child_name):
                    continue
                link = inferred_candidates.setdefault(
                    (parent_name, child_name),
                    _new_candidate(parent=parent_name, child=child_name, source_chunks=source_chunks),
                )
                link["signals"] = _dedupe_preserve_order(list(link["signals"]) + ["relationship_pattern"])
                link["evidence"] = _dedupe_preserve_order(list(link["evidence"]) + [relationship])
                link["source_chunks"] = sorted(set(list(link["source_chunks"]) + source_chunks))

        explicit_family = _EXPLICIT_TAXONOMY_FAMILIES.get(parent_name)
        if explicit_family is not None:
            parent_chunks = _source_chunk_set(payload)
            for child_name in explicit_family["children"]:
                if child_name == parent_name or child_name not in known_concepts:
                    continue
                child_payload = concepts[child_name]
                shared_chunks = sorted(parent_chunks & _source_chunk_set(child_payload))
                if not shared_chunks:
                    continue
                terminology_evidence = _terminology_supports_structural_family(
                    payload,
                    child_name=child_name,
                )
                if not terminology_evidence:
                    continue
                link = inferred_candidates.setdefault(
                    (parent_name, child_name),
                    _new_candidate(parent=parent_name, child=child_name, source_chunks=shared_chunks),
                )
                link["signals"] = _dedupe_preserve_order(list(link["signals"]) + ["structural_family_pattern"])
                link["evidence"] = _dedupe_preserve_order(list(link["evidence"]) + terminology_evidence)
                link["source_chunks"] = sorted(set(list(link["source_chunks"]) + shared_chunks))

    inferred_by_parent: dict[str, list[dict[str, object]]] = {}
    for link in inferred_candidates.values():
        inferred_by_parent.setdefault(str(link["parent"]), []).append(link)

    accepted_links: list[dict[str, object]] = []
    rejected_candidates: list[dict[str, object]] = []

    for parent_name in sorted(inferred_by_parent):
        parent_candidates = sorted(inferred_by_parent[parent_name], key=_candidate_sort_key)
        families: dict[tuple[str, int], list[dict[str, object]]] = {}
        for link in parent_candidates:
            child_name = str(link["child"])
            signature = _signature_tokens(child_name)
            family_key = ((signature[-1] if signature else child_name), len(signature))
            families.setdefault(family_key, []).append(link)

        accepted_pairs: set[tuple[str, str]] = set()
        coherent_families: list[list[dict[str, object]]] = []
        family_reasons: dict[tuple[str, int], str] = {}
        explicit_acceptances: dict[tuple[str, int], str] = {}
        for family_key, family_links in families.items():
            ordered_family = sorted(family_links, key=_candidate_sort_key)
            explicit_reason = _explicit_family_reason(
                parent_name=parent_name,
                family_links=ordered_family,
                parent_candidates=parent_candidates,
            )
            if explicit_reason in {"explicit_family_pattern", "structural_family_pattern"}:
                coherent_families.append(ordered_family)
                explicit_acceptances[family_key] = explicit_reason
                continue
            if explicit_reason is not None:
                family_reasons[family_key] = explicit_reason
                continue
            reason = _family_rejection_reason(
                parent_name=parent_name,
                family_links=ordered_family,
                parent_candidates=parent_candidates,
            )
            if reason is None:
                coherent_families.append(ordered_family)
            else:
                family_reasons[family_key] = reason

        accepted_family = _select_coherent_family(
            [link for family in coherent_families for link in family]
        )
        for link in accepted_family:
            accepted_pairs.add((str(link["parent"]), str(link["child"])))
            accepted_family_key = (
                (_signature_tokens(str(link["child"]))[-1] if _signature_tokens(str(link["child"])) else str(link["child"])),
                len(_signature_tokens(str(link["child"]))),
            )
            accepted_links.append(_build_candidate_audit_row(link, decision="accepted"))
        if accepted_family:
            accepted_family_key = (
                (_signature_tokens(str(accepted_family[0]["child"]))[-1] if _signature_tokens(str(accepted_family[0]["child"])) else str(accepted_family[0]["child"])),
                len(_signature_tokens(str(accepted_family[0]["child"]))),
            )
        else:
            accepted_family_key = None

        if accepted_family and accepted_family_key in explicit_acceptances:
            acceptance_reason = explicit_acceptances[accepted_family_key]
            accepted_links[-len(accepted_family):] = [
                _build_candidate_audit_row(
                    link,
                    decision="accepted",
                    acceptance_reason=acceptance_reason,
                )
                for link in accepted_family
            ]

        for family_key, family_links in sorted(families.items()):
            if family_key == accepted_family_key:
                for link in sorted(family_links, key=_candidate_sort_key):
                    pair = (str(link["parent"]), str(link["child"]))
                    if pair in accepted_pairs:
                        continue
                    rejected_candidates.append(
                        _build_candidate_audit_row(
                            link,
                            decision="rejected",
                            rejection_reason="family_not_selected",
                        )
                    )
                continue

            rejection_reason = family_reasons.get(family_key, "family_not_selected")
            for link in sorted(family_links, key=_candidate_sort_key):
                rejected_candidates.append(
                    _build_candidate_audit_row(
                        link,
                        decision="rejected",
                        rejection_reason=rejection_reason,
                    )
                )

    accepted_links.sort(key=lambda item: (str(item["parent"]), str(item["child"])))
    rejected_candidates.sort(
        key=lambda item: (
            str(item["parent"]),
            str(item["child"]),
            str(item.get("rejection_reason", "")),
        )
    )
    return accepted_links, rejected_candidates


def infer_taxonomy_links(concepts: dict[str, dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    """Infer auditable taxonomy links between existing canonical concepts."""
    accepted_links, _ = _infer_taxonomy(concepts)
    links = [
        {
            "parent": str(link["parent"]),
            "child": str(link["child"]),
            "signals": list(link["signals"]),
            "evidence": list(link["evidence"]),
            "source_chunks": list(link["source_chunks"]),
        }
        for link in accepted_links
    ]
    return {"links": links}


def infer_taxonomy_audit(concepts: dict[str, dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    """Return accepted and rejected taxonomy candidates for debugging and audits."""
    accepted_links, rejected_candidates = _infer_taxonomy(concepts)
    return {
        "accepted_links": accepted_links,
        "rejected_candidates": rejected_candidates,
    }
