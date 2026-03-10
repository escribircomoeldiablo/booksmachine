from __future__ import annotations

import unittest
from unittest.mock import patch

from src.knowledge_extractor import (
    build_chunk_knowledge_prompt,
    chunk_knowledge_to_summary_text,
    extract_chunk_knowledge,
)
from src.knowledge_schema import SectionRef


class KnowledgeExtractorTests(unittest.TestCase):
    def test_prompt_defaults_to_original_language_for_knowledge(self) -> None:
        prompt = build_chunk_knowledge_prompt(
            chunk_text="English source text",
            chunk_id="chunk_1",
            source_fingerprint="book_hash",
            section_refs=[],
        )

        self.assertIn("idioma original del fragmento", prompt)

    def test_prompt_can_target_spanish_knowledge_output(self) -> None:
        prompt = build_chunk_knowledge_prompt(
            chunk_text="English source text",
            chunk_id="chunk_1",
            source_fingerprint="book_hash",
            section_refs=[],
            knowledge_language="es",
        )

        self.assertIn("campos textuales en espanol tecnico claro", prompt)

    def test_valid_llm_payload_produces_valid_record(self) -> None:
        payload = (
            '{"schema_version":"1.0.0","chunk_id":"chunk_1","source_fingerprint":"book_hash",'
            '"section_refs":[{"label":"Intro","type":"chapter","start_char":0,"end_char":100}],'
            '"concepts":["Casas"],"definitions":["Casa: sector tematico"],'
            '"technical_rules":["Regla"],"procedures":["Paso"],"terminology":["horoskopos"],'
            '"relationships":[],"examples":[],"ambiguities":[]}'
        )
        with patch("src.knowledge_extractor.ask_llm", return_value=payload):
            result = extract_chunk_knowledge(
                chunk_text="text",
                chunk_id="chunk_1",
                source_fingerprint="book_hash",
                section_refs=[SectionRef(label="Intro", type="chapter", start_char=0, end_char=100)],
            )

        self.assertFalse(result.used_fallback)
        self.assertIsNone(result.parse_error)
        self.assertEqual(result.record.chunk_id, "chunk_1")
        self.assertEqual(result.record.concepts, ["Casas"])

    def test_invalid_payload_triggers_controlled_fallback(self) -> None:
        with patch("src.knowledge_extractor.ask_llm", return_value="invalid-json"):
            result = extract_chunk_knowledge(
                chunk_text="text",
                chunk_id="chunk_9",
                source_fingerprint="book_hash",
                section_refs=[],
            )

        self.assertTrue(result.used_fallback)
        self.assertIsNotNone(result.parse_error)
        self.assertEqual(result.record.chunk_id, "chunk_9")
        self.assertEqual(result.record.technical_rules, [])

    def test_renderer_is_structured_and_not_json_dump(self) -> None:
        payload = (
            '{"schema_version":"1.0.0","chunk_id":"chunk_1","source_fingerprint":"book_hash",'
            '"section_refs":[],"concepts":["C1"],"definitions":["D1"],"technical_rules":["R1"],'
            '"procedures":["P1"],"terminology":["T1"],"relationships":[],"examples":[],"ambiguities":[]}'
        )
        with patch("src.knowledge_extractor.ask_llm", return_value=payload):
            result = extract_chunk_knowledge(
                chunk_text="text",
                chunk_id="chunk_1",
                source_fingerprint="book_hash",
            )

        rendered = chunk_knowledge_to_summary_text(result.record)
        self.assertIn("CONCEPTOS", rendered)
        self.assertIn("DEFINICIONES", rendered)
        self.assertIn("REGLAS", rendered)
        self.assertNotIn('"schema_version"', rendered)


if __name__ == "__main__":
    unittest.main()
