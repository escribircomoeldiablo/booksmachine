from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.pipeline import process_book


class PipelineContractTests(unittest.TestCase):
    def test_output_path_naming_and_format_are_stable(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.pipeline.OUTPUT_FOLDER", tmpdir):
                with patch("src.pipeline.load_book", return_value="source text"):
                    with patch("src.pipeline.split_into_chunks", return_value=["c1", "c2"]):
                        with patch(
                            "src.pipeline.summarize_chunk",
                            side_effect=lambda chunk: f"summary::{chunk}",
                        ):
                            output_path = process_book("books/sample_book.txt")

            expected_path = Path(tmpdir) / "sample_book_summary.txt"
            expected_text = (
                "## Chunk 1\nsummary::c1\n\n---\n\n## Chunk 2\nsummary::c2"
            )

            self.assertEqual(output_path, str(expected_path))
            self.assertTrue(expected_path.exists())
            self.assertEqual(expected_path.read_text(encoding="utf-8"), expected_text)

    def test_empty_chunks_raises_same_error_shape(self) -> None:
        with patch("src.pipeline.load_book", return_value="source text"):
            with patch("src.pipeline.split_into_chunks", return_value=[]):
                with self.assertRaisesRegex(
                    ValueError,
                    r"^No readable content found in: books/sample_book\.txt$",
                ):
                    process_book("books/sample_book.txt")


if __name__ == "__main__":
    unittest.main()
