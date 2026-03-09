from __future__ import annotations

import tempfile
import unittest
from unittest.mock import patch

from src.pipeline import process_book
from src.summarizer import build_summary_prompt
from src.synthesizer import build_block_prompt, build_compendium_prompt


class OutputLanguageAndProgressTests(unittest.TestCase):
    def test_summary_prompt_can_target_original_language(self) -> None:
        prompt = build_summary_prompt("Latin text", output_language="original")
        self.assertIn("idioma original", prompt)

    def test_synthesis_prompts_can_target_original_language(self) -> None:
        chunk_prompt = build_block_prompt(
            1,
            [{"chunk_index": 1, "summary_text": "summary"}],
            output_language="original",
        )
        self.assertIn("idioma original", chunk_prompt)

        compendium_prompt = build_compendium_prompt(
            [
                {
                    "block_index": 1,
                    "chunk_start": 1,
                    "chunk_end": 1,
                    "chunk_indices": [1],
                    "summary_text": "block",
                }
            ],
            output_language="original",
        )
        self.assertIn("idioma original", compendium_prompt)

    def test_pipeline_reports_progress_events(self) -> None:
        events: list[tuple[str, str]] = []

        def on_progress(stage: str, message: str, _: dict[str, object]) -> None:
            events.append((stage, message))

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.pipeline.OUTPUT_FOLDER", tmpdir):
                with patch("src.pipeline.load_book", return_value="source text"):
                    with patch("src.pipeline.split_into_chunks", return_value=["c1"]):
                        with patch("src.pipeline.summarize_chunk", return_value="summary::c1"):
                            with patch(
                                "src.pipeline.synthesize_blocks",
                                return_value=(
                                    [
                                        {
                                            "block_index": 1,
                                            "chunk_start": 1,
                                            "chunk_end": 1,
                                            "chunk_indices": [1],
                                            "summary_text": "block::1",
                                        }
                                    ],
                                    1,
                                ),
                            ):
                                with patch(
                                    "src.pipeline.synthesize_compendium",
                                    return_value=("compendium::global", 0),
                                ):
                                    process_book(
                                        "books/sample_book.txt",
                                        output_language="es",
                                        progress_callback=on_progress,
                                        verbose=False,
                                    )

        stages = [stage for stage, _ in events]
        self.assertIn("loading", stages)
        self.assertIn("chunking", stages)
        self.assertIn("preflight", stages)
        self.assertIn("summarizing", stages)
        self.assertIn("synthesis", stages)
        self.assertIn("writing", stages)
        self.assertIn("done", stages)


if __name__ == "__main__":
    unittest.main()
