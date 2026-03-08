from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from src.pipeline import process_book


class PipelineControlTests(unittest.TestCase):
    def test_dry_run_does_not_call_llm_compile_or_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.pipeline.OUTPUT_FOLDER", tmpdir):
                with patch("src.pipeline.load_book", return_value="source text"):
                    with patch("src.pipeline.split_into_chunks", return_value=["c1", "c2"]):
                        with patch("src.pipeline.summarize_chunk") as summarize_mock:
                            with patch("src.pipeline.compile_chunk_summaries") as compile_mock:
                                output_path = process_book(
                                    "books/sample_book.txt",
                                    dry_run=True,
                                    verbose=False,
                                )

            self.assertFalse(Path(output_path).exists())
            self.assertFalse((Path(tmpdir) / ".checkpoints").exists())
            summarize_mock.assert_not_called()
            compile_mock.assert_not_called()

    def test_max_chunks_limits_llm_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.pipeline.OUTPUT_FOLDER", tmpdir):
                with patch("src.pipeline.load_book", return_value="source text"):
                    with patch(
                        "src.pipeline.split_into_chunks",
                        return_value=["c1", "c2", "c3"],
                    ):
                        with patch(
                            "src.pipeline.summarize_chunk",
                            side_effect=lambda chunk: f"summary::{chunk}",
                        ) as summarize_mock:
                            output_path = process_book(
                                "books/sample_book.txt",
                                mode="smoke",
                                max_chunks=2,
                                verbose=False,
                            )

            output_text = Path(output_path).read_text(encoding="utf-8")
            self.assertEqual(summarize_mock.call_count, 2)
            self.assertEqual(output_text.count("## Chunk "), 2)

    def test_resume_reuses_existing_checkpoints(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.pipeline.OUTPUT_FOLDER", tmpdir):
                with patch("src.pipeline.load_book", return_value="source text"):
                    with patch(
                        "src.pipeline.split_into_chunks",
                        return_value=["c1", "c2", "c3"],
                    ):
                        with patch(
                            "src.pipeline.summarize_chunk",
                            side_effect=lambda chunk: f"summary::{chunk}",
                        ) as first_run_mock:
                            process_book(
                                "books/sample_book.txt",
                                max_chunks=1,
                                verbose=False,
                            )
                        self.assertEqual(first_run_mock.call_count, 1)

                        with patch(
                            "src.pipeline.summarize_chunk",
                            side_effect=lambda chunk: f"summary::{chunk}",
                        ) as second_run_mock:
                            output_path = process_book(
                                "books/sample_book.txt",
                                mode="full",
                                verbose=False,
                            )

            output_text = Path(output_path).read_text(encoding="utf-8")
            self.assertEqual(second_run_mock.call_count, 2)
            self.assertEqual(output_text.count("## Chunk "), 3)

    def test_changed_input_invalidates_old_checkpoints(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.pipeline.OUTPUT_FOLDER", tmpdir):
                with patch("src.pipeline.split_into_chunks", return_value=["c1", "c2"]):
                    with patch("src.pipeline.load_book", return_value="source text v1"):
                        with patch(
                            "src.pipeline.summarize_chunk",
                            side_effect=lambda chunk: f"summary::{chunk}",
                        ) as first_run_mock:
                            process_book(
                                "books/sample_book.txt",
                                max_chunks=1,
                                verbose=False,
                            )
                        self.assertEqual(first_run_mock.call_count, 1)

                    with patch("src.pipeline.load_book", return_value="source text v2"):
                        with patch(
                            "src.pipeline.summarize_chunk",
                            side_effect=lambda chunk: f"summary::{chunk}",
                        ) as second_run_mock:
                            process_book(
                                "books/sample_book.txt",
                                mode="full",
                                verbose=False,
                            )
                        self.assertEqual(second_run_mock.call_count, 2)

    def test_preflight_and_final_counters_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.pipeline.OUTPUT_FOLDER", tmpdir):
                with patch("src.pipeline.load_book", return_value="source text"):
                    with patch("src.pipeline.split_into_chunks", return_value=["c1", "c2", "c3"]):
                        with patch(
                            "src.pipeline.summarize_chunk",
                            side_effect=lambda chunk: f"summary::{chunk}",
                        ):
                            capture = io.StringIO()
                            with redirect_stdout(capture):
                                process_book(
                                    "books/sample_book.txt",
                                    mode="smoke",
                                    max_chunks=1,
                                    verbose=True,
                                )

            report = capture.getvalue()
            self.assertIn("Total chunks detected:", report)
            self.assertIn("Chunks to process:", report)
            self.assertIn("Chunks really processed:", report)
            self.assertIn("LLM calls expected:", report)
            self.assertIn("LLM calls made:", report)


if __name__ == "__main__":
    unittest.main()
