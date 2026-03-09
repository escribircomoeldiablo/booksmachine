from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.pipeline import process_book


class PipelineStructuralChunkerTests(unittest.TestCase):
    def test_structural_manifest_includes_chunking_node(self) -> None:
        source_text = "A " * 200 + "B " * 200
        text_hash = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.pipeline.OUTPUT_FOLDER", tmpdir):
                with patch("src.pipeline.STRUCTURE_PASS_ENABLED", True):
                    with patch("src.pipeline.STRUCTURE_PASS_USE_LLM", False):
                        with patch("src.pipeline.STRUCTURAL_CHUNKER_ENABLED", True):
                            with patch("src.pipeline.STRUCTURAL_CHUNKER_TARGET_SIZE", 100):
                                with patch("src.pipeline.STRUCTURAL_CHUNKER_MIN_SIZE", 20):
                                    with patch("src.pipeline.STRUCTURAL_CHUNKER_SPLIT_WINDOW", 40):
                                        with patch(
                                            "src.pipeline.load_book_with_structure",
                                            return_value=(source_text, None),
                                        ):
                                            with patch(
                                                "src.pipeline.build_document_map",
                                                return_value={
                                                    "version": "1.0",
                                                    "generator": "structure_pass_v1",
                                                    "text_hash": text_hash,
                                                    "source_fingerprint": "books/sample_book.txt",
                                                    "normalized_text_length": len(source_text),
                                                    "sections": [
                                                        {
                                                            "section_index": 0,
                                                            "id": "section_0",
                                                            "label": "S0",
                                                            "type": "chapter",
                                                            "start_page": 1,
                                                            "end_page": 1,
                                                            "start_char": 0,
                                                            "end_char": 350,
                                                            "confidence": 1.0,
                                                        },
                                                        {
                                                            "section_index": 1,
                                                            "id": "section_350",
                                                            "label": "S1",
                                                            "type": "chapter",
                                                            "start_page": 2,
                                                            "end_page": 2,
                                                            "start_char": 350,
                                                            "end_char": len(source_text),
                                                            "confidence": 1.0,
                                                        },
                                                    ],
                                                    "headings": [],
                                                    "stats": {
                                                        "heading_candidates": 0,
                                                        "classified_headings": 0,
                                                        "sections_generated": 2,
                                                        "unknown_sections": 0,
                                                    },
                                                },
                                            ) as map_mock:
                                                with patch(
                                                    "src.pipeline.summarize_chunk",
                                                    side_effect=lambda chunk: f"summary::{chunk[:10]}",
                                                ):
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

            self.assertEqual(map_mock.call_count, 1)
            checkpoints = list((Path(tmpdir) / ".checkpoints").glob("**/manifest.json"))
            self.assertTrue(checkpoints)
            manifest = json.loads(checkpoints[0].read_text(encoding="utf-8"))
            self.assertIn("chunking", manifest)
            self.assertEqual(manifest["chunking"]["mode"], "structural")
            self.assertEqual(manifest["chunking"]["target_size"], 100)
            self.assertEqual(manifest["chunking"]["min_size"], 20)
            self.assertEqual(manifest["chunking"]["split_window"], 40)

    def test_degenerate_document_map_falls_back_to_legacy(self) -> None:
        source_text = "source text " * 40
        text_hash = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.pipeline.OUTPUT_FOLDER", tmpdir):
                with patch("src.pipeline.STRUCTURE_PASS_ENABLED", True):
                    with patch("src.pipeline.STRUCTURE_PASS_USE_LLM", False):
                        with patch("src.pipeline.STRUCTURAL_CHUNKER_ENABLED", True):
                            with patch(
                                "src.pipeline.load_book_with_structure",
                                return_value=(source_text, None),
                            ):
                                with patch(
                                    "src.pipeline.build_document_map",
                                    return_value={
                                        "version": "1.0",
                                        "generator": "structure_pass_v1",
                                        "text_hash": text_hash,
                                        "source_fingerprint": "books/sample_book.txt",
                                        "normalized_text_length": len(source_text),
                                        "sections": [
                                            {
                                                "section_index": 0,
                                                "id": "section_0",
                                                "label": "only",
                                                "type": "unknown",
                                                "start_page": None,
                                                "end_page": None,
                                                "start_char": 0,
                                                "end_char": len(source_text),
                                                "confidence": 0.0,
                                            }
                                        ],
                                        "headings": [],
                                        "stats": {
                                            "heading_candidates": 0,
                                            "classified_headings": 0,
                                            "sections_generated": 1,
                                            "unknown_sections": 1,
                                        },
                                    },
                                ):
                                    with patch(
                                        "src.pipeline.split_into_chunks",
                                        return_value=["c1", "c2"],
                                    ) as legacy_mock:
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
            self.assertEqual(legacy_mock.call_count, 1)
            checkpoints = list((Path(tmpdir) / ".checkpoints").glob("**/manifest.json"))
            self.assertTrue(checkpoints)
            manifest = json.loads(checkpoints[0].read_text(encoding="utf-8"))
            self.assertEqual(manifest["chunking"]["mode"], "legacy")
            self.assertEqual(manifest["chunking"]["target_size"], 1800)
            self.assertEqual(manifest["chunking"]["min_size"], 0)
            self.assertEqual(manifest["chunking"]["split_window"], 0)


if __name__ == "__main__":
    unittest.main()
