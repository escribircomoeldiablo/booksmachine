from __future__ import annotations

import unittest

from src.knowledge_parser import parse_chunk_knowledge_json
from src.knowledge_schema import CHUNK_KNOWLEDGE_SCHEMA_VERSION, SectionRef


class KnowledgeParserTests(unittest.TestCase):
    def test_parses_valid_json_payload(self) -> None:
        raw = """
        {
          "schema_version": "1.0.0",
          "chunk_id": "chunk_1",
          "source_fingerprint": "book_hash",
          "section_refs": [],
          "concepts": ["Sect"],
          "definitions": ["domicilio: regencia"],
          "technical_rules": ["Regla A"],
          "procedures": ["Paso 1"],
          "terminology": ["oikodespotes"],
          "relationships": [],
          "examples": [],
          "ambiguities": []
        }
        """
        result = parse_chunk_knowledge_json(
            raw,
            chunk_id="fallback_chunk",
            source_fingerprint="fallback_fingerprint",
        )

        self.assertTrue(result.ok)
        self.assertIsNone(result.error)
        self.assertEqual(result.record.schema_version, CHUNK_KNOWLEDGE_SCHEMA_VERSION)
        self.assertEqual(result.record.chunk_id, "chunk_1")
        self.assertEqual(result.record.concepts, ["Sect"])

    def test_invalid_json_falls_back_with_error(self) -> None:
        result = parse_chunk_knowledge_json(
            "not-json",
            chunk_id="chunk_5",
            source_fingerprint="book_hash",
        )

        self.assertFalse(result.ok)
        self.assertIsNotNone(result.error)
        self.assertEqual(result.record.chunk_id, "chunk_5")
        self.assertEqual(result.record.concepts, [])

    def test_missing_arrays_are_filled_with_empty_arrays(self) -> None:
        raw = """
        {
          "schema_version": "1.0.0",
          "chunk_id": "chunk_2",
          "source_fingerprint": "book_hash",
          "section_refs": []
        }
        """
        result = parse_chunk_knowledge_json(
            raw,
            chunk_id="fallback_chunk",
            source_fingerprint="book_hash",
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.record.terminology, [])
        self.assertEqual(result.record.procedures, [])

    def test_null_array_is_rejected(self) -> None:
        raw = """
        {
          "schema_version": "1.0.0",
          "chunk_id": "chunk_2",
          "source_fingerprint": "book_hash",
          "section_refs": [],
          "concepts": null,
          "definitions": [],
          "technical_rules": [],
          "procedures": [],
          "terminology": [],
          "relationships": [],
          "examples": [],
          "ambiguities": []
        }
        """
        result = parse_chunk_knowledge_json(
            raw,
            chunk_id="chunk_2",
            source_fingerprint="book_hash",
            section_refs=[SectionRef(label="A", type="section", start_char=0, end_char=10)],
        )

        self.assertFalse(result.ok)
        self.assertIn("concepts", result.error or "")
        self.assertEqual(result.record.concepts, [])

    def test_definitions_object_is_bridged_to_string(self) -> None:
        raw = """
        {
          "schema_version": "1.0.0",
          "chunk_id": "chunk_3",
          "source_fingerprint": "book_hash",
          "section_refs": [],
          "concepts": [],
          "definitions": [{"term":"Domicilio","definition":"Planeta en su signo propio"}],
          "technical_rules": [],
          "procedures": [],
          "terminology": [],
          "relationships": [],
          "examples": [],
          "ambiguities": []
        }
        """
        result = parse_chunk_knowledge_json(
            raw,
            chunk_id="chunk_3",
            source_fingerprint="book_hash",
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.record.definitions, ["Domicilio: Planeta en su signo propio"])

    def test_definitions_invalid_object_still_rejected(self) -> None:
        raw = """
        {
          "schema_version": "1.0.0",
          "chunk_id": "chunk_4",
          "source_fingerprint": "book_hash",
          "section_refs": [],
          "concepts": [],
          "definitions": [{"foo":"bar"}],
          "technical_rules": [],
          "procedures": [],
          "terminology": [],
          "relationships": [],
          "examples": [],
          "ambiguities": []
        }
        """
        result = parse_chunk_knowledge_json(
            raw,
            chunk_id="chunk_4",
            source_fingerprint="book_hash",
        )

        self.assertFalse(result.ok)
        self.assertIn("definitions[0]", result.error or "")

    def test_examples_object_is_bridged_to_string(self) -> None:
        raw = """
        {
          "schema_version": "1.0.0",
          "chunk_id": "chunk_5",
          "source_fingerprint": "book_hash",
          "section_refs": [],
          "concepts": [],
          "definitions": [],
          "technical_rules": [],
          "procedures": [],
          "terminology": [],
          "relationships": [],
          "examples": [{"case":"Chart A","description":"Mars in 10th activates career topics"}],
          "ambiguities": []
        }
        """
        result = parse_chunk_knowledge_json(
            raw,
            chunk_id="chunk_5",
            source_fingerprint="book_hash",
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.record.examples, ["Chart A: Mars in 10th activates career topics"])

    def test_relationships_object_is_bridged_to_string(self) -> None:
        raw = """
        {
          "schema_version": "1.0.0",
          "chunk_id": "chunk_6",
          "source_fingerprint": "book_hash",
          "section_refs": [],
          "concepts": [],
          "definitions": [],
          "technical_rules": [],
          "procedures": [],
          "terminology": [],
          "relationships": [{"source":"Mars","target":"10th house","relation":"activates"}],
          "examples": [],
          "ambiguities": []
        }
        """
        result = parse_chunk_knowledge_json(
            raw,
            chunk_id="chunk_6",
            source_fingerprint="book_hash",
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.record.relationships, ["Mars -> 10th house (activates)"])


if __name__ == "__main__":
    unittest.main()
