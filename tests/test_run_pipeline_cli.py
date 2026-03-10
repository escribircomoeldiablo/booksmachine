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
        )


if __name__ == "__main__":
    unittest.main()
