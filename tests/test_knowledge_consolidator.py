from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.knowledge_consolidator import (
    _build_canonical_concepts,
    _build_family_candidates_payload,
    _build_family_payload,
    _build_taxonomy_comparison_payload,
    _build_taxonomy_audit_payload,
    _build_taxonomy_output_path,
    _export_taxonomy_audit,
    build_family_candidates_output_path,
    build_concept_index,
    build_concepts_output_path,
    build_families_output_path,
    build_knowledge_family_candidates,
    build_knowledge_families,
    build_knowledge_ontology,
    consolidate_knowledge_chunks,
    export_concepts,
    export_family_candidates,
    export_families,
    load_chunk_knowledge,
    main,
    merge_concept_knowledge,
    normalize_concepts,
)


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


class KnowledgeConsolidatorTests(unittest.TestCase):
    def test_main_builds_selected_artifact_and_prints_output_path(self) -> None:
        stdout = io.StringIO()
        with (
            patch.object(sys, "argv", ["knowledge_consolidator", "outputs/book_knowledge_chunks.jsonl", "--artifact", "families"]),
            patch("src.knowledge_consolidator.build_knowledge_families", return_value="outputs/book_knowledge_families.json") as families_mock,
            patch("sys.stdout", stdout),
        ):
            main()

        families_mock.assert_called_once_with("outputs/book_knowledge_chunks.jsonl", None)
        self.assertEqual(stdout.getvalue().strip(), "outputs/book_knowledge_families.json")

    def test_main_passes_ontology_only_flags(self) -> None:
        stdout = io.StringIO()
        with (
            patch.object(
                sys,
                "argv",
                [
                    "knowledge_consolidator",
                    "outputs/book_knowledge_chunks.jsonl",
                    "--artifact",
                    "ontology",
                    "--reuse-existing-families",
                    "--skip-family-candidates",
                ],
            ),
            patch("src.knowledge_consolidator.build_knowledge_ontology", return_value="outputs/book_knowledge_ontology.json") as ontology_mock,
            patch("sys.stdout", stdout),
        ):
            main()

        ontology_mock.assert_called_once_with(
            "outputs/book_knowledge_chunks.jsonl",
            None,
            reuse_existing_families=True,
            skip_family_candidates=True,
        )
        self.assertEqual(stdout.getvalue().strip(), "outputs/book_knowledge_ontology.json")

    def test_main_builds_all_artifacts_in_order(self) -> None:
        stdout = io.StringIO()
        with (
            patch.object(sys, "argv", ["knowledge_consolidator", "outputs/book_knowledge_chunks.jsonl", "--artifact", "all"]),
            patch("src.knowledge_consolidator.consolidate_knowledge_chunks", return_value="outputs/book_knowledge_concepts.json") as concepts_mock,
            patch("src.knowledge_consolidator.build_knowledge_families", return_value="outputs/book_knowledge_families.json") as families_mock,
            patch(
                "src.knowledge_consolidator.build_knowledge_family_candidates",
                return_value="outputs/book_knowledge_family_candidates.json",
            ) as candidates_mock,
            patch("src.knowledge_consolidator.build_knowledge_ontology", return_value="outputs/book_knowledge_ontology.json") as ontology_mock,
            patch("src.knowledge_consolidator.build_procedural_audit", return_value="outputs/book_procedural_audit.json") as procedural_mock,
            patch("src.knowledge_consolidator.build_procedure_frames_artifact", return_value="outputs/book_procedure_frames.json") as frames_mock,
            patch("sys.stdout", stdout),
        ):
            main()

        concepts_mock.assert_called_once_with("outputs/book_knowledge_chunks.jsonl")
        families_mock.assert_called_once_with("outputs/book_knowledge_chunks.jsonl")
        candidates_mock.assert_called_once_with("outputs/book_knowledge_chunks.jsonl")
        ontology_mock.assert_called_once_with("outputs/book_knowledge_chunks.jsonl")
        procedural_mock.assert_called_once_with("outputs/book_knowledge_chunks.jsonl")
        frames_mock.assert_called_once_with("outputs/book_knowledge_chunks.jsonl")
        self.assertEqual(
            stdout.getvalue().strip().splitlines(),
            [
                "outputs/book_knowledge_concepts.json",
                "outputs/book_knowledge_families.json",
                "outputs/book_knowledge_family_candidates.json",
                "outputs/book_knowledge_ontology.json",
                "outputs/book_procedural_audit.json",
                "outputs/book_procedure_frames.json",
            ],
        )

    def test_load_chunk_knowledge_uses_audit_sidecar_and_skips_skipped_chunks(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            chunks_path = Path(tmpdir) / "Book_knowledge_chunks.jsonl"
            audit_path = Path(tmpdir) / "Book_knowledge_audit.jsonl"
            _write_jsonl(
                chunks_path,
                [
                    {
                        "chunk_id": "chunk_0_0_10",
                        "concepts": ["Whole-sign houses"],
                        "definitions": ["d1"],
                        "technical_rules": [],
                        "procedures": [],
                        "terminology": [],
                        "relationships": [],
                        "examples": [],
                        "ambiguities": [],
                    },
                    {
                        "chunk_id": "chunk_1_10_20",
                        "concepts": ["Angular Houses"],
                        "definitions": ["d2"],
                        "technical_rules": [],
                        "procedures": [],
                        "terminology": [],
                        "relationships": [],
                        "examples": [],
                        "ambiguities": [],
                    },
                ],
            )
            _write_jsonl(
                audit_path,
                [
                    {"chunk_id": "chunk_0_0_10", "chunk_index": 1, "decision": "extract"},
                    {"chunk_id": "chunk_1_10_20", "chunk_index": 2, "decision": "skip"},
                ],
            )

            rows = load_chunk_knowledge(str(chunks_path))

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["chunk_index"], 1)
            self.assertEqual(rows[0]["concepts"], ["Whole-sign houses"])

    def test_normalize_concepts_attaches_internal_canonical_names(self) -> None:
        rows = normalize_concepts(
            [
                {
                    "chunk_index": 5,
                    "concepts": ["Whole-sign houses", "Whole sign houses", "Angular Houses"],
                }
            ]
        )

        self.assertEqual(
            rows[0]["_normalized_concepts"],
            ["whole sign house system", "angular house"],
        )
        self.assertEqual(rows[0]["concepts"], ["Whole-sign houses", "Whole sign houses", "Angular Houses"])

    def test_build_concept_index_preserves_first_seen_order_without_duplicates(self) -> None:
        concept_index = build_concept_index(
            [
                {"chunk_index": 7, "_normalized_concepts": ["angular house", "succedent house"]},
                {"chunk_index": 8, "_normalized_concepts": ["angular house", "cadent house"]},
                {"chunk_index": 8, "_normalized_concepts": ["angular house"]},
                {"chunk_index": 9, "_normalized_concepts": ["succedent house", "cadent house"]},
            ]
        )

        self.assertEqual(concept_index["angular house"], [7, 8])
        self.assertEqual(concept_index["succedent house"], [7, 9])
        self.assertEqual(concept_index["cadent house"], [8, 9])

    def test_merge_concept_knowledge_combines_fields_and_dedupes_exact_text(self) -> None:
        chunks = [
            {
                "chunk_index": 7,
                "_normalized_concepts": ["angular house"],
                "definitions": ["Angular houses are strong."],
                "technical_rules": ["Planets are strongest near angles."],
                "procedures": ["Assess proximity to the angles."],
                "terminology": ["Kentron"],
                "examples": ["Mars in the 10th."],
                "relationships": ["Angular houses oppose cadent houses."],
            },
            {
                "chunk_index": 8,
                "_normalized_concepts": ["angular house"],
                "definitions": ["Angular houses are strong.", "Angular houses mark cardinal points."],
                "technical_rules": ["Planets are strongest near angles."],
                "procedures": ["Assess proximity to the angles.", "Classify 1, 4, 7, and 10 as angular."],
                "terminology": ["Kentron", "Cardo"],
                "examples": ["Mars in the 10th."],
                "relationships": ["Angular houses oppose cadent houses.", "Angular triads flank angular houses."],
            },
        ]

        merged = merge_concept_knowledge({"angular house": [7, 8]}, chunks)

        self.assertEqual(merged["angular house"]["source_chunks"], [7, 8])
        self.assertEqual(
            merged["angular house"]["definitions"],
            ["Angular houses are strong.", "Angular houses mark cardinal points."],
        )
        self.assertEqual(merged["angular house"]["terminology"], ["Kentron", "Cardo"])
        self.assertEqual(
            merged["angular house"]["relationships"],
            ["Angular houses oppose cadent houses.", "Angular triads flank angular houses."],
        )

    def test_merge_concept_knowledge_derives_shared_procedure_from_multiple_rules(self) -> None:
        chunks = [
            {
                "chunk_index": 8,
                "_normalized_concepts": ["predominator"],
                "definitions": [],
                "technical_rules": [],
                "procedures": [],
                "terminology": ["Predominator"],
                "examples": [],
                "relationships": [],
                "decision_rules": [
                    {
                        "condition": "the sect light is cadent",
                        "outcome": "examine the contrary light",
                        "related_steps": [],
                    },
                    {
                        "condition": "both lights are cadent",
                        "outcome": "the Ascendant has the predomination",
                        "related_steps": [],
                    },
                ],
                "preconditions": [],
                "exceptions": [],
                "author_variants": [],
                "procedure_outputs": [],
            }
        ]

        merged = merge_concept_knowledge({"predominator": [8]}, chunks)

        self.assertEqual(
            [step["text"] for step in merged["predominator"]["shared_procedure"]],
            [
                "If the sect light is cadent, then examine the contrary light",
                "If both lights are cadent, then the Ascendant has the predomination",
            ],
        )

    def test_merge_concept_knowledge_keeps_shared_procedure_empty_when_multiple_authors_present(self) -> None:
        chunks = [
            {
                "chunk_index": 8,
                "_normalized_concepts": ["predominator"],
                "definitions": [],
                "technical_rules": [],
                "procedures": [],
                "terminology": ["Predominator"],
                "examples": [],
                "relationships": [],
                "decision_rules": [
                    {
                        "condition": "the sect light is cadent",
                        "outcome": "examine the contrary light",
                        "related_steps": [],
                    },
                    {
                        "condition": "both lights are cadent",
                        "outcome": "the Ascendant has the predomination",
                        "related_steps": [],
                    },
                ],
                "preconditions": [],
                "exceptions": [],
                "author_variants": [
                    {"author": "Porphyry", "kind": "variant", "text": "Porphyry variant", "related_steps": []},
                    {"author": "Valens", "kind": "variant", "text": "Valens variant", "related_steps": []},
                ],
                "procedure_outputs": [],
            }
        ]

        merged = merge_concept_knowledge({"predominator": [8]}, chunks)

        self.assertEqual(merged["predominator"]["shared_procedure"], [])

    def test_merge_concept_knowledge_matches_procedural_aliases_to_anchor_concept(self) -> None:
        chunks = [
            {
                "chunk_index": 8,
                "concepts": ["Predomination of the light in a chart"],
                "_normalized_concepts": ["predomination of the light in a chart"],
                "definitions": [],
                "technical_rules": [],
                "procedures": [],
                "terminology": [],
                "examples": [],
                "relationships": [],
                "decision_rules": [
                    {
                        "condition": "the sect light is cadent",
                        "outcome": "examine the contrary light",
                        "related_steps": [],
                    }
                ],
                "preconditions": [],
                "exceptions": [],
                "author_variants": [],
                "procedure_outputs": [],
            }
        ]

        merged = merge_concept_knowledge({"predominator": [8]}, chunks)

        self.assertEqual(len(merged["predominator"]["decision_rules"]), 1)
        self.assertEqual(
            merged["predominator"]["decision_rules"][0]["outcome"],
            "examine the contrary light",
        )

    def test_merge_concept_knowledge_serializes_existing_if_rules_without_double_if(self) -> None:
        chunks = [
            {
                "chunk_index": 8,
                "_normalized_concepts": ["predominator"],
                "definitions": [],
                "technical_rules": [],
                "procedures": [],
                "terminology": [],
                "examples": [],
                "relationships": [],
                "decision_rules": [
                    {
                        "condition": "If the Moon is ascending in the east",
                        "outcome": "the Moon will be the Predominator",
                        "related_steps": [],
                    }
                ],
                "preconditions": [],
                "exceptions": [],
                "author_variants": [],
                "procedure_outputs": [],
            }
        ]

        merged = merge_concept_knowledge({"predominator": [8]}, chunks)

        self.assertEqual(
            merged["predominator"]["procedures"],
            ["If the Moon is ascending in the east, then the Moon will be the Predominator."],
        )

    def test_merge_concept_knowledge_does_not_fallback_procedural_rules_into_house_system(self) -> None:
        chunks = [
            {
                "chunk_index": 8,
                "concepts": ["Predominator", "House system"],
                "_normalized_concepts": ["predominator", "house system"],
                "definitions": [],
                "technical_rules": [],
                "procedures": [],
                "terminology": [],
                "examples": [],
                "relationships": [],
                "decision_rules": [
                    {
                        "condition": "both lights are cadent",
                        "outcome": "the Ascendant has the predomination",
                        "related_steps": [],
                    }
                ],
                "preconditions": [],
                "exceptions": [],
                "author_variants": [],
                "procedure_outputs": [],
            }
        ]

        merged = merge_concept_knowledge({"house system": [8]}, chunks)

        self.assertEqual(merged["house system"]["decision_rules"], [])

    def test_merge_concept_knowledge_does_not_fallback_procedural_rules_into_oikodespotes(self) -> None:
        chunks = [
            {
                "chunk_index": 8,
                "concepts": ["Predominator", "Oikodespotes"],
                "_normalized_concepts": ["predominator", "oikodespotes"],
                "definitions": [],
                "technical_rules": [],
                "procedures": [],
                "terminology": [],
                "examples": [],
                "relationships": [],
                "decision_rules": [
                    {
                        "condition": "both lights are cadent",
                        "outcome": "the Ascendant has the predomination",
                        "related_steps": [],
                    }
                ],
                "preconditions": [],
                "exceptions": [],
                "author_variants": [],
                "procedure_outputs": [],
            }
        ]

        merged = merge_concept_knowledge({"oikodespotes": [8]}, chunks)

        self.assertEqual(merged["oikodespotes"]["decision_rules"], [])

    def test_merge_concept_knowledge_projects_chunk_payload_per_concept(self) -> None:
        chunks = [
            {
                "chunk_index": 7,
                "_normalized_concepts": ["house system", "predominator", "angular house"],
                "_chunk_type": "glossary",
                "_decision": "extract",
                "definitions": [
                    "House system: A way of dividing houses.",
                    "Predominator: The source of life force.",
                    "Angular houses: The strongest houses.",
                ],
                "technical_rules": [
                    "Predominator depends on sect and angular houses.",
                    "Angular houses are strongest.",
                ],
                "procedures": [
                    "Determine the Predominator by assessing sect and angularity.",
                ],
                "terminology": ["Predominator", "Angular houses", "House system"],
                "examples": ["Angular houses include the 1st, 4th, 7th, and 10th."],
                "relationships": [
                    "Predominator selection depends on angular houses.",
                    "Different house systems assign planets differently.",
                ],
            }
        ]

        merged = merge_concept_knowledge(
            {"house system": [7], "predominator": [7], "angular house": [7]},
            chunks,
        )

        self.assertEqual(merged["house system"]["definitions"], ["House system: A way of dividing houses."])
        self.assertEqual(merged["house system"]["relationships"], ["Different house systems assign planets differently."])
        self.assertEqual(merged["predominator"]["definitions"], ["Predominator: The source of life force."])
        self.assertEqual(
            merged["predominator"]["technical_rules"],
            ["Predominator depends on sect and angular houses."],
        )
        self.assertEqual(merged["angular house"]["definitions"], ["Angular houses: The strongest houses."])
        self.assertEqual(merged["angular house"]["examples"], ["Angular houses include the 1st, 4th, 7th, and 10th."])
        self.assertNotIn("Predominator: The source of life force.", merged["house system"]["definitions"])

    def test_merge_concept_knowledge_preserves_minimal_structural_parent_payload_for_closed_family(self) -> None:
        chunks = [
            {
                "chunk_index": 34,
                "concepts": ["Angularity and favorability of house", "Good houses", "Bad houses or places"],
                "_normalized_concepts": [
                    "angularity and favorability of house",
                    "good houses",
                    "bad houses or places",
                ],
                "_chunk_type": "",
                "_decision": "extract",
                "definitions": [],
                "technical_rules": [],
                "procedures": [],
                "terminology": ["Good houses", "Bad houses or places"],
                "examples": [],
                "relationships": [],
            }
        ]

        merged = merge_concept_knowledge(
            {"angularity and favorability of house": [34], "good houses": [34], "bad houses or places": [34]},
            chunks,
        )

        self.assertEqual(
            merged["angularity and favorability of house"]["terminology"],
            ["Good houses", "Bad houses or places"],
        )
        self.assertEqual(merged["angularity and favorability of house"]["source_chunks"], [34])

    def test_export_and_full_consolidation_write_expected_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            chunks_path = base / "Ancient Astrology - Vol 2_knowledge_chunks.jsonl"
            audit_path = base / "Ancient Astrology - Vol 2_knowledge_audit.jsonl"
            _write_jsonl(
                chunks_path,
                [
                    {
                        "chunk_id": "chunk_6_100_200",
                        "concepts": ["Angular Houses", "Succedent houses"],
                        "definitions": ["Angular houses: strong houses."],
                        "technical_rules": ["Angular houses are strong."],
                        "procedures": ["Classify 1, 4, 7, and 10 as angular."],
                        "terminology": ["Kentron"],
                        "relationships": ["Angular houses are followed by succedent houses."],
                        "examples": ["Saturn in the 1st house."],
                        "ambiguities": [],
                    },
                    {
                        "chunk_id": "chunk_7_200_300",
                        "concepts": ["angular house", "Cadent houses"],
                        "definitions": ["Angular houses mark the cardinal points."],
                        "technical_rules": ["Cadent houses are weaker."],
                        "procedures": ["Classify 3, 6, 9, and 12 as cadent."],
                        "terminology": ["Cardo"],
                        "relationships": ["Cadent houses decline from angular houses."],
                        "examples": ["Moon in the 12th house."],
                        "ambiguities": [],
                    },
                    {
                        "chunk_id": "chunk_8_300_400",
                        "concepts": ["Angularity of house as source of dynamic cosmic energy and stable support"],
                        "definitions": ["Long narrative concept that should be filtered out."],
                        "technical_rules": [],
                        "procedures": [],
                        "terminology": [],
                        "relationships": [],
                        "examples": [],
                        "ambiguities": [],
                    },
                ],
            )
            _write_jsonl(
                audit_path,
                [
                    {"chunk_id": "chunk_6_100_200", "chunk_index": 7, "decision": "extract"},
                    {"chunk_id": "chunk_7_200_300", "chunk_index": 8, "decision": "extract"},
                    {"chunk_id": "chunk_8_300_400", "chunk_index": 9, "decision": "extract"},
                ],
            )

            output_path = consolidate_knowledge_chunks(str(chunks_path))
            exported = json.loads(Path(output_path).read_text(encoding="utf-8"))

            self.assertEqual(
                output_path,
                build_concepts_output_path(str(chunks_path)),
            )
            self.assertIn("angular houses", exported)
            self.assertEqual(exported["angular houses"]["source_chunks"], [7, 8])
            self.assertEqual(exported["succedent houses"]["source_chunks"], [7])
            self.assertEqual(exported["cadent houses"]["source_chunks"], [8])
            self.assertNotIn("angularity of house as source of dynamic cosmic energy and stable support", exported)

    def test_full_consolidation_applies_post_filter_canonicalization(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            chunks_path = base / "Ancient Astrology - Vol 2_knowledge_chunks.jsonl"
            audit_path = base / "Ancient Astrology - Vol 2_knowledge_audit.jsonl"
            _write_jsonl(
                chunks_path,
                [
                    {
                        "chunk_id": "chunk_0_0_50",
                        "concepts": ["relative angularity of house"],
                        "definitions": ["Relative angularity measures strength by proximity to angles."],
                        "technical_rules": [],
                        "procedures": [],
                        "terminology": [],
                        "relationships": [],
                        "examples": [],
                        "ambiguities": [],
                    },
                    {
                        "chunk_id": "chunk_1_50_100",
                        "concepts": ["angularity of house", "Angular Houses", "chreniatistiko house"],
                        "definitions": ["Angularity of house indicates operative strength."],
                        "technical_rules": ["Angular houses carry the most force."],
                        "procedures": [],
                        "terminology": ["Chreniatistiko"],
                        "relationships": [],
                        "examples": [],
                        "ambiguities": [],
                    },
                ],
            )
            _write_jsonl(
                audit_path,
                [
                    {"chunk_id": "chunk_0_0_50", "chunk_index": 1, "decision": "extract"},
                    {"chunk_id": "chunk_1_50_100", "chunk_index": 2, "decision": "extract"},
                ],
            )

            output_path = consolidate_knowledge_chunks(str(chunks_path))
            exported = json.loads(Path(output_path).read_text(encoding="utf-8"))

            self.assertIn("house angularity", exported)
            self.assertEqual(exported["house angularity"]["source_chunks"], [1, 2])
            self.assertIn("angular houses", exported)
            self.assertIn("chrematistikos", exported)
            self.assertNotIn("relative angularity of house", exported)
            self.assertNotIn("chreniatistiko house", exported)

    def test_export_concepts_writes_json_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "concepts.json"
            export_concepts({"angular house": {"concept": "angular house", "source_chunks": [7]}}, str(output_path))
            written = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(written["angular house"]["concept"], "angular house")

    def test_build_taxonomy_output_path_uses_stable_naming(self) -> None:
        self.assertTrue(
            _build_taxonomy_output_path("outputs/Book_knowledge_chunks.jsonl").endswith(
                "Book_knowledge_taxonomy.json"
            )
        )

    def test_taxonomy_audit_payload_is_minimal_and_uses_canonical_builder(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            chunks_path = base / "Ancient Astrology - Vol 2_knowledge_chunks.jsonl"
            audit_path = base / "Ancient Astrology - Vol 2_knowledge_audit.jsonl"
            _write_jsonl(
                chunks_path,
                [
                    {
                        "chunk_id": "chunk_7_0_100",
                        "concepts": ["Angularity of house"],
                        "definitions": [
                            "Angular houses: the strongest houses.",
                            "Succedent houses: houses following angular houses.",
                            "Cadent houses: houses declining from angular houses.",
                        ],
                        "technical_rules": [],
                        "procedures": [],
                        "terminology": [],
                        "relationships": [],
                        "examples": [],
                        "ambiguities": [],
                    }
                ],
            )
            _write_jsonl(
                audit_path,
                [{"chunk_id": "chunk_7_0_100", "chunk_index": 8, "decision": "extract"}],
            )

            canonical = _build_canonical_concepts(str(chunks_path))
            audit_payload = _build_taxonomy_audit_payload(str(chunks_path))

            self.assertEqual(set(audit_payload), {"links"})
            self.assertIn("house angularity", canonical)
            self.assertEqual(
                [(link["parent"], link["child"]) for link in audit_payload["links"]],
                [
                    ("house angularity", "angular houses"),
                    ("house angularity", "cadent houses"),
                    ("house angularity", "succedent houses"),
                ],
            )

    def test_canonical_builder_preserves_closed_structural_parent_for_taxonomy_pattern(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            chunks_path = base / "Ancient Astrology - Vol 2_knowledge_chunks.jsonl"
            audit_path = base / "Ancient Astrology - Vol 2_knowledge_audit.jsonl"
            _write_jsonl(
                chunks_path,
                [
                    {
                        "chunk_id": "chunk_33_0_100",
                        "concepts": ["Angularity and favorability of house", "Good houses", "Bad houses or places"],
                        "definitions": [],
                        "technical_rules": [],
                        "procedures": [],
                        "terminology": ["Good houses", "Bad houses or places"],
                        "relationships": [],
                        "examples": [],
                        "ambiguities": [],
                    }
                ],
            )
            _write_jsonl(
                audit_path,
                [{"chunk_id": "chunk_33_0_100", "chunk_index": 34, "decision": "extract"}],
            )

            canonical = _build_canonical_concepts(str(chunks_path))
            audit_payload = _build_taxonomy_audit_payload(str(chunks_path))

            self.assertIn("favorability of house", canonical)
            self.assertEqual(
                canonical["favorability of house"]["terminology"],
                ["Benefic houses", "Malefic houses"],
            )
            self.assertEqual(
                [(link["parent"], link["child"]) for link in audit_payload["links"]],
                [
                    ("favorability of house", "benefic houses"),
                    ("favorability of house", "malefic houses"),
                ],
            )

    def test_export_taxonomy_audit_writes_minimal_json_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "Book_knowledge_taxonomy.json"
            payload = {
                "links": [
                    {
                        "parent": "angularity of house",
                        "child": "angular houses",
                        "signals": ["definition_head"],
                        "evidence": ["Angular houses: the strongest houses."],
                        "source_chunks": [7],
                    }
                ]
            }

            _export_taxonomy_audit(payload, str(output_path))
            written = json.loads(output_path.read_text(encoding="utf-8"))

            self.assertEqual(written, payload)

    def test_taxonomy_comparison_payload_shows_when_inference_already_covers_legacy_case(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            chunks_path = base / "Ancient Astrology - Vol 2_knowledge_chunks.jsonl"
            audit_path = base / "Ancient Astrology - Vol 2_knowledge_audit.jsonl"
            _write_jsonl(
                chunks_path,
                [
                    {
                        "chunk_id": "chunk_7_0_100",
                        "concepts": ["Angularity of house"],
                        "definitions": [
                            "Angular houses: the strongest houses.",
                            "Succedent houses: houses following angular houses.",
                            "Cadent houses: houses declining from angular houses.",
                        ],
                        "technical_rules": [],
                        "procedures": [],
                        "terminology": [],
                        "relationships": [],
                        "examples": [],
                        "ambiguities": [],
                    }
                ],
            )
            _write_jsonl(
                audit_path,
                [{"chunk_id": "chunk_7_0_100", "chunk_index": 8, "decision": "extract"}],
            )

            comparison = _build_taxonomy_comparison_payload(str(chunks_path))

            self.assertEqual(
                comparison["inferred_only_edges"],
                comparison["inferred_plus_legacy_edges"],
            )
            self.assertEqual(comparison["legacy_only_edges"], [])

    def test_taxonomy_comparison_payload_isolates_legacy_only_edges(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            chunks_path = base / "Ancient Astrology - Vol 2_knowledge_chunks.jsonl"
            audit_path = base / "Ancient Astrology - Vol 2_knowledge_audit.jsonl"
            _write_jsonl(
                chunks_path,
                [
                    {
                        "chunk_id": "chunk_5_0_100",
                        "concepts": ["Angular Houses", "Succedent houses", "Cadent houses"],
                        "definitions": [],
                        "technical_rules": ["Angular houses are strong."],
                        "procedures": [],
                        "terminology": [],
                        "relationships": [],
                        "examples": [],
                        "ambiguities": [],
                    }
                ],
            )
            _write_jsonl(
                audit_path,
                [{"chunk_id": "chunk_5_0_100", "chunk_index": 6, "decision": "extract"}],
            )

            comparison = _build_taxonomy_comparison_payload(str(chunks_path))

            self.assertEqual(comparison["links"], [])
            self.assertEqual(comparison["inferred_only_edges"], [])
            self.assertEqual(
                comparison["legacy_only_edges"],
                [
                    {"parent": "house angularity", "child": "angular houses"},
                    {"parent": "house angularity", "child": "succedent houses"},
                    {"parent": "house angularity", "child": "cadent houses"},
                ],
            )

    def test_build_knowledge_ontology_writes_new_artifact_without_changing_concepts_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            chunks_path = base / "Ancient Astrology - Vol 2_knowledge_chunks.jsonl"
            audit_path = base / "Ancient Astrology - Vol 2_knowledge_audit.jsonl"
            _write_jsonl(
                chunks_path,
                [
                    {
                        "chunk_id": "chunk_5_0_100",
                        "concepts": ["Whole sign house system", "Angular Houses", "chreniatistiko house"],
                        "definitions": ["Whole sign houses align signs with houses."],
                        "technical_rules": ["Angular houses are strong."],
                        "procedures": ["Assign one sign per house."],
                        "terminology": ["Whole-sign houses"],
                        "relationships": ["Angular houses are followed by succedent houses."],
                        "examples": [],
                        "ambiguities": [],
                    },
                    {
                        "chunk_id": "chunk_6_100_200",
                        "concepts": ["whole sign houses", "Succedent houses", "Cadent houses"],
                        "definitions": ["Succedent houses have moderate strength."],
                        "technical_rules": ["Cadent houses are weaker."],
                        "procedures": ["Classify 2, 5, 8, and 11 as succedent."],
                        "terminology": ["Cadent houses"],
                        "relationships": [],
                        "examples": [],
                        "ambiguities": [],
                    },
                ],
            )
            _write_jsonl(
                audit_path,
                [
                    {"chunk_id": "chunk_5_0_100", "chunk_index": 6, "decision": "extract"},
                    {"chunk_id": "chunk_6_100_200", "chunk_index": 7, "decision": "extract"},
                ],
            )

            concepts_output_path = consolidate_knowledge_chunks(str(chunks_path))
            ontology_output_path = build_knowledge_ontology(str(chunks_path))
            concepts_exported = json.loads(Path(concepts_output_path).read_text(encoding="utf-8"))
            ontology_exported = json.loads(Path(ontology_output_path).read_text(encoding="utf-8"))

            self.assertTrue(concepts_output_path.endswith("_knowledge_concepts.json"))
            self.assertTrue(ontology_output_path.endswith("_knowledge_ontology.json"))
            self.assertIn("angular houses", concepts_exported)
            self.assertIn("whole sign house system", concepts_exported)
            self.assertIn("house angularity", ontology_exported)
            self.assertEqual(
                ontology_exported["house angularity"]["child_concepts"],
                ["angular houses", "succedent houses", "cadent houses"],
            )
            self.assertEqual(
                ontology_exported["angular houses"]["parent_concepts"],
                ["house angularity", "house classification"],
            )
            self.assertIn("chrematistikos", ontology_exported)
            self.assertEqual(ontology_exported["chrematistikos"]["related_concepts"], ["house angularity"])
            self.assertIn("whole sign house system", ontology_exported)
            self.assertEqual(ontology_exported["whole sign house system"]["aliases"], [])

    def test_consolidation_does_not_dump_mixed_procedural_chunk_into_predominator(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            chunks_path = base / "Ancient Astrology - Vol 2_knowledge_chunks.jsonl"
            audit_path = base / "Ancient Astrology - Vol 2_knowledge_audit.jsonl"
            _write_jsonl(
                chunks_path,
                [
                    {
                        "chunk_id": "chunk_87_0_100",
                        "concepts": ["Predominator", "Profection", "Primary direction", "Progression"],
                        "definitions": [
                            "Profections: A symbolic timing procedure in which each sign is individually activated, in zodiacal order, at a fixed rate.",
                            "Primary direction: A timing technique based on motion by right ascension.",
                            "Progression: A derived motion used for timing.",
                        ],
                        "technical_rules": [
                            "In profections, the time lord governs the life for the duration of the profection.",
                        ],
                        "procedures": [],
                        "terminology": ["Annual lord", "Time lord"],
                        "relationships": [],
                        "examples": [],
                        "ambiguities": [],
                        "procedure_steps": [
                            {"id": "step-1", "order": 1, "text": "Activate each zodiac sign individually in zodiacal order at a fixed rate"},
                            {"id": "step-2", "order": 2, "text": "Identify the house matters occupied by the profected sign"},
                            {"id": "step-3", "order": 3, "text": "Determine the planet ruling the profected sign (the time lord)"},
                        ],
                        "decision_rules": [
                            {
                                "condition": "In primary directions, when a planet or point encounters another planet, exact aspect, or angle by right ascension",
                                "outcome": "This signifies an event or timing point in the native's life",
                                "related_steps": [],
                            }
                        ],
                        "preconditions": [],
                        "exceptions": [],
                        "author_variants": [
                            {
                                "author": "Valens",
                                "kind": "usage",
                                "text": "Described tertiary progressions as a timing technique for nativities but did not give it a specific name",
                                "related_steps": [],
                                "operation": "annotate",
                            }
                        ],
                        "procedure_outputs": [
                            {"text": "Identification of the time lord who governs the native's life during the profection period"},
                            {"text": "Comparison of progressed planetary positions to natal positions to indicate timing of events"},
                        ],
                    }
                ],
            )
            _write_jsonl(
                audit_path,
                [{"chunk_id": "chunk_87_0_100", "chunk_index": 88, "decision": "extract"}],
            )

            exported = _build_canonical_concepts(str(chunks_path))

            self.assertEqual(exported["predominator"]["shared_procedure"], [])
            self.assertEqual(exported["predominator"]["procedure_outputs"], [])
            self.assertGreaterEqual(len(exported["profection"]["shared_procedure"]), 3)
            self.assertEqual(len(exported["primary direction"]["decision_rules"]), 1)
            self.assertEqual(len(exported["progression"]["author_variant_overrides"]), 1)

    def test_build_knowledge_families_writes_family_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            chunks_path = base / "Ancient Astrology - Vol 1_knowledge_chunks.jsonl"
            audit_path = base / "Ancient Astrology - Vol 1_knowledge_audit.jsonl"
            _write_jsonl(
                chunks_path,
                [
                    {
                        "chunk_id": "chunk_5_0_100",
                        "concepts": ["Void in course moon"],
                        "definitions": ["Void in course moon: the moon does not perfect an aspect before leaving its sign."],
                        "technical_rules": [],
                        "procedures": [],
                        "terminology": ["lunar application"],
                        "relationships": [],
                        "examples": [],
                        "ambiguities": [],
                    },
                    {
                        "chunk_id": "chunk_6_100_200",
                        "concepts": ["Celestial sympathy"],
                        "definitions": ["Celestial sympathy: affinity linking distant celestial causes and terrestrial effects."],
                        "technical_rules": [],
                        "procedures": [],
                        "terminology": [],
                        "relationships": [],
                        "examples": [],
                        "ambiguities": [],
                    }
                ],
            )
            _write_jsonl(
                audit_path,
                [
                    {"chunk_id": "chunk_5_0_100", "chunk_index": 6, "decision": "extract"},
                    {"chunk_id": "chunk_6_100_200", "chunk_index": 7, "decision": "extract"},
                ],
            )

            families_output_path = build_knowledge_families(str(chunks_path))
            families_exported = json.loads(Path(families_output_path).read_text(encoding="utf-8"))

            self.assertTrue(families_output_path.endswith("_knowledge_families.json"))
            family_ids = {family["family_id"] for family in families_exported["families"]}
            self.assertIn("lunar_motion", family_ids)
            lunar_motion = next(family for family in families_exported["families"] if family["family_id"] == "lunar_motion")
            self.assertIn("void in course moon", lunar_motion["members"])
            self.assertIn("celestial sympathy", families_exported["unassigned_concepts"])

    def test_build_knowledge_ontology_adds_family_nodes_even_without_taxonomy(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            chunks_path = base / "Ancient Astrology - Vol 1_knowledge_chunks.jsonl"
            audit_path = base / "Ancient Astrology - Vol 1_knowledge_audit.jsonl"
            _write_jsonl(
                chunks_path,
                [
                    {
                        "chunk_id": "chunk_5_0_100",
                        "concepts": ["Void in course moon"],
                        "definitions": ["Void in course moon: the moon does not perfect an aspect before leaving its sign."],
                        "technical_rules": [],
                        "procedures": [],
                        "terminology": ["lunar separation"],
                        "relationships": [],
                        "examples": [],
                        "ambiguities": [],
                    }
                ],
            )
            _write_jsonl(
                audit_path,
                [{"chunk_id": "chunk_5_0_100", "chunk_index": 6, "decision": "extract"}],
            )

            with patch("src.knowledge_consolidator.ONTOLOGY_ENABLE_INFERRED_TAXONOMY", False):
                ontology_output_path = build_knowledge_ontology(str(chunks_path))

            ontology_exported = json.loads(Path(ontology_output_path).read_text(encoding="utf-8"))
            families_exported = json.loads(
                Path(build_families_output_path(str(chunks_path))).read_text(encoding="utf-8")
            )

            self.assertEqual(families_exported["families"][0]["family_id"], "lunar_motion")
            self.assertIn("lunar motion", ontology_exported)
            self.assertEqual(ontology_exported["lunar motion"]["node_kind"], "family")
            self.assertEqual(ontology_exported["void in course moon"]["belongs_to_families"], ["lunar motion"])

    def test_build_knowledge_family_candidates_writes_validated_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            chunks_path = base / "Ancient Astrology - Vol 2_knowledge_chunks.jsonl"
            audit_path = base / "Ancient Astrology - Vol 2_knowledge_audit.jsonl"
            _write_jsonl(
                chunks_path,
                [
                    {
                        "chunk_id": "chunk_5_0_100",
                        "concepts": ["Electional chart", "Inception", "Hour marker", "Angle"],
                        "definitions": [
                            "Electional chart: Chart chosen for an action.",
                            "Inception: A chart for the start of an event.",
                            "Hour marker: The horoskopos or ascending degree.",
                            "Angle: A fundamental chart point.",
                        ],
                        "technical_rules": [],
                        "procedures": [],
                        "terminology": ["Electional chart", "Inception", "Hour marker", "Angle"],
                        "relationships": [],
                        "examples": [],
                        "ambiguities": [],
                    }
                ],
            )
            _write_jsonl(
                audit_path,
                [{"chunk_id": "chunk_5_0_100", "chunk_index": 6, "decision": "extract"}],
            )

            def _fake_llm(_: str) -> str:
                return json.dumps(
                    {
                        "candidate_families": [
                            {
                                "family_label": "event timing applications",
                                "members": ["electional chart", "inception", "hour marker"],
                                "rationale": "Techniques for timing or charting events.",
                            }
                        ],
                        "left_unclustered": ["angle"],
                    }
                )

            output_path = build_knowledge_family_candidates(str(chunks_path), llm_callable=_fake_llm)
            exported = json.loads(Path(output_path).read_text(encoding="utf-8"))

            self.assertTrue(output_path.endswith("_knowledge_family_candidates.json"))
            self.assertEqual(exported["summary"]["candidate_count_accepted"], 0)
            self.assertEqual(exported["candidate_families"], [])
            self.assertEqual(exported["left_unclustered"], [])

    def test_build_knowledge_ontology_exports_empty_family_candidates_when_discovery_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            chunks_path = base / "Ancient Astrology - Vol 2_knowledge_chunks.jsonl"
            audit_path = base / "Ancient Astrology - Vol 2_knowledge_audit.jsonl"
            _write_jsonl(
                chunks_path,
                [
                    {
                        "chunk_id": "chunk_5_0_100",
                        "concepts": ["Angle"],
                        "definitions": ["Angle: A fundamental chart point."],
                        "technical_rules": [],
                        "procedures": [],
                        "terminology": ["Angle"],
                        "relationships": [],
                        "examples": [],
                        "ambiguities": [],
                    }
                ],
            )
            _write_jsonl(
                audit_path,
                [{"chunk_id": "chunk_5_0_100", "chunk_index": 6, "decision": "extract"}],
            )

            ontology_output_path = build_knowledge_ontology(str(chunks_path))
            candidates_exported = json.loads(
                Path(build_family_candidates_output_path(str(chunks_path))).read_text(encoding="utf-8")
            )

            self.assertTrue(Path(ontology_output_path).exists())
            self.assertEqual(candidates_exported["candidate_families"], [])
            self.assertEqual(candidates_exported["left_unclustered"], [])

    def test_build_knowledge_ontology_can_reuse_existing_families_and_skip_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            chunks_path = base / "Ancient Astrology - Vol 2_knowledge_chunks.jsonl"
            audit_path = base / "Ancient Astrology - Vol 2_knowledge_audit.jsonl"
            families_path = Path(build_families_output_path(str(chunks_path)))
            candidates_path = Path(build_family_candidates_output_path(str(chunks_path)))
            _write_jsonl(
                chunks_path,
                [
                    {
                        "chunk_id": "chunk_5_0_100",
                        "concepts": ["Void in course moon"],
                        "definitions": ["Void in course moon: the moon does not perfect an aspect before leaving its sign."],
                        "technical_rules": [],
                        "procedures": [],
                        "terminology": ["lunar separation"],
                        "relationships": [],
                        "examples": [],
                        "ambiguities": [],
                    }
                ],
            )
            _write_jsonl(
                audit_path,
                [{"chunk_id": "chunk_5_0_100", "chunk_index": 6, "decision": "extract"}],
            )
            families_path.write_text(
                json.dumps(
                    {
                        "families": [
                            {
                                "family_id": "lunar_motion",
                                "label": "lunar motion",
                                "members": ["void in course moon"],
                            }
                        ],
                        "concept_assignments": [
                            {
                                "concept": "void in course moon",
                                "families": [{"family_id": "lunar_motion", "source": "fixture", "confidence": 1.0}],
                            }
                        ],
                        "unassigned_concepts": [],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            candidates_path.write_text('{"sentinel": true}', encoding="utf-8")

            with patch("src.knowledge_consolidator._build_family_candidates_payload") as candidates_mock:
                ontology_output_path = build_knowledge_ontology(
                    str(chunks_path),
                    reuse_existing_families=True,
                    skip_family_candidates=True,
                )

            ontology_exported = json.loads(Path(ontology_output_path).read_text(encoding="utf-8"))
            candidates_exported = json.loads(candidates_path.read_text(encoding="utf-8"))

            candidates_mock.assert_not_called()
            self.assertTrue(Path(ontology_output_path).exists())
            self.assertEqual(ontology_exported["void in course moon"]["family_id"], ["lunar_motion"])
            self.assertEqual(ontology_exported["void in course moon"]["belongs_to_families"], ["lunar motion"])
            self.assertEqual(candidates_exported, {"sentinel": True})

    def test_build_knowledge_ontology_keeps_legacy_behavior_when_inferred_taxonomy_flag_is_off(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            chunks_path = base / "Ancient Astrology - Vol 2_knowledge_chunks.jsonl"
            audit_path = base / "Ancient Astrology - Vol 2_knowledge_audit.jsonl"
            _write_jsonl(
                chunks_path,
                [
                    {
                        "chunk_id": "chunk_5_0_100",
                        "concepts": ["Angularity of house", "Angular Houses", "Succedent houses", "Cadent houses"],
                        "definitions": [
                            "Angular houses: strong houses.",
                            "Succedent houses: houses following angular houses.",
                            "Cadent houses: houses declining from angular houses.",
                        ],
                        "technical_rules": ["Angular houses are strong."],
                        "procedures": [],
                        "terminology": [],
                        "relationships": [],
                        "examples": [],
                        "ambiguities": [],
                    }
                ],
            )
            _write_jsonl(
                audit_path,
                [{"chunk_id": "chunk_5_0_100", "chunk_index": 6, "decision": "extract"}],
            )

            with patch("src.knowledge_consolidator.ONTOLOGY_ENABLE_INFERRED_TAXONOMY", False):
                ontology_output_path = build_knowledge_ontology(str(chunks_path))

            ontology_exported = json.loads(Path(ontology_output_path).read_text(encoding="utf-8"))
            self.assertIn("house angularity", ontology_exported)
            self.assertEqual(
                ontology_exported["house angularity"]["child_concepts"],
                ["angular houses", "succedent houses", "cadent houses"],
            )

    def test_build_knowledge_ontology_can_consume_inferred_taxonomy_without_changing_concepts_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            chunks_path = base / "Ancient Astrology - Vol 2_knowledge_chunks.jsonl"
            audit_path = base / "Ancient Astrology - Vol 2_knowledge_audit.jsonl"
            _write_jsonl(
                chunks_path,
                [
                    {
                        "chunk_id": "chunk_5_0_100",
                        "concepts": ["Angularity of house", "Angular Houses", "Succedent houses", "Cadent houses"],
                        "definitions": [
                            "Angular houses: strong houses.",
                            "Succedent houses: houses following angular houses.",
                            "Cadent houses: houses declining from angular houses.",
                        ],
                        "technical_rules": ["Angular houses are strong."],
                        "procedures": [],
                        "terminology": [],
                        "relationships": [],
                        "examples": [],
                        "ambiguities": [],
                    }
                ],
            )
            _write_jsonl(
                audit_path,
                [{"chunk_id": "chunk_5_0_100", "chunk_index": 6, "decision": "extract"}],
            )

            concepts_output_path = consolidate_knowledge_chunks(str(chunks_path))
            concepts_exported = json.loads(Path(concepts_output_path).read_text(encoding="utf-8"))

            with patch("src.knowledge_consolidator.ONTOLOGY_ENABLE_INFERRED_TAXONOMY", True):
                ontology_output_path = build_knowledge_ontology(str(chunks_path))

            ontology_exported = json.loads(Path(ontology_output_path).read_text(encoding="utf-8"))

            self.assertIn("house angularity", concepts_exported)
            self.assertIn("house angularity", ontology_exported)
            self.assertEqual(
                ontology_exported["house angularity"]["child_concepts"],
                ["angular houses", "succedent houses", "cadent houses"],
            )
            self.assertEqual(ontology_exported["house angularity"]["aliases"], [])

    def test_consolidation_promotes_taxonomy_subconcepts_into_independent_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            chunks_path = base / "Ancient Astrology - Vol 2_knowledge_chunks.jsonl"
            audit_path = base / "Ancient Astrology - Vol 2_knowledge_audit.jsonl"
            _write_jsonl(
                chunks_path,
                [
                    {
                        "chunk_id": "chunk_7_0_100",
                        "concepts": ["Angularity of houses as source of dynamic cosmic energy and stable support"],
                        "definitions": [
                            "Succedent houses: houses following angular houses with moderate energy.",
                            "Cadent houses: houses following succedent houses and declining from power.",
                        ],
                        "technical_rules": [
                            "The Greek epanaphora means to rise toward the angular house.",
                            "The Greek apoklino means to slope down from the angular house.",
                        ],
                        "procedures": [],
                        "terminology": ["Epanaphora", "Apoklino"],
                        "relationships": [],
                        "examples": [],
                        "ambiguities": [],
                    },
                    {
                        "chunk_id": "chunk_8_100_200",
                        "concepts": ["Relative favorability of houses"],
                        "definitions": ["Benefic houses: houses favorable to the life of the individual."],
                        "technical_rules": [],
                        "procedures": [],
                        "terminology": [],
                        "relationships": [
                            "Benefic houses include angular, 11th, 9th, and 5th; malefic houses include 2nd, 6th, 8th, and 12th."
                        ],
                        "examples": [],
                        "ambiguities": [],
                    },
                ],
            )
            _write_jsonl(
                audit_path,
                [
                    {"chunk_id": "chunk_7_0_100", "chunk_index": 8, "decision": "extract"},
                    {"chunk_id": "chunk_8_100_200", "chunk_index": 9, "decision": "extract"},
                ],
            )

            output_path = consolidate_knowledge_chunks(str(chunks_path))
            exported = json.loads(Path(output_path).read_text(encoding="utf-8"))

            self.assertIn("succedent houses", exported)
            self.assertIn("cadent houses", exported)
            self.assertIn("epanaphora", exported)
            self.assertIn("apoklino", exported)
            self.assertIn("benefic houses", exported)
            self.assertIn("malefic houses", exported)
            self.assertIn("favorability of house", exported)
            self.assertEqual(exported["epanaphora"]["terminology"], ["Epanaphora"])
            self.assertEqual(exported["apoklino"]["terminology"], ["Apoklino"])
            self.assertEqual(
                exported["malefic houses"]["relationships"],
                [
                    "Benefic houses include angular, 11th, 9th, and 5th; malefic houses include 2nd, 6th, 8th, and 12th."
                ],
            )

    def test_consolidation_preserves_structural_parent_house_angularity(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            chunks_path = base / "Ancient Astrology - Vol 2_knowledge_chunks.jsonl"
            audit_path = base / "Ancient Astrology - Vol 2_knowledge_audit.jsonl"
            _write_jsonl(
                chunks_path,
                [
                    {
                        "chunk_id": "chunk_50_0_100",
                        "concepts": ["Planetary condition"],
                        "definitions": [
                            "House Angularity: angular houses (1,4,7,10) offer dynamic strength and stability to residing planets.",
                            "Angular houses: the strongest houses.",
                            "Cadent houses: the weakest houses.",
                        ],
                        "technical_rules": [
                            "Angular houses, succedent houses, and cadent houses form a strength hierarchy."
                        ],
                        "procedures": [],
                        "terminology": ["Succedent Houses"],
                        "relationships": [],
                        "examples": [],
                        "ambiguities": [],
                    }
                ],
            )
            _write_jsonl(
                audit_path,
                [{"chunk_id": "chunk_50_0_100", "chunk_index": 51, "decision": "extract"}],
            )

            output_path = consolidate_knowledge_chunks(str(chunks_path))
            exported = json.loads(Path(output_path).read_text(encoding="utf-8"))

            self.assertIn("house angularity", exported)
            self.assertEqual(exported["house angularity"]["source_chunks"], [51])
            self.assertIn("angular houses", exported)
            self.assertIn("succedent houses", exported)
            self.assertIn("cadent houses", exported)


if __name__ == "__main__":
    unittest.main()
