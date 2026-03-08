from __future__ import annotations

import unittest
from unittest.mock import patch

from src.synthesizer import (
    build_block_prompt,
    build_compendium_prompt,
    expected_synthesis_calls,
    group_chunk_summary_records,
    make_chunk_summary_records,
    synthesize_blocks,
    synthesize_compendium,
)


class SynthesizerTests(unittest.TestCase):
    def test_group_chunk_summary_records_sizes(self) -> None:
        records_1 = make_chunk_summary_records(["s1"])
        records_8 = make_chunk_summary_records([f"s{i}" for i in range(1, 9)])
        records_9 = make_chunk_summary_records([f"s{i}" for i in range(1, 10)])
        records_16 = make_chunk_summary_records([f"s{i}" for i in range(1, 17)])

        self.assertEqual(len(group_chunk_summary_records(records_1)), 1)
        self.assertEqual(len(group_chunk_summary_records(records_8)), 1)
        self.assertEqual(len(group_chunk_summary_records(records_9)), 2)
        self.assertEqual(len(group_chunk_summary_records(records_16)), 2)

    def test_block_traceability_metadata_is_consistent(self) -> None:
        chunk_records = make_chunk_summary_records([f"s{i}" for i in range(1, 10)])

        with patch("src.synthesizer.ask_llm", side_effect=["b1", "b2"]):
            block_records, llm_calls = synthesize_blocks(chunk_records)

        self.assertEqual(llm_calls, 2)
        self.assertEqual(len(block_records), 2)
        self.assertEqual(block_records[0]["chunk_start"], 1)
        self.assertEqual(block_records[0]["chunk_end"], 8)
        self.assertEqual(block_records[0]["chunk_indices"], [1, 2, 3, 4, 5, 6, 7, 8])
        self.assertEqual(block_records[1]["chunk_start"], 9)
        self.assertEqual(block_records[1]["chunk_end"], 9)
        self.assertEqual(block_records[1]["chunk_indices"], [9])

    def test_prompts_include_only_summaries_and_metadata(self) -> None:
        chunk_records = make_chunk_summary_records(["summary a", "summary b"])
        block_prompt = build_block_prompt(1, chunk_records)
        self.assertIn("Chunk 1", block_prompt)
        self.assertIn("summary a", block_prompt)
        self.assertNotIn("Text chunk:", block_prompt)

        block_records = [
            {
                "block_index": 1,
                "chunk_start": 1,
                "chunk_end": 2,
                "chunk_indices": [1, 2],
                "summary_text": "block summary",
            }
        ]
        compendium_prompt = build_compendium_prompt(block_records)
        self.assertIn("Block 1 (Chunks 1-2)", compendium_prompt)
        self.assertIn("block summary", compendium_prompt)
        self.assertNotIn("Text chunk:", compendium_prompt)

    def test_single_block_compendium_avoids_second_llm_call(self) -> None:
        block_records = [
            {
                "block_index": 1,
                "chunk_start": 1,
                "chunk_end": 3,
                "chunk_indices": [1, 2, 3],
                "summary_text": "single block summary",
            }
        ]

        with patch("src.synthesizer.ask_llm") as ask_mock:
            compendium, llm_calls = synthesize_compendium(block_records)

        ask_mock.assert_not_called()
        self.assertEqual(compendium, "single block summary")
        self.assertEqual(llm_calls, 0)

    def test_expected_synthesis_calls_formula(self) -> None:
        self.assertEqual(expected_synthesis_calls(0), 0)
        self.assertEqual(expected_synthesis_calls(1), 1)
        self.assertEqual(expected_synthesis_calls(8), 1)
        self.assertEqual(expected_synthesis_calls(9), 3)
        self.assertEqual(expected_synthesis_calls(16), 3)

    def test_empty_chunk_summary_fails_fast(self) -> None:
        with self.assertRaisesRegex(
            RuntimeError,
            r"^Chunk summary is empty for chunk 1\.$",
        ):
            make_chunk_summary_records(["  "])


if __name__ == "__main__":
    unittest.main()
