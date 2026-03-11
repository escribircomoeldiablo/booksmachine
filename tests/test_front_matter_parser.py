from __future__ import annotations

import unittest

from src.front_matter_parser import parse_front_matter_outline_json
from src.front_matter_schema import FRONT_MATTER_OUTLINE_SCHEMA_VERSION, FrontMatterSource


class FrontMatterParserTests(unittest.TestCase):
    def test_parses_valid_payload(self) -> None:
        raw = """
        {
          "schema_version": "1.0.0",
          "book_title": "Should Be Ignored",
          "source": {
            "has_toc": true,
            "has_introduction": true,
            "has_preface": false,
            "strategy": "mixed"
          },
          "family_candidates": [
            {
              "name": "Natal Astrology",
              "aliases": ["Genethlialogy"],
              "evidence": ["Contents: Book I"],
              "confidence": 0.82,
              "status": "candidate"
            }
          ],
          "core_concepts_expected": [
            {
              "name": "houses",
              "evidence": ["Introduction mentions houses"],
              "priority": "high"
            }
          ],
          "provisional_taxonomy": [
            {
              "parent": "charts",
              "child": "natal charts",
              "relation_type": "subdomain_of",
              "confidence": 0.6
            }
          ],
          "normalization_hints": [
            {
              "canonical": "oikodespotes",
              "variants": ["oecodespot", "oikodespotes"]
            }
          ],
          "confidence_notes": ["front matter gives only a preliminary signal"]
        }
        """
        result = parse_front_matter_outline_json(
            raw,
            book_title="Fixed Title",
            source=FrontMatterSource(has_toc=True, has_introduction=True, has_preface=False, strategy="mixed"),
        )

        self.assertTrue(result.ok)
        self.assertIsNone(result.error)
        self.assertEqual(result.record.schema_version, FRONT_MATTER_OUTLINE_SCHEMA_VERSION)
        self.assertEqual(result.record.book_title, "Fixed Title")
        self.assertEqual(result.record.source.strategy, "mixed")
        self.assertEqual(result.record.family_candidates[0].name, "Natal Astrology")
        self.assertEqual(result.record.normalization_hints[0].variants, ["oecodespot", "oikodespotes"])

    def test_invalid_json_falls_back_to_valid_minimal_record(self) -> None:
        result = parse_front_matter_outline_json(
            "not-json",
            book_title="Book Title",
            source=FrontMatterSource(has_toc=False, has_introduction=False, has_preface=False, strategy="initial_excerpt"),
        )

        self.assertFalse(result.ok)
        self.assertIsNotNone(result.error)
        self.assertEqual(result.record.book_title, "Book Title")
        self.assertEqual(result.record.family_candidates, [])
        self.assertEqual(result.record.source.strategy, "initial_excerpt")
        self.assertTrue(any("parse_fallback" in note for note in result.record.confidence_notes))

    def test_invalid_hint_shape_is_rejected(self) -> None:
        raw = """
        {
          "schema_version": "1.0.0",
          "book_title": "Bad",
          "source": {
            "has_toc": false,
            "has_introduction": false,
            "has_preface": false,
            "strategy": "document_map"
          },
          "family_candidates": [],
          "core_concepts_expected": [],
          "provisional_taxonomy": [],
          "normalization_hints": [{"canonical": "sect", "variants": "sect doctrine"}],
          "confidence_notes": []
        }
        """
        result = parse_front_matter_outline_json(
            raw,
            book_title="Stable Title",
            source=FrontMatterSource(has_toc=False, has_introduction=False, has_preface=False, strategy="document_map"),
        )

        self.assertFalse(result.ok)
        self.assertIn("normalization_hints[0].variants", result.error or "")
        self.assertEqual(result.record.book_title, "Stable Title")

    def test_parses_fenced_json_with_wrapper_text(self) -> None:
        raw = """Preliminary note

        ```json
        {
          "schema_version": "1.0.0",
          "family_candidates": [],
          "core_concepts_expected": [],
          "provisional_taxonomy": [],
          "normalization_hints": [],
          "confidence_notes": ["wrapped"]
        }
        ```

        End note.
        """
        result = parse_front_matter_outline_json(
            raw,
            book_title="Wrapped Title",
            source=FrontMatterSource(has_toc=False, has_introduction=True, has_preface=False, strategy="mixed"),
        )

        self.assertTrue(result.ok)
        self.assertIsNone(result.error)
        self.assertEqual(result.record.book_title, "Wrapped Title")
        self.assertEqual(result.record.source.strategy, "mixed")
        self.assertEqual(result.record.confidence_notes, ["wrapped"])


if __name__ == "__main__":
    unittest.main()
