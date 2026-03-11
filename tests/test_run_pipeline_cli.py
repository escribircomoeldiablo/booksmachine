from __future__ import annotations

import sys
import unittest
from unittest.mock import patch

import run_pipeline


class RunPipelineCliTests(unittest.TestCase):
    def test_cli_passes_output_and_knowledge_languages(self) -> None:
        with patch.object(
            sys,
            "argv",
            [
                "run_pipeline.py",
                "books/sample_book.txt",
                "--output-language",
                "es",
                "--knowledge-language",
                "original",
            ],
        ), patch("run_pipeline.process_book") as process_mock:
            run_pipeline.main()

        process_mock.assert_called_once_with(
            "books/sample_book.txt",
            mode="full",
            max_chunks=None,
            dry_run=False,
            verbose=True,
            resume=True,
            output_language="es",
            knowledge_language="original",
            output_folder=None,
            front_matter_outline_enabled=None,
        )

    def test_cli_passes_front_matter_override(self) -> None:
        with patch.object(
            sys,
            "argv",
            [
                "run_pipeline.py",
                "books/sample_book.txt",
                "--front-matter-outline",
            ],
        ), patch("run_pipeline.process_book") as process_mock:
            run_pipeline.main()

        process_mock.assert_called_once_with(
            "books/sample_book.txt",
            mode="full",
            max_chunks=None,
            dry_run=False,
            verbose=True,
            resume=True,
            output_language="es",
            knowledge_language="original",
            output_folder=None,
            front_matter_outline_enabled=True,
        )


if __name__ == "__main__":
    unittest.main()
