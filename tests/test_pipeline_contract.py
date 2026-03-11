from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.pipeline import process_book


class PipelineContractTests(unittest.TestCase):
    def test_output_artifacts_are_generated_with_stable_naming(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.pipeline.OUTPUT_FOLDER", tmpdir):
                with patch("src.pipeline.STRUCTURE_PASS_ENABLED", False):
                    with patch("src.pipeline.load_book", return_value="source text"):
                        with patch("src.front_matter_extractor.ask_llm", return_value="{}"):
                            with patch("src.pipeline.split_into_chunks", return_value=["c1", "c2"]):
                                with patch(
                                    "src.pipeline.summarize_chunk",
                                    side_effect=lambda chunk: f"summary::{chunk}",
                                ):
                                    with patch(
                                        "src.pipeline.synthesize_blocks",
                                        return_value=(
                                            [
                                                {
                                                    "block_index": 1,
                                                    "chunk_start": 1,
                                                    "chunk_end": 2,
                                                    "chunk_indices": [1, 2],
                                                    "summary_text": "block::1-2",
                                                }
                                            ],
                                            1,
                                        ),
                                    ):
                                        with patch(
                                            "src.pipeline.synthesize_compendium",
                                            return_value=("compendium::global", 0),
                                        ):
                                            output_path = process_book("books/sample_book.txt")

            expected_compendium_path = Path(tmpdir) / "sample_book_summary.txt"
            expected_chunk_path = Path(tmpdir) / "sample_book_summary_chunks.txt"
            expected_block_path = Path(tmpdir) / "sample_book_summary_blocks.txt"
            expected_front_matter_path = Path(tmpdir) / "sample_book_front_matter_outline.json"
            expected_chunk_text = (
                "## Chunk 1\nsummary::c1\n\n---\n\n## Chunk 2\nsummary::c2"
            )
            expected_block_text = "## Block 1 (Chunks 1-2)\nblock::1-2"

            self.assertEqual(output_path, str(expected_compendium_path))
            self.assertTrue(expected_compendium_path.exists())
            self.assertTrue(expected_chunk_path.exists())
            self.assertTrue(expected_block_path.exists())
            self.assertFalse(expected_front_matter_path.exists())
            self.assertEqual(
                expected_compendium_path.read_text(encoding="utf-8"),
                "compendium::global",
            )
            self.assertEqual(expected_chunk_path.read_text(encoding="utf-8"), expected_chunk_text)
            self.assertEqual(expected_block_path.read_text(encoding="utf-8"), expected_block_text)

    def test_empty_chunk_summary_raises_runtime_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.pipeline.OUTPUT_FOLDER", tmpdir):
                with patch("src.pipeline.STRUCTURE_PASS_ENABLED", False):
                    with patch("src.pipeline.load_book", return_value="source text"):
                        with patch("src.front_matter_extractor.ask_llm", return_value="{}"):
                            with patch("src.pipeline.split_into_chunks", return_value=["c1"]):
                                with patch("src.pipeline.summarize_chunk", return_value="   "):
                                    with self.assertRaisesRegex(
                                        RuntimeError,
                                        r"^Chunk summary is empty for chunk 1\.$",
                                    ):
                                        process_book("books/sample_book.txt")

    def test_empty_chunks_raises_same_error_shape(self) -> None:
        with patch("src.pipeline.STRUCTURE_PASS_ENABLED", False):
            with patch("src.pipeline.load_book", return_value="source text"):
                with patch("src.front_matter_extractor.ask_llm", return_value="{}"):
                    with patch("src.pipeline.split_into_chunks", return_value=[]):
                        with self.assertRaisesRegex(
                            ValueError,
                            r"^No readable content found in: books/sample_book\.txt$",
                        ):
                            process_book("books/sample_book.txt")


if __name__ == "__main__":
    unittest.main()
