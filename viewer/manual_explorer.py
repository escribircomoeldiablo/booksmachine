from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from flask import Flask, abort, jsonify, render_template, request

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = BASE_DIR / "outputs"
TEMPLATE_DIR = BASE_DIR / "viewer" / "templates"
STATIC_DIR = BASE_DIR / "viewer" / "static"

REQUIRED_ARTIFACTS = {
    "concepts": "_knowledge_concepts.json",
    "families": "_knowledge_families.json",
    "ontology": "_knowledge_ontology.json",
    "summary_blocks": "_summary_blocks.txt",
    "summary_chunks": "_summary_chunks.txt",
}
OPTIONAL_ARTIFACTS = {
    "procedure_frames": "_procedure_frames.json",
}

BLOCK_HEADER_RE = re.compile(
    r"^## Block (?P<index>\d+)(?: \(Chunks (?P<start>\d+)-(?P<end>\d+)\))?\s*$",
    re.MULTILINE,
)
CHUNK_HEADER_RE = re.compile(r"^## Chunk (?P<index>\d+)\s*$", re.MULTILINE)
RELATION_DETAIL_RE = re.compile(
    r"(?:details:\s*)?(?:from:\s*(?P<from>[^;]+);\s*)?"
    r"(?:to:\s*(?P<to>[^;]+);\s*)?"
    r"(?:type:\s*(?P<type>[^;]+))?",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class BookArtifacts:
    slug: str
    title: str
    paths: dict[str, Path]


def create_app() -> Flask:
    app = Flask(__name__, template_folder=str(TEMPLATE_DIR), static_folder=str(STATIC_DIR))

    @app.get("/")
    def index() -> str:
        return render_template("explorer.html")

    @app.get("/api/books")
    def books() -> Any:
        discovered = discover_books()
        records = [serialize_book_record(record) for record in discovered]
        default_book = pick_default_book(discovered)
        return jsonify({"books": records, "default_book": default_book.slug if default_book else None})

    @app.get("/api/books/<book_slug>/overview")
    def overview(book_slug: str) -> Any:
        book = get_book(book_slug)
        dataset = load_book_dataset(book)
        return jsonify(
            {
                "book": serialize_book_record(book),
                "families": dataset["family_list"],
                "stats": dataset["stats"],
                "initial_family": dataset["initial_family"],
                "initial_concept": dataset["initial_concept"],
            }
        )

    @app.get("/api/books/<book_slug>/tree")
    def tree(book_slug: str) -> Any:
        family = request.args.get("family", "").strip().lower()
        dataset = load_book_dataset(get_book(book_slug))
        return jsonify(build_family_tree_payload(dataset, family))

    @app.get("/api/books/<book_slug>/concept/<concept_name>")
    def concept(book_slug: str, concept_name: str) -> Any:
        dataset = load_book_dataset(get_book(book_slug))
        return jsonify(build_concept_payload(dataset, concept_name))

    @app.get("/api/books/<book_slug>/search")
    def search(book_slug: str) -> Any:
        query = request.args.get("q", "").strip()
        dataset = load_book_dataset(get_book(book_slug))
        return jsonify({"results": search_dataset(dataset, query)})

    return app


def serialize_book_record(book: BookArtifacts) -> dict[str, Any]:
    return {"slug": book.slug, "title": book.title}


def discover_books() -> list[BookArtifacts]:
    if not OUTPUTS_DIR.exists():
        return []

    candidate_paths: dict[str, dict[str, Path]] = defaultdict(dict)

    for path in OUTPUTS_DIR.iterdir():
        if path.is_dir():
            for artifact_key, suffix in REQUIRED_ARTIFACTS.items():
                child = path / suffix.removeprefix("_")
                if child.exists():
                    candidate_paths[path.name][artifact_key] = child
            for artifact_key, suffix in OPTIONAL_ARTIFACTS.items():
                child = path / suffix.removeprefix("_")
                if child.exists():
                    candidate_paths[path.name][artifact_key] = child
            continue

        for artifact_key, suffix in REQUIRED_ARTIFACTS.items():
            if path.name.endswith(suffix):
                base_name = path.name[: -len(suffix)]
                candidate_paths[base_name][artifact_key] = path
        for artifact_key, suffix in OPTIONAL_ARTIFACTS.items():
            if path.name.endswith(suffix):
                base_name = path.name[: -len(suffix)]
                candidate_paths[base_name][artifact_key] = path

    books: list[BookArtifacts] = []
    for title, paths in sorted(candidate_paths.items()):
        if not paths:
            continue
        books.append(
            BookArtifacts(
                slug=slugify(title),
                title=title,
                paths=paths,
            )
        )
    return books


def pick_default_book(books: list[BookArtifacts]) -> BookArtifacts | None:
    if not books:
        return None
    return max(
        books,
        key=lambda book: (
            extract_volume_number(book.title),
            max(path.stat().st_mtime for path in book.paths.values() if path.exists()),
            book.title,
        ),
    )


def extract_volume_number(title: str) -> int:
    match = re.search(r"\bvol(?:ume)?\s*(\d+)\b", title, re.IGNORECASE)
    return int(match.group(1)) if match else 0


def slugify(value: str) -> str:
    collapsed = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return collapsed or "book"


@lru_cache(maxsize=64)
def books_by_slug() -> dict[str, BookArtifacts]:
    return {book.slug: book for book in discover_books()}


def get_book(book_slug: str) -> BookArtifacts:
    book = books_by_slug().get(book_slug)
    if book is None:
        abort(404, description=f"Unknown book: {book_slug}")
    return book


def load_book_dataset(book: BookArtifacts) -> dict[str, Any]:
    concepts = load_json(book.paths.get("concepts"), default={})
    ontology = load_json(book.paths.get("ontology"), default={})
    families_payload = load_json(book.paths.get("families"), default={})
    procedure_frames = load_json(book.paths.get("procedure_frames"), default={})
    blocks = parse_block_artifacts(read_text(book.paths.get("summary_blocks")))
    chunks = parse_chunk_artifacts(read_text(book.paths.get("summary_chunks")))

    concepts_by_name = normalize_concept_records(concepts, ontology)
    ontology_by_name = normalize_concept_records(ontology, ontology)
    concepts_by_name = merge_concept_maps(concepts_by_name, ontology_by_name)
    family_map, concept_to_families = normalize_families(
        families_payload,
        concepts_by_name,
    )

    enrich_hierarchy(concepts_by_name)
    chunk_to_concepts = build_chunk_to_concepts(concepts_by_name)
    blocks = enrich_blocks(blocks, chunk_to_concepts)
    concept_names = sorted(concepts_by_name)
    block_index_by_concept = build_block_index_by_concept(blocks)

    family_list = build_family_list(family_map, concepts_by_name, concept_to_families)
    initial_family = family_list[0]["label"] if family_list else ""
    initial_concept = first_concept_for_family(initial_family, concepts_by_name, concept_to_families)
    procedure_frames_by_concept = build_procedure_frame_index(procedure_frames, concepts_by_name)

    return {
        "book": book,
        "concepts": concepts_by_name,
        "families": family_map,
        "concept_to_families": concept_to_families,
        "family_list": family_list,
        "blocks": blocks,
        "block_index_by_concept": block_index_by_concept,
        "chunks": chunks,
        "chunk_to_concepts": chunk_to_concepts,
        "concept_names": concept_names,
        "stats": {
            "concept_count": len(concepts_by_name),
            "family_count": len(family_list),
            "block_count": len(blocks),
            "chunk_count": len(chunks),
        },
        "procedure_frames": procedure_frames if isinstance(procedure_frames, dict) else {},
        "procedure_frames_by_concept": procedure_frames_by_concept,
        "initial_family": initial_family,
        "initial_concept": initial_concept,
    }


def load_json(path: Path | None, *, default: Any) -> Any:
    if path is None or not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def read_text(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def normalize_concept_records(primary_payload: Any, fallback_payload: Any) -> dict[str, dict[str, Any]]:
    source = primary_payload if isinstance(primary_payload, dict) and primary_payload else fallback_payload
    if not isinstance(source, dict):
        return {}

    records: dict[str, dict[str, Any]] = {}
    for name, payload in source.items():
        if not isinstance(payload, dict):
            continue
        concept_name = normalize_name(payload.get("concept") or name)
        if not concept_name:
            continue
        records[concept_name] = {
            "concept": concept_name,
            "display_name": payload.get("concept") or name,
            "aliases": unique_texts(payload.get("aliases")),
            "definitions": unique_texts(payload.get("definitions")),
            "technical_rules": unique_texts(payload.get("technical_rules")),
            "procedures": unique_texts(payload.get("procedures")),
            "terminology": unique_texts(payload.get("terminology")),
            "examples": unique_texts(payload.get("examples")),
            "relationships": unique_texts(payload.get("relationships")),
            "shared_procedure": unique_object_list(payload.get("shared_procedure")),
            "decision_rules": unique_object_list(payload.get("decision_rules")),
            "preconditions": unique_object_list(payload.get("preconditions")),
            "exceptions": unique_object_list(payload.get("exceptions")),
            "author_variant_overrides": unique_object_list(payload.get("author_variant_overrides")),
            "procedure_outputs": unique_object_list(payload.get("procedure_outputs")),
            "concept_evidence": payload.get("concept_evidence", {}) if isinstance(payload.get("concept_evidence", {}), dict) else {},
            "procedure_evidence": payload.get("procedure_evidence", {}) if isinstance(payload.get("procedure_evidence", {}), dict) else {},
            "source_chunks": unique_ints(payload.get("source_chunks")),
            "parent_concepts": normalize_names(payload.get("parent_concepts")),
            "child_concepts": normalize_names(payload.get("child_concepts")),
            "related_concepts": normalize_names(payload.get("related_concepts")),
            "belongs_to_families": normalize_names(payload.get("belongs_to_families")),
            "family_members": normalize_names(payload.get("family_members")),
            "node_kind": str(payload.get("node_kind") or "topic"),
        }
    return records


def merge_concept_maps(*maps: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for concept_map in maps:
        for concept_name, record in concept_map.items():
            current = merged.setdefault(
                concept_name,
                {
                    "concept": concept_name,
                    "display_name": record.get("display_name", concept_name),
                    "aliases": [],
                    "definitions": [],
                    "technical_rules": [],
                    "procedures": [],
                    "terminology": [],
                    "examples": [],
                    "relationships": [],
                    "shared_procedure": [],
                    "decision_rules": [],
                    "preconditions": [],
                    "exceptions": [],
                    "author_variant_overrides": [],
                    "procedure_outputs": [],
                    "concept_evidence": {},
                    "procedure_evidence": {},
                    "source_chunks": [],
                    "parent_concepts": [],
                    "child_concepts": [],
                    "related_concepts": [],
                    "belongs_to_families": [],
                    "family_members": [],
                    "node_kind": record.get("node_kind", "topic"),
                },
            )
            for key in (
                "aliases",
                "definitions",
                "technical_rules",
                "procedures",
                "terminology",
                "examples",
                "relationships",
                "shared_procedure",
                "decision_rules",
                "preconditions",
                "exceptions",
                "author_variant_overrides",
                "procedure_outputs",
                "source_chunks",
                "parent_concepts",
                "child_concepts",
                "related_concepts",
                "belongs_to_families",
                "family_members",
            ):
                current[key] = merge_lists(current[key], record.get(key, []))
            if not current["display_name"]:
                current["display_name"] = record.get("display_name", concept_name)
            if current.get("node_kind") == "topic" and record.get("node_kind"):
                current["node_kind"] = record["node_kind"]
    return merged


def merge_lists(left: list[Any], right: list[Any]) -> list[Any]:
    seen: list[Any] = []
    for item in list(left) + list(right):
        if item not in seen:
            seen.append(item)
    return seen


def normalize_families(
    payload: Any,
    concepts_by_name: dict[str, dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, set[str]]]:
    family_map: dict[str, dict[str, Any]] = {}
    concept_to_families: dict[str, set[str]] = defaultdict(set)

    family_entries = payload.get("families", []) if isinstance(payload, dict) else []
    for entry in family_entries:
        if not isinstance(entry, dict):
            continue
        label = normalize_name(entry.get("label") or entry.get("family_id"))
        if not label:
            continue
        members = normalize_names(entry.get("members"))
        family_map[label] = {
            "id": str(entry.get("family_id") or label),
            "label": label,
            "members": members,
        }
        for member in members:
            concept_to_families[member].add(label)

    for concept_name, record in concepts_by_name.items():
        for family in normalize_names(record.get("belongs_to_families")):
            concept_to_families[concept_name].add(family)
            family_record = family_map.setdefault(
                family,
                {"id": slugify(family), "label": family, "members": []},
            )
            if concept_name not in family_record["members"]:
                family_record["members"].append(concept_name)

    return family_map, concept_to_families


def enrich_hierarchy(concepts_by_name: dict[str, dict[str, Any]]) -> None:
    for concept_name, record in concepts_by_name.items():
        for child in list(record["child_concepts"]):
            child_record = concepts_by_name.get(child)
            if child_record is None:
                continue
            if concept_name not in child_record["parent_concepts"]:
                child_record["parent_concepts"].append(concept_name)

        for parent in list(record["parent_concepts"]):
            parent_record = concepts_by_name.get(parent)
            if parent_record is None:
                continue
            if concept_name not in parent_record["child_concepts"]:
                parent_record["child_concepts"].append(concept_name)


def parse_block_artifacts(text: str) -> list[dict[str, Any]]:
    if not text.strip():
        return []
    matches = list(BLOCK_HEADER_RE.finditer(text))
    blocks: list[dict[str, Any]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        blocks.append(
            {
                "block_id": f"Block {match.group('index')}",
                "block_index": int(match.group("index")),
                "chunk_start": int(match.group("start")) if match.group("start") else None,
                "chunk_end": int(match.group("end")) if match.group("end") else None,
                "block_text": body,
                "related_concepts": [],
            }
        )
    return blocks


def parse_chunk_artifacts(text: str) -> list[dict[str, Any]]:
    if not text.strip():
        return []
    matches = list(CHUNK_HEADER_RE.finditer(text))
    chunks: list[dict[str, Any]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        chunks.append(
            {
                "chunk_id": int(match.group("index")),
                "chunk_text": text[start:end].strip(),
            }
        )
    return chunks


def build_chunk_to_concepts(concepts_by_name: dict[str, dict[str, Any]]) -> dict[int, list[str]]:
    chunk_map: dict[int, list[str]] = defaultdict(list)
    for concept_name, record in concepts_by_name.items():
        for chunk_id in record["source_chunks"]:
            if concept_name not in chunk_map[chunk_id]:
                chunk_map[chunk_id].append(concept_name)
    for chunk_id in chunk_map:
        chunk_map[chunk_id].sort()
    return dict(chunk_map)


def enrich_blocks(
    blocks: list[dict[str, Any]],
    chunk_to_concepts: dict[int, list[str]],
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for block in blocks:
        related: list[str] = []
        if block["chunk_start"] is not None and block["chunk_end"] is not None:
            for chunk_id in range(block["chunk_start"], block["chunk_end"] + 1):
                related = merge_lists(related, chunk_to_concepts.get(chunk_id, []))
        block["related_concepts"] = related
        enriched.append(block)
    return enriched


def build_block_index_by_concept(blocks: list[dict[str, Any]]) -> dict[str, list[int]]:
    index: dict[str, list[int]] = defaultdict(list)
    for block in blocks:
        block_index = block["block_index"]
        for concept_name in block["related_concepts"]:
            if block_index not in index[concept_name]:
                index[concept_name].append(block_index)
    return dict(index)


def build_procedure_frame_index(
    payload: Any,
    concepts_by_name: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    if not isinstance(payload, dict):
        return {}
    index: dict[str, dict[str, Any]] = {}
    for frame_id, raw in payload.items():
        if not isinstance(raw, dict):
            continue
        record = {
            "id": str(raw.get("id") or frame_id),
            "label": str(raw.get("label") or frame_id),
            "goal": str(raw.get("goal") or "").strip(),
            "anchor_concepts": normalize_names(raw.get("anchor_concepts")),
            "supporting_concepts": normalize_names(raw.get("supporting_concepts")),
            "shared_steps": unique_object_list(raw.get("shared_steps")),
            "decision_rules": unique_object_list(raw.get("decision_rules")),
            "preconditions": unique_object_list(raw.get("preconditions")),
            "exceptions": unique_object_list(raw.get("exceptions")),
            "author_variant_overrides": unique_object_list(raw.get("author_variant_overrides")),
            "procedure_outputs": unique_object_list(raw.get("procedure_outputs")),
            "related_concepts": normalize_names(raw.get("related_concepts")),
            "evidence": raw.get("evidence", {}) if isinstance(raw.get("evidence", {}), dict) else {},
            "source_chunks": unique_ints(raw.get("source_chunks")),
        }
        members = record["anchor_concepts"] + [c for c in record["supporting_concepts"] if c not in record["anchor_concepts"]]
        for concept_name in members:
            if concept_name not in concepts_by_name:
                continue
            index[concept_name] = record
    return index


def build_family_list(
    family_map: dict[str, dict[str, Any]],
    concepts_by_name: dict[str, dict[str, Any]],
    concept_to_families: dict[str, set[str]],
) -> list[dict[str, Any]]:
    families: list[dict[str, Any]] = []
    for family_label, record in family_map.items():
        members = [
            concept_name
            for concept_name in concepts_by_name
            if family_label in concept_to_families.get(concept_name, set())
        ]
        members = sorted(set(members))
        families.append(
            {
                "id": record["id"],
                "label": family_label,
                "concept_count": len(members),
                "members": members,
            }
        )
    families.sort(key=lambda item: (-item["concept_count"], item["label"]))
    return families


def first_concept_for_family(
    family_label: str,
    concepts_by_name: dict[str, dict[str, Any]],
    concept_to_families: dict[str, set[str]],
) -> str | None:
    if not family_label:
        return next(iter(sorted(concepts_by_name)), None)
    family_concepts = [
        name
        for name in concepts_by_name
        if family_label in concept_to_families.get(name, set())
    ]
    if not family_concepts:
        return next(iter(sorted(concepts_by_name)), None)
    family_concepts = sorted(family_concepts)
    tree = build_family_tree(concepts_by_name, concept_to_families, family_label)
    first_tree_concept = first_tree_node(tree)
    return first_tree_concept or family_concepts[0]


def build_family_tree_payload(dataset: dict[str, Any], family_label: str) -> dict[str, Any]:
    concepts_by_name = dataset["concepts"]
    concept_to_families = dataset["concept_to_families"]
    normalized_family = normalize_name(family_label) or dataset["initial_family"]
    tree = build_family_tree(concepts_by_name, concept_to_families, normalized_family)
    selected = first_tree_node(tree) or first_concept_for_family(
        normalized_family,
        concepts_by_name,
        concept_to_families,
    )
    return {"family": normalized_family, "tree": tree, "selected_concept": selected}


def build_family_tree(
    concepts_by_name: dict[str, dict[str, Any]],
    concept_to_families: dict[str, set[str]],
    family_label: str,
) -> dict[str, Any]:
    relevant = sorted(
        concept_name
        for concept_name in concepts_by_name
        if family_label in concept_to_families.get(concept_name, set())
    )
    relevant_set = set(relevant)

    roots = [
        concept_name
        for concept_name in relevant
        if not any(parent in relevant_set for parent in concepts_by_name[concept_name]["parent_concepts"])
    ]
    if not roots:
        roots = relevant

    def make_node(concept_name: str, trail: set[str]) -> dict[str, Any]:
        if concept_name in trail:
            return leaf_node(concepts_by_name, concept_name)
        record = concepts_by_name[concept_name]
        child_candidates = [
            child for child in record["child_concepts"] if child in relevant_set and child != concept_name
        ]
        children = [
            make_node(child, trail | {concept_name})
            for child in sorted(child_candidates)
        ]
        return {
            "id": concept_name,
            "label": record["display_name"],
            "kind": record["node_kind"],
            "children": children,
        }

    return {
        "id": f"family::{family_label}",
        "label": family_label,
        "kind": "family_root",
        "children": [make_node(root, set()) for root in roots],
    }


def leaf_node(concepts_by_name: dict[str, dict[str, Any]], concept_name: str) -> dict[str, Any]:
    record = concepts_by_name[concept_name]
    return {
        "id": concept_name,
        "label": record["display_name"],
        "kind": record["node_kind"],
        "children": [],
    }


def first_tree_node(tree: dict[str, Any]) -> str | None:
    for child in tree.get("children", []):
        result = descend_first_concept(child)
        if result:
            return result
    return None


def descend_first_concept(node: dict[str, Any]) -> str | None:
    if node.get("kind") != "family_root":
        return node.get("id")
    for child in node.get("children", []):
        result = descend_first_concept(child)
        if result:
            return result
    return None


def build_concept_payload(dataset: dict[str, Any], raw_concept_name: str) -> dict[str, Any]:
    concept_name = normalize_name(raw_concept_name)
    record = dataset["concepts"].get(concept_name)
    if record is None:
        abort(404, description=f"Unknown concept: {raw_concept_name}")

    families = sorted(dataset["concept_to_families"].get(concept_name, set()))
    primary_family = families[0] if families else ""
    hierarchy = build_breadcrumb(dataset["concepts"], concept_name, primary_family)
    associative = categorize_associative_relationships(record)
    associative_display = {
        key: display_mixed_values(dataset["concepts"], values) for key, values in associative.items()
    }
    concept_blocks = blocks_for_concept(dataset, concept_name)
    concept_chunks = chunks_for_concept(dataset, concept_name)
    related_concepts = build_related_concepts(dataset, concept_name, associative)
    procedure_frame = dataset["procedure_frames_by_concept"].get(concept_name)
    procedure_frame_payload = None
    if procedure_frame:
        procedure_frame_payload = {
            "id": procedure_frame["id"],
            "label": procedure_frame["label"],
            "goal": procedure_frame["goal"],
            "anchor_concepts": display_names(dataset["concepts"], procedure_frame["anchor_concepts"]),
            "supporting_concepts": display_names(dataset["concepts"], procedure_frame["supporting_concepts"]),
            "shared_steps": procedure_frame["shared_steps"],
            "decision_rules": procedure_frame["decision_rules"],
            "preconditions": procedure_frame["preconditions"],
            "exceptions": procedure_frame["exceptions"],
            "author_variant_overrides": procedure_frame["author_variant_overrides"],
            "procedure_outputs": procedure_frame["procedure_outputs"],
            "related_concepts": display_names(dataset["concepts"], procedure_frame["related_concepts"]),
            "source_chunks": procedure_frame["source_chunks"],
        }

    return {
        "concept_name": record["display_name"],
        "concept_key": concept_name,
        "family": primary_family or "Unassigned",
        "families": families,
        "definition_primary": record["definitions"][0] if record["definitions"] else None,
        "definition_variants": record["definitions"][1:],
        "breadcrumb": hierarchy,
        "node_kind": record["node_kind"],
        "relations": {
            "belongs_to": families,
            "parent": display_names(dataset["concepts"], record["parent_concepts"]),
            "children": display_names(dataset["concepts"], record["child_concepts"]),
            "related_to": associative_display["related_to"],
            "contrasts_with": associative_display["contrasts_with"],
            "depends_on": associative_display["depends_on"],
            "used_in": associative_display["used_in"],
        },
        "shared_procedure": record["shared_procedure"],
        "decision_rules": record["decision_rules"],
        "preconditions": record["preconditions"],
        "exceptions": record["exceptions"],
        "author_variant_overrides": record["author_variant_overrides"],
        "procedure_outputs": record["procedure_outputs"],
        "concept_evidence": record["concept_evidence"],
        "procedure_evidence": record["procedure_evidence"],
        "terminology": record["terminology"],
        "synonyms": record["aliases"],
        "variants": record["family_members"],
        "related_concepts": display_names(dataset["concepts"], related_concepts),
        "technical_rules": record["technical_rules"],
        "procedures": record["procedures"],
        "examples": record["examples"],
        "procedure_frame": procedure_frame_payload,
        "metrics": {
            "source_chunks_count": len(record["source_chunks"]),
            "summary_blocks_count": len(concept_blocks),
            "direct_relations_count": count_direct_relations(record, associative_display, families),
        },
        "source_chunks": concept_chunks,
        "summary_blocks": concept_blocks,
    }


def build_breadcrumb(
    concepts_by_name: dict[str, dict[str, Any]],
    concept_name: str,
    family_label: str,
) -> list[str]:
    path: list[str] = []
    visited: set[str] = set()
    current = concept_name
    while current and current not in visited:
        visited.add(current)
        path.append(concepts_by_name.get(current, {}).get("display_name", current))
        parents = concepts_by_name.get(current, {}).get("parent_concepts", [])
        current = sorted(parents)[0] if parents else ""
    path.reverse()
    if family_label:
        family_display = family_label
        if not path or normalize_name(path[0]) != family_label:
            path.insert(0, family_display)
    return path


def categorize_associative_relationships(record: dict[str, Any]) -> dict[str, list[str]]:
    categorized = {
        "related_to": display_names_from_keys(record["related_concepts"]),
        "contrasts_with": [],
        "depends_on": [],
        "used_in": [],
    }
    for relation in record["relationships"]:
        parsed = parse_relation_text(relation, record["concept"])
        if parsed is None:
            if relation not in categorized["related_to"]:
                categorized["related_to"].append(relation)
            continue
        categorized[parsed["bucket"]] = merge_lists(categorized[parsed["bucket"]], [parsed["target"]])
    return categorized


def parse_relation_text(relation: str, concept_name: str) -> dict[str, str] | None:
    match = RELATION_DETAIL_RE.search(relation)
    if not match:
        return None
    source = normalize_name(match.group("from") or "")
    target = normalize_name(match.group("to") or "")
    rel_type = (match.group("type") or "").strip().lower()
    if not source and not target:
        return None
    counterpart = target if source == concept_name and target else source if target == concept_name else target or source
    if not counterpart:
        return None
    bucket = "related_to"
    if "contrast" in rel_type or "oppos" in rel_type:
        bucket = "contrasts_with"
    elif "depend" in rel_type or "criteria" in rel_type or "require" in rel_type:
        bucket = "depends_on"
    elif "use" in rel_type or "application" in rel_type or "assignment" in rel_type:
        bucket = "used_in"
    return {"bucket": bucket, "target": counterpart}


def blocks_for_concept(dataset: dict[str, Any], concept_name: str) -> list[dict[str, Any]]:
    record = dataset["concepts"][concept_name]
    concept_chunks = set(record["source_chunks"])
    concept_display = record["display_name"].lower()
    matched: list[dict[str, Any]] = []

    for block in dataset["blocks"]:
        chunk_match = False
        if block["chunk_start"] is not None and block["chunk_end"] is not None:
            block_range = range(block["chunk_start"], block["chunk_end"] + 1)
            chunk_match = any(chunk_id in concept_chunks for chunk_id in block_range)
        text_match = concept_display in block["block_text"].lower()
        if not chunk_match and not text_match:
            continue
        matched.append(
            {
                "block_id": block["block_id"],
                "block_index": block["block_index"],
                "block_text": block["block_text"],
                "related_concepts": display_names(dataset["concepts"], block["related_concepts"][:12]),
            }
        )
    matched.sort(key=lambda item: item["block_index"])
    return matched


def build_related_concepts(
    dataset: dict[str, Any],
    concept_name: str,
    associative: dict[str, list[str]],
    limit: int = 10,
) -> list[str]:
    concepts = dataset["concepts"]
    record = concepts[concept_name]
    concept_to_families = dataset["concept_to_families"]
    block_index_by_concept = dataset["block_index_by_concept"]

    scores: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "direct": 0,
            "cooccurrence": 0,
            "terminology": 0,
            "reasons": set(),
        }
    )

    def add_candidate(candidate: str, *, direct: int = 0, cooccurrence: int = 0, terminology: int = 0, reason: str = "") -> None:
        candidate_name = normalize_name(candidate)
        if not candidate_name or candidate_name == concept_name or candidate_name not in concepts:
            return
        entry = scores[candidate_name]
        entry["direct"] = max(entry["direct"], direct)
        entry["cooccurrence"] += cooccurrence
        entry["terminology"] += terminology
        if reason:
            entry["reasons"].add(reason)

    for parent in record["parent_concepts"]:
        add_candidate(parent, direct=5, reason="parent")
        for sibling in concepts.get(parent, {}).get("child_concepts", []):
            if sibling != concept_name:
                add_candidate(sibling, direct=3, reason="sibling")

    for child in record["child_concepts"]:
        add_candidate(child, direct=4, reason="child")

    for related in record["related_concepts"]:
        add_candidate(related, direct=4, reason="related")

    for bucket in ("related_to", "contrasts_with", "depends_on", "used_in"):
        for related in associative.get(bucket, []):
            add_candidate(related, direct=3, reason=bucket)

    for family in concept_to_families.get(concept_name, set()):
        add_candidate(family, direct=4, reason="family")
        family_record = concepts.get(family, {})
        for member in family_record.get("family_members", []):
            if member != concept_name:
                add_candidate(member, direct=3, reason="family_member")
        for peer_name, peer_families in concept_to_families.items():
            if peer_name != concept_name and family in peer_families:
                add_candidate(peer_name, direct=2, reason="shared_family")

    concept_block_indexes = set(block_index_by_concept.get(concept_name, []))
    for candidate_name, block_indexes in block_index_by_concept.items():
        if candidate_name == concept_name:
            continue
        overlap = len(concept_block_indexes.intersection(block_indexes))
        if overlap:
            add_candidate(candidate_name, cooccurrence=overlap, reason="shared_blocks")

    source_terms = concept_signal_terms(record)
    for candidate_name, candidate_record in concepts.items():
        if candidate_name == concept_name:
            continue
        overlap = shared_signal_terms(source_terms, concept_signal_terms(candidate_record))
        if overlap:
            add_candidate(candidate_name, terminology=overlap, reason="shared_terminology")

    ranked = sorted(
        scores.items(),
        key=lambda item: (
            -item[1]["direct"],
            -item[1]["cooccurrence"],
            -item[1]["terminology"],
            concepts[item[0]].get("display_name", item[0]).lower(),
        ),
    )
    return [candidate_name for candidate_name, _score in ranked[:limit]]


def chunks_for_concept(dataset: dict[str, Any], concept_name: str) -> list[dict[str, Any]]:
    record = dataset["concepts"][concept_name]
    chunk_index = {chunk["chunk_id"]: chunk for chunk in dataset["chunks"]}
    evidence: list[dict[str, Any]] = []
    for chunk_id in record["source_chunks"]:
        chunk = chunk_index.get(chunk_id)
        evidence.append(
            {
                "chunk_id": chunk_id,
                "chunk_text": chunk["chunk_text"] if chunk else "Chunk summary unavailable.",
            }
        )
    return evidence


def concept_signal_terms(record: dict[str, Any]) -> set[str]:
    values = [record.get("concept", ""), record.get("display_name", "")]
    values.extend(record.get("aliases", []))
    values.extend(record.get("terminology", []))
    return {term for value in values for term in expand_signal_term(value)}


def expand_signal_term(value: Any) -> set[str]:
    text = normalize_name(value)
    if not text:
        return set()
    variants = {text}
    simplified = re.sub(r"[^\w\s]", "", text).strip()
    if simplified:
        variants.add(simplified)
    if text.endswith("s") and len(text) > 3:
        variants.add(text[:-1])
    if simplified.endswith("s") and len(simplified) > 3:
        variants.add(simplified[:-1])
    return {variant for variant in variants if variant}


def shared_signal_terms(left: set[str], right: set[str]) -> int:
    return len(left.intersection(right))


def count_direct_relations(
    record: dict[str, Any],
    associative: dict[str, list[str]],
    families: list[str],
) -> int:
    return sum(
        len(values)
        for values in (
            families,
            record["parent_concepts"],
            record["child_concepts"],
            associative["related_to"],
            associative["contrasts_with"],
            associative["depends_on"],
            associative["used_in"],
        )
    )


def search_dataset(dataset: dict[str, Any], query: str) -> list[dict[str, Any]]:
    q = normalize_name(query)
    if not q:
        return []

    results: list[dict[str, Any]] = []
    for concept_name, record in dataset["concepts"].items():
        family_labels = sorted(dataset["concept_to_families"].get(concept_name, set()))
        haystack = " ".join(
            [
                concept_name,
                " ".join(record["terminology"]),
                " ".join(record["aliases"]),
                " ".join(family_labels),
            ]
        ).lower()
        if q not in haystack:
            continue
        results.append(
            {
                "type": "concept",
                "concept_key": concept_name,
                "concept_name": record["display_name"],
                "family": family_labels[0] if family_labels else "Unassigned",
            }
        )

    for family in dataset["family_list"]:
        if q not in family["label"]:
            continue
        results.append(
            {
                "type": "family",
                "family": family["label"],
                "concept_count": family["concept_count"],
            }
        )

    results.sort(key=lambda item: (item["type"] != "concept", item.get("concept_name", item.get("family", ""))))
    return results[:25]


def display_names(concepts_by_name: dict[str, dict[str, Any]], concept_keys: list[str]) -> list[str]:
    names: list[str] = []
    for key in concept_keys:
        display = concepts_by_name.get(key, {}).get("display_name", key)
        if display not in names:
            names.append(display)
    return names


def display_names_from_keys(values: list[str]) -> list[str]:
    return [value for value in values if value]


def display_mixed_values(
    concepts_by_name: dict[str, dict[str, Any]],
    values: list[str],
) -> list[str]:
    rendered: list[str] = []
    for value in values:
        normalized = normalize_name(value)
        display = concepts_by_name.get(normalized, {}).get("display_name", value)
        if display not in rendered:
            rendered.append(display)
    return rendered


def unique_texts(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    output: list[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in output:
            output.append(text)
    return output


def unique_ints(values: Any) -> list[int]:
    if not isinstance(values, list):
        return []
    output: list[int] = []
    for value in values:
        try:
            number = int(value)
        except (TypeError, ValueError):
            continue
        if number not in output:
            output.append(number)
    return output


def unique_object_list(values: Any) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    output: list[dict[str, Any]] = []
    seen: list[dict[str, Any]] = []
    for value in values:
        if not isinstance(value, dict):
            continue
        if value in seen:
            continue
        seen.append(value)
        output.append(value)
    return output


def normalize_names(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    output: list[str] = []
    for value in values:
        normalized = normalize_name(value)
        if normalized and normalized not in output:
            output.append(normalized)
    return output


def normalize_name(value: Any) -> str:
    text = str(value or "").strip()
    return re.sub(r"\s+", " ", text).lower()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the manual explorer viewer.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=5050, type=int)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    app = create_app()
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
