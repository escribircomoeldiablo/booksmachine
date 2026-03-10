"""LLM-assisted discovery of book-specific family candidates."""

from __future__ import annotations

import json
from pathlib import Path

from .ai_client import ask_llm

_PROMPT_TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "prompts" / "family_discovery.txt"


def load_family_discovery_prompt_template(path: str | None = None) -> str:
    """Load the family discovery prompt template."""
    prompt_path = Path(path) if path else _PROMPT_TEMPLATE_PATH
    return prompt_path.read_text(encoding="utf-8")


def _concept_context(payload: dict[str, object]) -> dict[str, object]:
    return {
        "label": str(payload.get("concept", "")).strip(),
        "definitions": list(payload.get("definitions", []))[:2],
        "terminology": list(payload.get("terminology", []))[:4],
        "relationships": list(payload.get("relationships", []))[:2],
        "source_chunks": list(payload.get("source_chunks", [])),
    }


def build_family_discovery_prompt(
    *,
    concepts: dict[str, dict[str, object]],
    unassigned_concepts: list[str],
    prompt_template: str | None = None,
) -> str:
    """Build the discovery prompt for one book-specific unassigned set."""
    template = prompt_template or load_family_discovery_prompt_template()
    context = {
        "unassigned_concepts": unassigned_concepts,
        "concept_context": {
            concept_name: _concept_context(concepts[concept_name])
            for concept_name in unassigned_concepts
            if concept_name in concepts
        },
    }
    return template.replace("{{INPUT_JSON}}", json.dumps(context, ensure_ascii=False, indent=2))


def _extract_json_block(raw_text: str) -> str:
    stripped = raw_text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3:
            stripped = "\n".join(lines[1:-1]).strip()

    start = stripped.find("{")
    if start < 0:
        raise ValueError("Family discovery response did not contain a JSON object.")

    depth = 0
    for index in range(start, len(stripped)):
        char = stripped[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return stripped[start : index + 1]

    raise ValueError("Family discovery response contained incomplete JSON.")


def parse_family_discovery_response(raw_text: str) -> dict[str, object]:
    """Parse and normalize the LLM discovery output."""
    payload = json.loads(_extract_json_block(raw_text))
    candidate_rows = payload.get("candidate_families", [])
    left_unclustered = payload.get("left_unclustered", [])

    normalized_candidates: list[dict[str, object]] = []
    if isinstance(candidate_rows, list):
        for item in candidate_rows:
            if not isinstance(item, dict):
                continue
            family_label = str(item.get("family_label", "")).strip()
            members = item.get("members", [])
            rationale = str(item.get("rationale", "")).strip()
            if not family_label or not isinstance(members, list):
                continue
            normalized_candidates.append(
                {
                    "family_label": family_label,
                    "members": [member.strip() for member in members if isinstance(member, str) and member.strip()],
                    "rationale": rationale,
                }
            )

    normalized_left = (
        [item.strip() for item in left_unclustered if isinstance(item, str) and item.strip()]
        if isinstance(left_unclustered, list)
        else []
    )
    return {
        "candidate_families": normalized_candidates,
        "left_unclustered": normalized_left,
    }


def discover_family_candidates(
    *,
    concepts: dict[str, dict[str, object]],
    family_payload: dict[str, object],
    llm_callable=None,
    prompt_template_path: str | None = None,
) -> dict[str, object]:
    """Run LLM discovery over currently unassigned concepts."""
    unassigned_concepts = [
        concept_name
        for concept_name in family_payload.get("unassigned_concepts", [])
        if isinstance(concept_name, str) and concept_name in concepts
    ]
    if not unassigned_concepts:
        return {
            "candidate_families": [],
            "left_unclustered": [],
            "discovery_error": None,
        }

    prompt = build_family_discovery_prompt(
        concepts=concepts,
        unassigned_concepts=unassigned_concepts,
        prompt_template=load_family_discovery_prompt_template(prompt_template_path),
    )
    llm = llm_callable or ask_llm
    try:
        raw_text = llm(prompt)
        parsed = parse_family_discovery_response(raw_text)
        parsed["discovery_error"] = None
        return parsed
    except Exception as exc:
        return {
            "candidate_families": [],
            "left_unclustered": list(unassigned_concepts),
            "discovery_error": str(exc),
        }
