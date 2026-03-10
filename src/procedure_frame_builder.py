from __future__ import annotations

import re
from typing import Any


PROCEDURE_EVIDENCE_FIELDS: tuple[str, ...] = (
    "procedure_steps",
    "decision_rules",
    "preconditions",
    "exceptions",
    "author_variants",
    "procedure_outputs",
)

_FRAME_SPECS: tuple[dict[str, Any], ...] = (
    {
        "id": "determine_predominator",
        "frame_type": "selection",
        "label": "Determine Predominator",
        "goal": "Determine which factor holds the predomination in the nativity.",
        "anchor_concepts": ("predominator",),
        "supporting_concepts": (
            "predomination",
            "predomination of light",
            "predomination of sect light",
            "sect light predomination criteria",
            "sect light preference",
            "positional consideration for selecting predominator",
            "angularity in predomination",
        ),
        "related_concepts": ("sect", "house system", "oikodespotes"),
        "include_signals": (
            "predominator",
            "predomination",
            "sect light",
            "candidate",
            "ascendant",
            "lot of fortune",
            "prenatal lunation",
            "witnessed",
        ),
        "exclude_signals": (
            "good character",
            "success by means",
            "illness",
            "fortunate and unfortunate experiences",
        ),
    },
    {
        "id": "apply_profections",
        "frame_type": "timing",
        "label": "Apply Profections",
        "goal": "Apply profections to determine the time lord and the matters emphasized during the profected period.",
        "anchor_concepts": ("profection", "annual lord of year", "time lord"),
        "supporting_concepts": ("chronokrator",),
        "related_concepts": ("primary directions", "progressions"),
        "include_signals": (
            "profection",
            "annual lord",
            "time lord",
            "chronokrator",
            "profected sign",
            "activated",
            "zodiacal order",
            "period of influence",
        ),
        "exclude_signals": (
            "circumambulation",
            "primary directions",
            "progressions",
        ),
    },
    {
        "id": "determine_oikodespotes",
        "frame_type": "selection",
        "label": "Determine Oikodespotes",
        "goal": "Determine the master of the nativity by selecting the appropriate ruler from the Predominator or other designated source.",
        "anchor_concepts": ("oikodespotes", "master of the nativity"),
        "supporting_concepts": ("sunoikodespotes joint master",),
        "related_concepts": ("predominator", "house system"),
        "include_signals": (
            "oikodespotes",
            "master of the nativity",
            "bound lord",
            "domicile lord",
            "joint master",
            "sunoikodespotes",
            "witnessed by the predominator",
            "assign",
            "determine",
            "select",
        ),
        "exclude_signals": (
            "good character",
            "success by means",
            "what it signifies",
            "character delineation",
            "physical constitution",
            "harm",
            "ill repute",
        ),
    },
    {
        "id": "evaluate_oikodespotes",
        "frame_type": "evaluation",
        "label": "Evaluate Oikodespotes",
        "goal": "Judge the condition and effects of the Oikodespotes once selected.",
        "anchor_concepts": ("oikodespotes", "master of the nativity"),
        "supporting_concepts": ("sunoikodespotes joint master",),
        "related_concepts": ("predominator",),
        "include_signals": (
            "good character",
            "bad character",
            "good effects",
            "injurious",
            "success by means",
            "what it signifies",
            "physical constitution",
            "bodily constitution",
            "ill repute",
            "harm",
            "benefic",
            "malefic",
            "sect",
            "dignity",
            "angular",
            "succedent",
            "cadent",
        ),
        "exclude_signals": (
            "assign the master",
            "determine the master",
            "domicile lord of the predominator",
            "bound lord of the predominator",
        ),
    },
)

_SPACE_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^a-z0-9\s]")


def _dedupe_list(items: list[Any]) -> list[Any]:
    deduped: list[Any] = []
    for item in items:
        if item not in deduped:
            deduped.append(item)
    return deduped


def _normalize_text(value: str) -> str:
    return _SPACE_RE.sub(" ", str(value).strip())


def _surface(value: str) -> str:
    normalized = _normalize_text(value).lower().replace("-", " ")
    normalized = _PUNCT_RE.sub(" ", normalized)
    return _SPACE_RE.sub(" ", normalized).strip()


def _text_has_any_signal(text: str, signals: tuple[str, ...]) -> bool:
    blob = _surface(text)
    return any(_surface(signal) in blob for signal in signals)


def _text_passes_filters(text: str, spec: dict[str, Any]) -> bool:
    include = tuple(spec.get("include_signals", ()))
    exclude = tuple(spec.get("exclude_signals", ()))
    if include and not _text_has_any_signal(text, include):
        return False
    if exclude and _text_has_any_signal(text, exclude):
        return False
    return True


def _normalize_condition(value: str) -> str:
    text = _normalize_text(value)
    text = re.sub(r"^(?:if|si)\s+", "", text, flags=re.IGNORECASE)
    return text.strip(" .;:")


def _normalize_outcome(value: str) -> str:
    return _normalize_text(value).strip(" .;:")


def _sentence_case(value: str) -> str:
    text = _normalize_text(value)
    if not text:
        return ""
    return text[0].upper() + text[1:]


def _rule_quality(condition: str, outcome: str) -> bool:
    c = _surface(condition)
    o = _surface(outcome)
    if not c or not o:
        return False
    if "e g" in c:
        return False
    if o.startswith(("first ", "second ", "third ", "fourth ", "fifth ", "sixth ", "seventh ", "eighth ", "ninth ", "tenth ", "eleventh ", "twelfth ")):
        return False
    if o.startswith("r if ") or o.startswith("re is no "):
        return False
    return True


def _normalize_rule(rule: dict[str, Any]) -> dict[str, Any] | None:
    condition = _normalize_condition(str(rule.get("condition", "")))
    outcome = _normalize_outcome(str(rule.get("outcome", "")))
    if not _rule_quality(condition, outcome):
        return None
    return {
        "condition": condition,
        "outcome": outcome,
        "related_steps": [str(v).strip() for v in rule.get("related_steps", []) if str(v).strip()],
    }


def _rule_text(rule: dict[str, Any]) -> str:
    return f"{rule.get('condition', '')} {rule.get('outcome', '')}"


def _rule_key(rule: dict[str, Any]) -> tuple[str, str]:
    condition = _surface(str(rule.get("condition", "")))
    outcome = _surface(str(rule.get("outcome", "")))
    outcome = outcome.replace("will be the predominator", "is the predominator")
    outcome = outcome.replace("the predomination goes to the ascendant", "predomination goes to the ascendant")
    outcome = outcome.replace("predomination goes to the ascendant", "the ascendant has the predomination")
    outcome = outcome.replace("the ascendant will have the predomination", "the ascendant has the predomination")
    outcome = outcome.replace("moon will be the predominator", "moon is the predominator")
    return condition, outcome


def _rule_priority(rule: dict[str, Any]) -> tuple[int, str, str]:
    condition, outcome = _rule_key(rule)
    if "light of the sect is cadent" in condition and "other light" in outcome:
        return (1, condition, outcome)
    if "moon" in condition and "ascending in the east" in condition and "predominator" in outcome:
        return (2, condition, outcome)
    if ("both lights" in condition or ("sun" in condition and "moon" in condition)) and (
        "cadent" in condition or "declining" in condition
    ) and "ascendant" in outcome:
        return (3, condition, outcome)
    if "bound lord" in condition or "domicile lord" in condition:
        return (4, condition, outcome)
    return (50, condition, outcome)


def _step_id(order: int, text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", _surface(text)).strip("-")[:48] or "step"
    return f"step-{order:03d}-{slug}"


def _step_from_rule(rule: dict[str, Any], order: int) -> dict[str, Any]:
    text = _sentence_case(f"If {rule['condition']}, then {rule['outcome']}")
    return {"id": _step_id(order, text), "order": order, "text": text}


def _normalize_steps(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in sorted(steps, key=lambda step: (int(step.get("order", 0)), str(step.get("id", "")))):
        text = _normalize_text(str(item.get("text", ""))).strip(" .;:")
        if not text:
            continue
        key = (_surface(text), str(item.get("id", "")))
        if key in seen:
            continue
        seen.add(key)
        deduped.append({"id": str(item.get("id") or _step_id(len(deduped) + 1, text)), "order": len(deduped) + 1, "text": text})
    return deduped


def _derive_shared_steps(frame: dict[str, Any]) -> list[dict[str, Any]]:
    explicit = _normalize_steps(list(frame.get("shared_steps", [])))
    if len(explicit) >= 2:
        return explicit
    rules = [rule for raw in frame.get("decision_rules", []) if (rule := _normalize_rule(raw)) is not None]
    ranked = sorted(rules, key=_rule_priority)
    derived: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str]] = set()
    for raw_rule in ranked:
        key = _rule_key(raw_rule)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        derived.append(_step_from_rule(raw_rule, len(derived) + 1))
        if len(derived) >= 3:
            break
    if len(derived) >= 2:
        return derived
    return explicit


def _normalize_author_variants(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in items:
        normalized = {
            "author": _normalize_text(str(item.get("author", ""))),
            "kind": _normalize_text(str(item.get("kind", ""))),
            "text": _normalize_text(str(item.get("text", ""))),
            "related_steps": [str(v).strip() for v in item.get("related_steps", []) if str(v).strip()],
            "operation": _normalize_text(str(item.get("operation", ""))) or "annotate",
        }
        key = (_surface(normalized["author"]), _surface(normalized["kind"]), _surface(normalized["text"]))
        if not key[2] or key in seen:
            continue
        seen.add(key)
        deduped.append(normalized)
    return deduped


def _selection_rule_kind(rule: dict[str, Any]) -> str:
    condition, outcome = _rule_key(rule)
    blob = f"{condition} {outcome}"
    if any(token in blob for token in ("other light", "contrary light", "ascendant")):
        return "fallback"
    if any(token in outcome for token in ("select ", "is the predominator", "qualifies as", "becomes the master", "is selected as master")):
        return "candidate"
    return "candidate"


def _split_selection_rules(rules: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidate_priority_rules: list[dict[str, Any]] = []
    fallback_rules: list[dict[str, Any]] = []
    for rule in rules:
        if _selection_rule_kind(rule) == "fallback":
            fallback_rules.append(rule)
        else:
            candidate_priority_rules.append(rule)
    return candidate_priority_rules, fallback_rules


def _derived_rules_from_author_methods(items: list[dict[str, Any]], spec: dict[str, Any]) -> list[dict[str, Any]]:
    if spec.get("frame_type") != "selection":
        return []
    derived: list[dict[str, Any]] = []
    for item in items:
        author = _normalize_text(str(item.get("author", ""))) or "This method"
        text = _surface(str(item.get("text", "")))
        rule: dict[str, Any] | None = None
        if "domicile lord of the predominator" in text:
            rule = {
                "condition": f"{author}'s method is followed",
                "outcome": "select the domicile lord of the Predominator as Oikodespotes",
                "related_steps": [],
            }
        elif "bound lord of the predominator" in text:
            rule = {
                "condition": f"{author}'s method is followed",
                "outcome": "select the bound lord of the Predominator as Oikodespotes",
                "related_steps": [],
            }
        elif "bound lord of the ascendant" in text:
            rule = {
                "condition": f"{author}'s method is followed",
                "outcome": "select the bound lord of the Ascendant as Master of the Nativity",
                "related_steps": [],
            }
        elif "sign following the natal moon" in text:
            rule = {
                "condition": f"{author}'s method is followed",
                "outcome": "select the domicile lord of the sign following the natal Moon as Oikodespotes",
                "related_steps": [],
            }
        if rule is not None and _text_passes_filters(_rule_text(rule), spec):
            derived.append(rule)
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for rule in derived:
        key = _rule_key(rule)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(rule)
    return deduped


def _classify_author_variant(item: dict[str, Any], spec: dict[str, Any]) -> str:
    text = f"{item.get('kind', '')} {item.get('text', '')}"
    if not _text_passes_filters(text, spec):
        return "skip"
    blob = _surface(text)
    if spec.get("frame_type") == "selection" and any(
        token in blob
        for token in ("house system", "whole sign", "whole-sign", "porphyry house system", "terminological", "unclear if used")
    ):
        return "methodological_note"
    if any(token in blob for token in ("method", "procedure", "assignment", "assigns", "looked for", "determining", "determine", "select")):
        return "author_method"
    return "override"


def _derived_evaluation_rules_from_technical_rules(rules: list[str], spec: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    derived_rules: list[dict[str, Any]] = []
    derived_preconditions: list[dict[str, Any]] = []
    for raw in rules:
        text = _normalize_text(raw)
        if not text or not _text_passes_filters(text, spec):
            continue
        lowered = _surface(text)
        if lowered.startswith("when "):
            parts = text[5:].split(",", 1)
            if len(parts) == 2:
                condition, outcome = parts
                rule = _normalize_rule({"condition": condition, "outcome": outcome, "related_steps": []})
                if rule is not None:
                    derived_rules.append(rule)
                    continue
        if lowered.startswith("if "):
            parts = text[3:].split(",", 1)
            if len(parts) == 2:
                condition, outcome = parts
                rule = _normalize_rule({"condition": condition, "outcome": outcome, "related_steps": []})
                if rule is not None:
                    derived_rules.append(rule)
                    continue
        if lowered.startswith("in delineation consider if "):
            body = text[len("In delineation, consider if "):]
            for piece in body.split(","):
                piece = _normalize_text(piece)
                if piece:
                    derived_preconditions.append({"text": piece, "scope": "evaluation of the Oikodespotes", "related_steps": []})
            continue
        if "belongs to the sect of the chart" in lowered or "angular or succedent houses" in lowered or "own domiciles or exaltation" in lowered:
            derived_preconditions.append({"text": text, "scope": "evaluation of the Oikodespotes", "related_steps": []})
    deduped_rules: list[dict[str, Any]] = []
    seen_rule_keys: set[tuple[str, str]] = set()
    for rule in derived_rules:
        key = _rule_key(rule)
        if key in seen_rule_keys:
            continue
        seen_rule_keys.add(key)
        deduped_rules.append(rule)
    deduped_pre: list[dict[str, Any]] = []
    seen_pre: set[tuple[str, str]] = set()
    for item in derived_preconditions:
        key = (_surface(item["text"]), _surface(item["scope"]))
        if key in seen_pre:
            continue
        seen_pre.add(key)
        deduped_pre.append(item)
    return deduped_rules, deduped_pre


def _empty_evidence() -> dict[str, list[dict[str, Any]]]:
    return {
        "shared_steps": [],
        "decision_rules": [],
        "preconditions": [],
        "exceptions": [],
        "author_variant_overrides": [],
        "author_method_variants": [],
        "procedure_outputs": [],
    }


def _append_step(steps: list[dict[str, Any]], text: str) -> None:
    normalized = _normalize_text(text).strip(" .;:")
    if not normalized:
        return
    key = _surface(normalized)
    if any(_surface(str(item.get("text", ""))) == key for item in steps):
        return
    order = len(steps) + 1
    steps.append({"id": _step_id(order, normalized), "order": order, "text": normalized})


def _derive_timing_steps_from_texts(frame: dict[str, Any]) -> list[dict[str, Any]]:
    steps = _normalize_steps(list(frame.get("shared_steps", [])))
    blob = _surface(" ".join(frame.get("_definitions", []) + frame.get("_technical_rules", [])))
    if not blob:
        return steps

    if len(steps) < 1 and ("profection" in blob or "annual lord" in blob or "time lord" in blob):
        _append_step(steps, "Select the type of profection (annual, monthly, daily) according to the timing interval required")
    if "activated" in blob and "zodiacal order" in blob:
        _append_step(steps, "Activate the next sign in zodiacal order at each interval")
    if "house occupied by the profected sign" in blob or "matters of the house occupied by the profected sign" in blob:
        _append_step(steps, "Emphasize the matters of the house occupied by the profected sign for that period")
    if "planet that rules the profected sign" in blob or "time lord" in blob:
        _append_step(steps, "Identify the planet that rules the profected sign (the time lord)")
    if "bring about its significations" in blob or "governs the life for the duration" in blob:
        _append_step(steps, "Interpret the effect of the time lord during its period of influence based on its significations in the natal chart")
    return _normalize_steps(steps)


def _derive_selection_steps(frame: dict[str, Any]) -> list[dict[str, Any]]:
    explicit = _normalize_steps(list(frame.get("shared_steps", [])))
    if len(explicit) >= 3:
        return explicit

    derived: list[dict[str, Any]] = []
    ordered_rules = sorted(
        list(frame.get("candidate_priority_rules", [])) + list(frame.get("fallback_rules", [])),
        key=_rule_priority,
    )
    for rule in ordered_rules:
        normalized = _normalize_rule(rule)
        if normalized is None:
            continue
        key = _rule_key(normalized)
        if any(_surface(step.get("text", "")) == _surface(_step_from_rule(normalized, 1)["text"]) for step in derived):
            continue
        derived.append(_step_from_rule(normalized, len(derived) + 1))
        if len(derived) >= 4:
            break
    if len(derived) >= 2:
        return _normalize_steps(derived)
    return explicit


def _merge_evidence(target: dict[str, list[dict[str, Any]]], source: dict[str, Any]) -> None:
    mapping = {
        "procedure_steps": "shared_steps",
        "decision_rules": "decision_rules",
        "preconditions": "preconditions",
        "exceptions": "exceptions",
        "author_variants": "author_variant_overrides",
        "procedure_outputs": "procedure_outputs",
    }
    for source_key, target_key in mapping.items():
        values = source.get(source_key, [])
        if not isinstance(values, list):
            continue
        for item in values:
            if item not in target[target_key]:
                target[target_key].append(item)


def _has_procedural_content(record: dict[str, Any]) -> bool:
    return any(
        record.get(field_name)
        for field_name in (
            "shared_procedure",
            "decision_rules",
            "preconditions",
            "exceptions",
            "author_variant_overrides",
            "procedure_outputs",
        )
    )


def _collect_member_records(
    concepts: dict[str, dict[str, Any]],
    spec: dict[str, Any],
) -> tuple[list[str], list[str], list[tuple[str, dict[str, Any]]]]:
    anchors = [concept for concept in spec["anchor_concepts"] if concept in concepts]
    supports = [concept for concept in spec["supporting_concepts"] if concept in concepts]
    members = anchors + [concept for concept in supports if concept not in anchors]
    records = [
        (concept, concepts[concept])
        for concept in members
        if _has_procedural_content(concepts[concept])
    ]
    return anchors, supports, records


def _filter_steps(steps: list[dict[str, Any]], spec: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        step for step in steps
        if _text_passes_filters(str(step.get("text", "")), spec)
    ]


def _filter_rules(rules: list[dict[str, Any]], spec: dict[str, Any]) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    seen_rule_keys: set[tuple[str, str]] = set()
    for raw_rule in rules:
        rule = _normalize_rule(raw_rule)
        if rule is None:
            continue
        if not _text_passes_filters(_rule_text(rule), spec):
            continue
        key = _rule_key(rule)
        if key in seen_rule_keys:
            continue
        seen_rule_keys.add(key)
        filtered.append(rule)
    return filtered


def _filter_conditions(items: list[dict[str, Any]], spec: dict[str, Any]) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        text = _normalize_text(str(item.get("text", "")))
        scope = _normalize_text(str(item.get("scope", "")))
        if not text or not _text_passes_filters(f"{scope} {text}", spec):
            continue
        key = (_surface(text), _surface(scope))
        if key in seen:
            continue
        seen.add(key)
        filtered.append(
            {
                "text": text,
                "scope": scope,
                "related_steps": [str(v).strip() for v in item.get("related_steps", []) if str(v).strip()],
            }
        )
    return filtered


def _filter_outputs(items: list[dict[str, Any]], spec: dict[str, Any]) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        text = _normalize_text(str(item.get("text", "")))
        if not text or not _text_passes_filters(text, spec):
            continue
        key = _surface(text)
        if key in seen:
            continue
        seen.add(key)
        filtered.append({"text": text})
    return filtered


def build_procedure_frames(
    concepts: dict[str, dict[str, Any]],
    ontology: dict[str, dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    frames: dict[str, dict[str, Any]] = {}
    for spec in _FRAME_SPECS:
        anchors, supports, records = _collect_member_records(concepts, spec)
        if not records:
            continue

        frame = {
            "id": spec["id"],
            "frame_type": spec["frame_type"],
            "label": spec["label"],
            "goal": spec["goal"],
            "anchor_concepts": anchors,
            "supporting_concepts": [concept for concept in supports if concept not in anchors],
            "shared_steps": [],
            "decision_rules": [],
            "preconditions": [],
            "exceptions": [],
            "candidate_priority_rules": [],
            "fallback_rules": [],
            "author_method_variants": [],
            "author_variant_overrides": [],
            "methodological_notes": [],
            "procedure_outputs": [],
            "related_concepts": [],
            "evidence": _empty_evidence(),
            "source_chunks": [],
            "_definitions": [],
            "_technical_rules": [],
        }

        related = list(spec.get("related_concepts", ()))
        for concept_name, record in records:
            frame["shared_steps"] = _dedupe_list(frame["shared_steps"] + list(record.get("shared_procedure", [])))
            frame["decision_rules"] = _dedupe_list(frame["decision_rules"] + list(record.get("decision_rules", [])))
            frame["preconditions"] = _dedupe_list(frame["preconditions"] + list(record.get("preconditions", [])))
            frame["exceptions"] = _dedupe_list(frame["exceptions"] + list(record.get("exceptions", [])))
            frame["procedure_outputs"] = _dedupe_list(frame["procedure_outputs"] + list(record.get("procedure_outputs", [])))
            frame["source_chunks"] = _dedupe_list(frame["source_chunks"] + list(record.get("source_chunks", [])))
            frame["_definitions"] = _dedupe_list(frame["_definitions"] + list(record.get("definitions", [])))
            frame["_technical_rules"] = _dedupe_list(frame["_technical_rules"] + list(record.get("technical_rules", [])))
            related = _dedupe_list(
                related
                + list(record.get("related_concepts", []))
                + list(record.get("parent_concepts", []))
                + list(record.get("child_concepts", []))
            )
            for variant in record.get("author_variant_overrides", []):
                classification = _classify_author_variant(variant, spec)
                if classification == "author_method":
                    frame["author_method_variants"].append(variant)
                elif classification == "methodological_note":
                    frame["methodological_notes"].append(variant)
                elif classification == "override":
                    frame["author_variant_overrides"].append(variant)
            _merge_evidence(frame["evidence"], record.get("procedure_evidence", {}))

        frame["decision_rules"] = _filter_rules(frame["decision_rules"], spec)
        frame["preconditions"] = _filter_conditions(frame["preconditions"], spec)
        frame["exceptions"] = _filter_conditions(frame["exceptions"], spec)
        frame["procedure_outputs"] = _filter_outputs(frame["procedure_outputs"], spec)
        frame["author_method_variants"] = _normalize_author_variants(frame["author_method_variants"])
        frame["author_variant_overrides"] = _normalize_author_variants(frame["author_variant_overrides"])
        frame["methodological_notes"] = _normalize_author_variants(frame["methodological_notes"])
        if spec.get("frame_type") == "evaluation":
            derived_rules, derived_preconditions = _derived_evaluation_rules_from_technical_rules(frame["_technical_rules"], spec)
            frame["decision_rules"] = _filter_rules(frame["decision_rules"] + derived_rules, spec)
            frame["preconditions"] = _filter_conditions(frame["preconditions"] + derived_preconditions, spec)
        if not frame["decision_rules"] and frame["author_method_variants"]:
            frame["decision_rules"] = _derived_rules_from_author_methods(frame["author_method_variants"], spec)
        if spec.get("frame_type") == "selection":
            frame["candidate_priority_rules"], frame["fallback_rules"] = _split_selection_rules(frame["decision_rules"])
        if spec.get("frame_type") == "timing":
            frame["shared_steps"] = _derive_timing_steps_from_texts(frame)
        if spec.get("frame_type") == "selection":
            frame["shared_steps"] = _filter_steps(_derive_selection_steps(frame), spec)
        else:
            frame["shared_steps"] = _filter_steps(_derive_shared_steps(frame), spec)

        if not any(
            frame.get(field_name)
            for field_name in (
                "shared_steps",
                "decision_rules",
                "preconditions",
                "exceptions",
                "candidate_priority_rules",
                "fallback_rules",
                "author_method_variants",
                "author_variant_overrides",
                "methodological_notes",
                "procedure_outputs",
            )
        ):
            continue

        frame["related_concepts"] = [
            concept
            for concept in _dedupe_list(related)
            if concept not in frame["anchor_concepts"] and concept not in frame["supporting_concepts"]
        ]
        frame.pop("_definitions", None)
        frame.pop("_technical_rules", None)
        frames[frame["id"]] = frame

    return frames
