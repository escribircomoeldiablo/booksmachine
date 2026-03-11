from __future__ import annotations

import unittest
from unittest.mock import patch

from src.argument_extractor import build_argument_prompt, extract_argument_chunk
from src.knowledge_schema import SectionRef


class ArgumentExtractorTests(unittest.TestCase):
    def test_build_prompt_includes_language_and_refs(self) -> None:
        prompt = build_argument_prompt(
            chunk_text="Text",
            chunk_id="c1",
            source_fingerprint="book",
            section_refs_json='[{"label":"Intro"}]',
            knowledge_language="es",
        )
        self.assertIn("Chunk id: c1", prompt)
        self.assertIn("Section refs:", prompt)
        self.assertIn("espanol tecnico", prompt)

    def test_extract_marks_empty_response_as_not_present(self) -> None:
        with patch("src.argument_extractor.ask_llm", return_value="   "):
            result = extract_argument_chunk(
                chunk_text="Text",
                chunk_id="c1",
                source_fingerprint="book",
                section_refs=[SectionRef(label="L", type="section", start_char=0, end_char=1)],
            )
        self.assertTrue(result.used_fallback)
        self.assertFalse(result.llm_response_present)
        self.assertEqual(result.error_kind, "llm_empty")

    def test_extract_marks_invalid_text_response_as_present(self) -> None:
        with patch("src.argument_extractor.ask_llm", return_value="not-json"):
            result = extract_argument_chunk(
                chunk_text="Text",
                chunk_id="c1",
                source_fingerprint="book",
                section_refs=[],
            )
        self.assertTrue(result.used_fallback)
        self.assertTrue(result.llm_response_present)
        self.assertEqual(result.error_kind, "parse_fallback")


if __name__ == "__main__":
    unittest.main()
