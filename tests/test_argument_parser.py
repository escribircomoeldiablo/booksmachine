from __future__ import annotations

import unittest

from src.argument_parser import parse_argument_chunk_json
from src.knowledge_schema import SectionRef


class ArgumentParserTests(unittest.TestCase):
    def test_parses_valid_payload(self) -> None:
        result = parse_argument_chunk_json(
            """
            {
              "schema_version": "1.0.0",
              "theses": ["The state shapes labor discipline."],
              "claims": ["Institutions mediate market coercion."],
              "evidence": ["The chapter cites factory inspection records."],
              "methods": ["comparative historical analysis"],
              "authors_or_schools": ["Marxism"],
              "key_terms": ["labor discipline"],
              "debates": ["Whether coercion or consent better explains compliance."],
              "limitations": ["The evidence is concentrated in urban archives."]
            }
            """,
            chunk_id="chunk-1",
            source_fingerprint="book",
            section_refs=[SectionRef(label="Intro", type="section", start_char=0, end_char=10)],
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.record.chunk_id, "chunk-1")
        self.assertEqual(result.record.theses, ["The state shapes labor discipline."])

    def test_invalid_json_falls_back(self) -> None:
        result = parse_argument_chunk_json(
            "not-json",
            chunk_id="chunk-1",
            source_fingerprint="book",
            section_refs=[],
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.error_kind, "parse_fallback")
        self.assertEqual(result.record.theses, [])

    def test_invalid_payload_shape_returns_invalid_payload(self) -> None:
        result = parse_argument_chunk_json(
            '{"theses":"bad"}',
            chunk_id="chunk-1",
            source_fingerprint="book",
            section_refs=[],
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.error_kind, "invalid_payload")


if __name__ == "__main__":
    unittest.main()
