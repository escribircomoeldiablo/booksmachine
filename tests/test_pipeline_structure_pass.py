from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.pipeline import process_book


class PipelineStructurePassTests(unittest.TestCase):
    def test_structure_pass_observation_writes_document_map_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.pipeline.OUTPUT_FOLDER", tmpdir):
                with patch("src.pipeline.STRUCTURE_PASS_ENABLED", True):
                    with patch("src.pipeline.STRUCTURE_PASS_USE_LLM", False):
                        with patch(
                            "src.pipeline.load_book_with_structure",
                            return_value=("CHAPTER 1 INTRODUCTION\nBody.", None),
                        ):
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
                                            process_book("books/sample_book.txt", verbose=False)

            sidecar_path = Path(tmpdir) / "sample_book_document_map.json"
            self.assertTrue(sidecar_path.exists())
            payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
            self.assertIn("metadata", payload)
            self.assertIn("document_map", payload)
            self.assertEqual(payload["metadata"]["structure_version"], "1.0")
            self.assertEqual(payload["metadata"]["generator"], "structure_pass_v1")
            sections = payload["document_map"]["sections"]
            self.assertGreaterEqual(len(sections), 1)
            self.assertEqual(sections[0]["section_index"], 0)


if __name__ == "__main__":
    unittest.main()
