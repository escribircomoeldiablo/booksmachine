"""Conservative normalization utilities for chunk knowledge records."""

from __future__ import annotations

import re

from .concept_normalization import normalize_concepts
from .knowledge_schema import (
    AuthorVariant,
    ChunkKnowledgeV1,
    DecisionRule,
    ProcedureCondition,
    ProcedureOutput,
    ProcedureStep,
)

CORE_FIELDS: tuple[str, ...] = (
    "concepts",
    "definitions",
    "technical_rules",
    "procedures",
    "relationships",
)
SEMANTIC_FIELDS: tuple[str, ...] = (
    "concepts",
    "definitions",
    "technical_rules",
    "procedures",
    "terminology",
    "relationships",
    "examples",
    "ambiguities",
)
AUTHOR_CANONICAL_MAP = {
    "valens": "Valens",
    "porphyry": "Porphyry",
    "paulus": "Paulus",
    "dorotheus": "Dorotheus",
    "ptolemy": "Ptolemy",
    "antiochus": "Antiochus",
}

_RE_EDITORIAL = re.compile(
    r"\b(copyright|all rights reserved|permission|reproduc|license|isbn|publisher|quoted|citation style)\b",
    re.IGNORECASE,
)
_RE_MODERN = re.compile(
    r"\b(modern|contemporary|psycholog|reinterpret|today|current|twentieth century|siglo xx|moderno|moderna)\b",
    re.IGNORECASE,
)
_RE_TRADITIONAL = re.compile(
    r"\b(house|houses|planet|ascendant|midheaven|dignity|sect|triplicity|horoskopos|domicile|angular|cadent|succedent|casa|casas|ascendente|mediocielo|secta)\b",
    re.IGNORECASE,
)
_RE_OPERATIONAL_DEFINITION = re.compile(
    r"\b(if|when|si|cuando|then|therefore|indicates|indica|applies|aplica|depends|depende|strength|fuerza|weak|debil|manifest|manifiesta|effect|efecto)\b",
    re.IGNORECASE,
)
_RE_DECISION_RULE = re.compile(
    r"^(?:if|si)\s+(?P<condition>.+?)(?:,\s*)?(?:then|entonces)\s+(?P<outcome>.+)$",
    re.IGNORECASE,
)
_RE_LINEAR_PROCEDURE_LEAD = re.compile(
    r"^(?:to use|to calculate|to determine|to assign|profections?\s*:|assigning\s+the|using\s+the)\s+",
    re.IGNORECASE,
)
_RE_LINEAR_PROCEDURE_SPLIT = re.compile(r";|\.\s+|,\s+(?=(?:and\s+)?(?:identify|determine|interpret|activate|assign|emphasize|advance|move|evaluate|apply)\b)", re.IGNORECASE)


def _normalize_string(value: str) -> str:
    return " ".join(value.strip().split())


def _dedupe_conservative(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        normalized = _normalize_string(item)
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    return result


def _normalize_procedure_text(value: str) -> str:
    normalized = _normalize_string(value)
    normalized = re.sub(r"^(?:step|paso)\s*\d+[:.)-]?\s*", "", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"^\d+[:.)-]?\s*", "", normalized)
    return normalized.strip(" .;:")


def _canonical_author_name(value: str) -> str:
    normalized = _normalize_string(value).strip(" .;:")
    if not normalized:
        return ""
    key = normalized.lower()
    return AUTHOR_CANONICAL_MAP.get(key, normalized.title() if key.islower() else normalized)


def _step_id(order: int, text: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", _normalize_procedure_text(text).lower()).strip("-")
    suffix = normalized[:48] or "step"
    return f"step-{order:03d}-{suffix}"


def _dedupe_steps(steps: list[ProcedureStep]) -> list[ProcedureStep]:
    seen: set[tuple[int, str]] = set()
    output: list[ProcedureStep] = []
    for step in sorted(steps, key=lambda item: (item.order, item.id, item.text)):
        normalized_text = _normalize_procedure_text(step.text)
        if not normalized_text:
            continue
        key = (step.order, normalized_text.lower())
        if key in seen:
            continue
        seen.add(key)
        output.append(
            ProcedureStep(
                id=step.id.strip() or _step_id(step.order, normalized_text),
                order=step.order,
                text=normalized_text,
            )
        )
    return output


def _dedupe_rules(rules: list[DecisionRule]) -> list[DecisionRule]:
    seen: set[tuple[str, str, tuple[str, ...]]] = set()
    output: list[DecisionRule] = []
    for rule in rules:
        condition = _normalize_string(rule.condition)
        outcome = _normalize_string(rule.outcome)
        related = tuple(dict.fromkeys(step for step in rule.related_steps if step))
        key = (condition.lower(), outcome.lower(), related)
        if not condition or not outcome or key in seen:
            continue
        seen.add(key)
        output.append(DecisionRule(condition=condition, outcome=outcome, related_steps=list(related)))
    return output


def _derive_decision_rules_from_technical_rules(record: ChunkKnowledgeV1) -> None:
    derived: list[DecisionRule] = []
    remaining_rules: list[str] = []
    for item in record.technical_rules:
        text = _normalize_string(item)
        match = _RE_DECISION_RULE.match(text)
        if match:
            derived.append(
                DecisionRule(
                    condition=_normalize_string(match.group("condition")),
                    outcome=_normalize_string(match.group("outcome")).rstrip("."),
                    related_steps=[],
                )
            )
            continue
        lowered = text.lower()
        if lowered.startswith("if ") or lowered.startswith("si "):
            if "," in text:
                condition, outcome = text.split(",", 1)
                outcome_text = outcome.strip().lstrip("then ").lstrip("entonces ").strip()
                if outcome_text:
                    derived.append(
                        DecisionRule(
                            condition=_normalize_string(re.sub(r"^(if|si)\s+", "", condition, flags=re.IGNORECASE)),
                            outcome=_normalize_string(outcome_text).rstrip("."),
                            related_steps=[],
                        )
                    )
                    continue
        remaining_rules.append(item)
    if derived:
        record.decision_rules = _dedupe_rules(list(record.decision_rules) + derived)
        record.technical_rules = remaining_rules


def _candidate_step_segments(text: str) -> list[str]:
    normalized = _normalize_string(text).rstrip(".")
    normalized = re.sub(r"^(?:to use|to calculate|to determine|to assign)\s+[^:]+:\s*", "", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"^(?:profections?|progressions?|primary directions?)\s*:\s*", "", normalized, flags=re.IGNORECASE)
    parts = [_normalize_procedure_text(part) for part in _RE_LINEAR_PROCEDURE_SPLIT.split(normalized)]
    parts = [re.sub(r"^and\s+", "", part, flags=re.IGNORECASE) for part in parts]
    parts = [part for part in parts if part]
    return parts


def _looks_like_linear_procedure(text: str) -> bool:
    normalized = _normalize_string(text)
    if not normalized:
        return False
    if _RE_LINEAR_PROCEDURE_LEAD.search(normalized):
        return True
    lowered = normalized.lower()
    return (
        "identify the time lord" in lowered
        or "interpret the matters" in lowered
        or "activate each zodiac" in lowered
        or "profected sign" in lowered
    )


def _promote_linear_procedures_to_steps(record: ChunkKnowledgeV1) -> None:
    if record.procedure_steps:
        return

    promoted_steps: list[ProcedureStep] = []
    for source_text in list(record.procedures) + list(record.technical_rules):
        text = _normalize_string(source_text)
        if not _looks_like_linear_procedure(text):
            continue
        segments = _candidate_step_segments(text)
        action_segments = []
        for segment in segments:
            lowered = segment.lower()
            if any(
                lowered.startswith(prefix)
                for prefix in (
                    "activate ",
                    "identify ",
                    "determine ",
                    "interpret ",
                    "assign ",
                    "emphasize ",
                    "move ",
                    "advance ",
                    "evaluate ",
                    "apply ",
                )
            ):
                action_segments.append(segment)
        if len(action_segments) < 2:
            continue
        for order, segment in enumerate(action_segments, start=len(promoted_steps) + 1):
            promoted_steps.append(
                ProcedureStep(
                    id=_step_id(order, segment),
                    order=order,
                    text=segment,
                )
            )

    if promoted_steps:
        record.procedure_steps = _dedupe_steps(list(record.procedure_steps) + promoted_steps)


def _dedupe_conditions(values: list[ProcedureCondition]) -> list[ProcedureCondition]:
    seen: set[tuple[str, str, tuple[str, ...]]] = set()
    output: list[ProcedureCondition] = []
    for item in values:
        text = _normalize_string(item.text)
        scope = _normalize_string(item.scope)
        related = tuple(dict.fromkeys(step for step in item.related_steps if step))
        key = (text.lower(), scope.lower(), related)
        if not text or key in seen:
            continue
        seen.add(key)
        output.append(ProcedureCondition(text=text, scope=scope, related_steps=list(related)))
    return output


def _dedupe_variants(values: list[AuthorVariant]) -> list[AuthorVariant]:
    seen: set[tuple[str, str, str, tuple[str, ...]]] = set()
    output: list[AuthorVariant] = []
    for item in values:
        author = _canonical_author_name(item.author)
        kind = _normalize_string(item.kind).lower()
        text = _normalize_string(item.text)
        related = tuple(dict.fromkeys(step for step in item.related_steps if step))
        key = (author.lower(), kind, text.lower(), related)
        if not author or not kind or not text or key in seen:
            continue
        seen.add(key)
        output.append(AuthorVariant(author=author, kind=kind, text=text, related_steps=list(related)))
    return output


def _dedupe_outputs(values: list[ProcedureOutput]) -> list[ProcedureOutput]:
    seen: set[str] = set()
    output: list[ProcedureOutput] = []
    for item in values:
        text = _normalize_string(item.text)
        key = text.lower()
        if not text or key in seen:
            continue
        seen.add(key)
        output.append(ProcedureOutput(text=text))
    return output


def derive_procedures(record: ChunkKnowledgeV1) -> list[str]:
    derived: list[str] = []
    for step in sorted(record.procedure_steps, key=lambda item: (item.order, item.id)):
        derived.append(f"{step.order}. {step.text}")
    for rule in record.decision_rules:
        derived.append(f"If {rule.condition}, then {rule.outcome}.")
    for item in record.preconditions:
        scope = f" ({item.scope})" if item.scope else ""
        derived.append(f"Precondition{scope}: {item.text}")
    for item in record.exceptions:
        scope = f" ({item.scope})" if item.scope else ""
        derived.append(f"Exception{scope}: {item.text}")
    for item in record.author_variants:
        derived.append(f"{item.author} [{item.kind}]: {item.text}")
    for item in record.procedure_outputs:
        derived.append(f"Output: {item.text}")
    return _dedupe_conservative(derived)


def normalize_chunk_knowledge(record: ChunkKnowledgeV1) -> ChunkKnowledgeV1:
    """Normalize selected fields while preserving core metadata."""
    record.terminology = _dedupe_conservative(record.terminology)
    record.concepts = _dedupe_conservative(record.concepts)
    record.technical_rules = _dedupe_conservative(record.technical_rules)
    _derive_decision_rules_from_technical_rules(record)
    _promote_linear_procedures_to_steps(record)
    record.procedure_steps = _dedupe_steps(record.procedure_steps)
    record.decision_rules = _dedupe_rules(record.decision_rules)
    record.preconditions = _dedupe_conditions(record.preconditions)
    record.exceptions = _dedupe_conditions(record.exceptions)
    record.author_variants = _dedupe_variants(record.author_variants)
    record.procedure_outputs = _dedupe_outputs(record.procedure_outputs)
    record.procedures = derive_procedures(record)
    return record


def _is_generic_definition(text: str) -> bool:
    normalized = _normalize_string(text)
    if not normalized:
        return True
    if _RE_OPERATIONAL_DEFINITION.search(normalized):
        return False
    words = normalized.split()
    if len(words) <= 5:
        return True
    if ":" in normalized:
        lhs, rhs = normalized.split(":", 1)
        if len(rhs.strip().split()) <= 5:
            return True
    lowered = normalized.lower()
    if any(token in lowered for token in ("is a", "is an", "means", "refers to", "es un", "es una", "significa")):
        return True
    return False


def _is_modern_embedded_item(text: str) -> bool:
    return bool(_RE_MODERN.search(text) and _RE_TRADITIONAL.search(text))


def apply_semantic_local_filter(
    record: ChunkKnowledgeV1,
    *,
    filter_editorial: bool,
    filter_generic_definitions: bool,
    filter_modern: bool,
) -> tuple[ChunkKnowledgeV1, list[str]]:
    """Apply deterministic semantic cleanup before doctrinal support gating."""
    actions: list[str] = []

    if filter_editorial:
        for field_name in ("technical_rules", "procedures"):
            source = getattr(record, field_name)
            kept = [item for item in source if not _RE_EDITORIAL.search(item)]
            if len(kept) < len(source):
                setattr(record, field_name, kept)
                actions.append(f"clear_editorial_{field_name}")

    if filter_generic_definitions:
        kept_definitions = [item for item in record.definitions if not _is_generic_definition(item)]
        if len(kept_definitions) < len(record.definitions):
            record.definitions = kept_definitions
            actions.append("drop_generic_definitions")

    if filter_modern:
        modern_fragments: list[str] = []
        for field_name in ("concepts", "definitions", "technical_rules", "procedures", "relationships"):
            source = getattr(record, field_name)
            kept: list[str] = []
            for item in source:
                if not _RE_MODERN.search(item):
                    kept.append(item)
                    continue
                if _is_modern_embedded_item(item):
                    kept.append(item)
                    modern_fragments.append(item)
                    actions.append("mark_modern_embedded_preserved_core")
                else:
                    modern_fragments.append(item)
                    actions.append(f"relocate_modern_{field_name}")
            setattr(record, field_name, kept)
        if modern_fragments:
            record.ambiguities = _dedupe_conservative(record.ambiguities + modern_fragments)
            actions.append("relocate_modern_to_ambiguities")

    record.ambiguities = _dedupe_conservative(record.ambiguities)
    return record, _dedupe_conservative(actions)


def _trim_items(items: list[str], limit: int) -> list[str]:
    if limit <= 0:
        return []
    return items[:limit]


def _has_strong_terminology_pattern(chunk_text: str) -> bool:
    text = chunk_text.lower()
    if ":" in chunk_text and sum(1 for line in chunk_text.splitlines() if ":" in line) >= 2:
        return True
    if any(marker in text for marker in ("term", "terminology", "glossary", "definition")):
        return True
    return False


def _has_explicit_ambiguity_evidence(chunk_text: str) -> bool:
    text = chunk_text.lower()
    markers = (
        "debate",
        "dispute",
        "uncertain",
        "ambigu",
        "variant",
        "however",
        "conflict",
        "some authors",
        "others",
    )
    return any(marker in text for marker in markers)


def apply_post_extraction_clamp(
    record: ChunkKnowledgeV1,
    *,
    confidence_profile: str,
    decision: str,
    chunk_type: str,
    chunk_text: str,
    weak_support_pattern: bool = False,
    weak_support_concepts_max: int = 2,
    weak_support_terminology_max: int = 3,
) -> tuple[ChunkKnowledgeV1, list[str]]:
    """Apply deterministic post-extraction clamp by confidence profile."""
    actions: list[str] = []

    if confidence_profile == "high" and decision == "extract" and chunk_type == "doctrinal_text":
        return record, actions

    if confidence_profile == "medium":
        for field_name in ("concepts", "definitions", "technical_rules", "procedures", "relationships"):
            values = getattr(record, field_name)
            limited = _trim_items(values, 8)
            if len(limited) < len(values):
                setattr(record, field_name, limited)
                actions.append(f"cap_{field_name}_8")
        if len(record.terminology) > 12:
            record.terminology = _trim_items(record.terminology, 12)
            actions.append("cap_terminology_12")
        if len(record.examples) > 6:
            record.examples = _trim_items(record.examples, 6)
            actions.append("cap_examples_6")

    if confidence_profile == "low" or decision == "extract_degraded":
        for field_name in ("definitions", "technical_rules", "procedures", "relationships"):
            if getattr(record, field_name):
                setattr(record, field_name, [])
                actions.append(f"clear_{field_name}")
        if len(record.concepts) > 4:
            record.concepts = _trim_items(record.concepts, 4)
            actions.append("cap_concepts_4")
        if len(record.examples) > 2:
            record.examples = _trim_items(record.examples, 2)
            actions.append("cap_examples_2")
        if not _has_strong_terminology_pattern(chunk_text):
            if record.terminology:
                record.terminology = []
                actions.append("clear_terminology_no_pattern")
        elif len(record.terminology) > 5:
            record.terminology = _trim_items(record.terminology, 5)
            actions.append("cap_terminology_5")
        if not _has_explicit_ambiguity_evidence(chunk_text) and record.ambiguities:
            record.ambiguities = []
            actions.append("clear_ambiguities_no_evidence")

    if confidence_profile == "contaminated" or decision == "skip":
        for field_name in CORE_FIELDS:
            if getattr(record, field_name):
                setattr(record, field_name, [])
                actions.append(f"clear_{field_name}")
        if record.examples:
            record.examples = []
            actions.append("clear_examples")
        if not _has_strong_terminology_pattern(chunk_text):
            if record.terminology:
                record.terminology = []
                actions.append("clear_terminology_no_pattern")
        elif len(record.terminology) > 3:
            record.terminology = _trim_items(record.terminology, 3)
            actions.append("cap_terminology_3")
        if not _has_explicit_ambiguity_evidence(chunk_text):
            if record.ambiguities:
                record.ambiguities = []
                actions.append("clear_ambiguities_no_evidence")
        elif len(record.ambiguities) > 2:
            record.ambiguities = _trim_items(record.ambiguities, 2)
            actions.append("cap_ambiguities_2")

    if weak_support_pattern:
        for field_name in ("definitions", "technical_rules", "procedures", "relationships"):
            if getattr(record, field_name):
                setattr(record, field_name, [])
                actions.append(f"clear_{field_name}_weak_support")
        if len(record.concepts) > weak_support_concepts_max:
            record.concepts = _trim_items(record.concepts, weak_support_concepts_max)
            actions.append(f"cap_concepts_{weak_support_concepts_max}_weak_support")
        if not _has_strong_terminology_pattern(chunk_text):
            if record.terminology:
                record.terminology = []
                actions.append("clear_terminology_weak_support_no_pattern")
        elif len(record.terminology) > weak_support_terminology_max:
            record.terminology = _trim_items(record.terminology, weak_support_terminology_max)
            actions.append(f"cap_terminology_{weak_support_terminology_max}_weak_support")
        if record.ambiguities:
            record.ambiguities = []
            actions.append("clear_ambiguities_weak_support")

    return record, actions


def merge_chunk_knowledge_records(records: list[ChunkKnowledgeV1]) -> dict[str, object]:
    """Deterministic concept-level consolidation over chunk records."""
    concept_index: dict[str, list[int]] = {}
    for idx, record in enumerate(records, start=1):
        canonical_concepts = normalize_concepts(record.concepts)
        for concept_name in canonical_concepts:
            bucket = concept_index.setdefault(concept_name, [])
            bucket.append(idx)

    merged_concepts = [
        {
            "concept": concept_name,
            "chunk_indices": indices,
            "mentions": len(indices),
        }
        for concept_name, indices in sorted(concept_index.items())
    ]
    return {
        "schema_version": "merge_v1",
        "record_count": len(records),
        "concept_index": concept_index,
        "merged_concepts": merged_concepts,
        "status": "ok",
    }
