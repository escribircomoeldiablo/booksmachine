from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.knowledge_consolidator import (
    build_concept_index,
    build_concepts_output_path,
    consolidate_knowledge_chunks,
    export_concepts,
    load_chunk_knowledge,
    merge_concept_knowledge,
    normalize_concepts,
)


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


class KnowledgeConsolidatorTests(unittest.TestCase):
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
            self.assertIn("angular house", exported)
            self.assertEqual(exported["angular house"]["source_chunks"], [7, 8])
            self.assertEqual(exported["succedent house"]["source_chunks"], [7])
            self.assertEqual(exported["cadent house"]["source_chunks"], [8])
            self.assertNotIn("angularity of house as source of dynamic cosmic energy and stable support", exported)

    def test_export_concepts_writes_json_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "concepts.json"
            export_concepts({"angular house": {"concept": "angular house", "source_chunks": [7]}}, str(output_path))
            written = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(written["angular house"]["concept"], "angular house")


if __name__ == "__main__":
    unittest.main()
