from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.pipeline import process_book


def _section(
    *,
    section_index: int,
    start_char: int,
    end_char: int,
    label: str,
    section_type: str,
    confidence: float = 1.0,
) -> dict[str, object]:
    return {
        "section_index": section_index,
        "id": f"section_{start_char}",
        "label": label,
        "type": section_type,
        "start_page": 1,
        "end_page": 1,
        "start_char": start_char,
        "end_char": end_char,
        "confidence": confidence,
    }


class PipelineStructuralChunkerTests(unittest.TestCase):
    def test_structural_manifest_includes_quality_and_chunking_nodes(self) -> None:
        source_text = "A " * 200 + "B " * 200
        text_hash = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
        structure_map = {
            "version": "1.0",
            "generator": "structure_pass_v1",
            "text_hash": text_hash,
            "source_fingerprint": "books/sample_book.txt",
            "normalized_text_length": len(source_text),
            "sections": [
                _section(section_index=0, start_char=0, end_char=200, label="CHAPTER ONE", section_type="chapter"),
                _section(section_index=1, start_char=200, end_char=len(source_text), label="2. Intro", section_type="section"),
            ],
            "headings": [],
            "stats": {
                "heading_candidates": 20,
                "classified_headings": 10,
                "sections_generated": 2,
                "unknown_sections": 0,
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.pipeline.OUTPUT_FOLDER", tmpdir), patch("src.pipeline.STRUCTURE_PASS_ENABLED", True), patch(
                "src.pipeline.STRUCTURE_PASS_USE_LLM", False
            ), patch("src.pipeline.STRUCTURAL_CHUNKER_ENABLED", True), patch(
                "src.pipeline.STRUCTURAL_CHUNKER_TARGET_SIZE", 100
            ), patch(
                "src.pipeline.STRUCTURAL_CHUNKER_MIN_SIZE", 20
            ), patch(
                "src.pipeline.STRUCTURAL_CHUNKER_SPLIT_WINDOW", 40
            ), patch(
                "src.pipeline.STRUCTURAL_CHUNKER_EXCLUDED_TYPES", {"index", "bibliography"}
            ), patch(
                "src.pipeline.load_book_with_structure", return_value=(source_text, None)
            ), patch(
                "src.pipeline.build_document_map", return_value=structure_map
            ), patch(
                "src.pipeline.build_structural_chunks",
                return_value={
                    "chunks": [
                        {
                            "chunk_index": 0,
                            "chunk_id": "chunk_0",
                            "section_id": "section_0",
                            "section_index": 0,
                            "start_char": 0,
                            "end_char": 450,
                            "start_page": 1,
                            "end_page": 1,
                            "text": "A" * 450,
                        },
                        {
                            "chunk_index": 1,
                            "chunk_id": "chunk_1",
                            "section_id": "section_200",
                            "section_index": 1,
                            "start_char": 450,
                            "end_char": 900,
                            "start_page": 1,
                            "end_page": 1,
                            "text": "B" * 450,
                        },
                    ],
                    "stats": {
                        "total_chunks": 2,
                        "avg_chunk_size": 450.0,
                        "sections_consumed": 2,
                        "sections_split": 0,
                        "sections_merged": 0,
                    },
                },
            ), patch(
                "src.pipeline.split_into_chunks", return_value=["l1", "l2", "l3", "l4"]
            ), patch(
                "src.pipeline.summarize_chunk", side_effect=lambda chunk: f"summary::{chunk[:10]}"
            ), patch(
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
            ), patch("src.pipeline.synthesize_compendium", return_value=("compendium::global", 0)):
                process_book("books/sample_book.txt", verbose=False)

            checkpoints = list((Path(tmpdir) / ".checkpoints").glob("**/manifest.json"))
            self.assertTrue(checkpoints)
            manifest = json.loads(checkpoints[0].read_text(encoding="utf-8"))
            self.assertIn("chunking", manifest)
            self.assertIn("structure_quality", manifest)
            self.assertEqual(manifest["chunking"]["mode"], "structural")
            self.assertTrue(manifest["structure_quality_passed"])
            self.assertIsNone(manifest["fallback_reason"])

    def test_semantic_gate_unknown_ratio_falls_back_to_legacy(self) -> None:
        source_text = "source text " * 80
        text_hash = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
        sections = [
            _section(section_index=0, start_char=0, end_char=300, label="noise", section_type="unknown", confidence=0.0),
            _section(
                section_index=1,
                start_char=300,
                end_char=600,
                label="unknown",
                section_type="unknown",
                confidence=0.0,
            ),
            _section(
                section_index=2,
                start_char=600,
                end_char=len(source_text),
                label="noise",
                section_type="unknown",
                confidence=0.0,
            ),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.pipeline.OUTPUT_FOLDER", tmpdir), patch("src.pipeline.STRUCTURE_PASS_ENABLED", True), patch(
                "src.pipeline.STRUCTURE_PASS_USE_LLM", False
            ), patch("src.pipeline.STRUCTURAL_CHUNKER_ENABLED", True), patch(
                "src.pipeline.load_book_with_structure", return_value=(source_text, None)
            ), patch(
                "src.pipeline.build_document_map",
                return_value={
                    "version": "1.0",
                    "generator": "structure_pass_v1",
                    "text_hash": text_hash,
                    "source_fingerprint": "books/sample_book.txt",
                    "normalized_text_length": len(source_text),
                    "sections": sections,
                    "headings": [],
                    "stats": {
                        "heading_candidates": 5,
                        "classified_headings": 0,
                        "sections_generated": len(sections),
                        "unknown_sections": len(sections),
                    },
                },
            ), patch("src.pipeline.split_into_chunks", return_value=["c1", "c2"]) as legacy_mock, patch(
                "src.pipeline.summarize_chunk", side_effect=lambda chunk: f"summary::{chunk}"
            ), patch(
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
            ), patch("src.pipeline.synthesize_compendium", return_value=("compendium::global", 0)):
                process_book("books/sample_book.txt", verbose=False)

            self.assertEqual(legacy_mock.call_count, 1)
            manifest = json.loads(next((Path(tmpdir) / ".checkpoints").glob("**/manifest.json")).read_text(encoding="utf-8"))
            self.assertEqual(manifest["chunking"]["mode"], "legacy")
            self.assertEqual(manifest["fallback_reason"], "semantic_gate_unknown_ratio")

    def test_structural_map_insufficient_sections_falls_back_to_legacy(self) -> None:
        source_text = "source text " * 20
        text_hash = hashlib.sha256(source_text.encode("utf-8")).hexdigest()

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.pipeline.OUTPUT_FOLDER", tmpdir), patch("src.pipeline.STRUCTURE_PASS_ENABLED", True), patch(
                "src.pipeline.STRUCTURE_PASS_USE_LLM", False
            ), patch("src.pipeline.STRUCTURAL_CHUNKER_ENABLED", True), patch(
                "src.pipeline.load_book_with_structure", return_value=(source_text, None)
            ), patch(
                "src.pipeline.build_document_map",
                return_value={
                    "version": "1.0",
                    "generator": "structure_pass_v1",
                    "text_hash": text_hash,
                    "source_fingerprint": "books/sample_book.txt",
                    "normalized_text_length": len(source_text),
                    "sections": [
                        _section(
                            section_index=0,
                            start_char=0,
                            end_char=len(source_text),
                            label="only",
                            section_type="unknown",
                            confidence=0.0,
                        )
                    ],
                    "headings": [],
                    "stats": {
                        "heading_candidates": 0,
                        "classified_headings": 0,
                        "sections_generated": 1,
                        "unknown_sections": 1,
                    },
                },
            ), patch("src.pipeline.split_into_chunks", return_value=["c1", "c2"]), patch(
                "src.pipeline.summarize_chunk", side_effect=lambda chunk: f"summary::{chunk}"
            ), patch(
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
            ), patch("src.pipeline.synthesize_compendium", return_value=("compendium::global", 0)):
                process_book("books/sample_book.txt", verbose=False)

            manifest = json.loads(next((Path(tmpdir) / ".checkpoints").glob("**/manifest.json")).read_text(encoding="utf-8"))
            self.assertEqual(manifest["chunking"]["mode"], "legacy")
            self.assertEqual(manifest["fallback_reason"], "structural_map_insufficient_sections")

    def test_semantic_gate_index_like_ratio_falls_back_to_legacy(self) -> None:
        source_text = "source text " * 120
        text_hash = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
        sections = [
            _section(section_index=0, start_char=0, end_char=250, label="W", section_type="chapter"),
            _section(section_index=1, start_char=250, end_char=500, label="Xenocrates 784", section_type="section"),
            _section(section_index=2, start_char=500, end_char=len(source_text), label="CHAPTER TITLE", section_type="chapter"),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.pipeline.OUTPUT_FOLDER", tmpdir), patch("src.pipeline.STRUCTURE_PASS_ENABLED", True), patch(
                "src.pipeline.STRUCTURE_PASS_USE_LLM", False
            ), patch("src.pipeline.STRUCTURAL_CHUNKER_ENABLED", True), patch(
                "src.pipeline.load_book_with_structure", return_value=(source_text, None)
            ), patch(
                "src.pipeline.build_document_map",
                return_value={
                    "version": "1.0",
                    "generator": "structure_pass_v1",
                    "text_hash": text_hash,
                    "source_fingerprint": "books/sample_book.txt",
                    "normalized_text_length": len(source_text),
                    "sections": sections,
                    "headings": [],
                    "stats": {
                        "heading_candidates": 20,
                        "classified_headings": 10,
                        "sections_generated": len(sections),
                        "unknown_sections": 0,
                    },
                },
            ), patch("src.pipeline.split_into_chunks", return_value=["c1", "c2"]), patch(
                "src.pipeline.summarize_chunk", side_effect=lambda chunk: f"summary::{chunk}"
            ), patch(
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
            ), patch("src.pipeline.synthesize_compendium", return_value=("compendium::global", 0)):
                process_book("books/sample_book.txt", verbose=False)

            manifest = json.loads(next((Path(tmpdir) / ".checkpoints").glob("**/manifest.json")).read_text(encoding="utf-8"))
            self.assertEqual(manifest["chunking"]["mode"], "legacy")
            self.assertEqual(manifest["fallback_reason"], "semantic_gate_index_like_ratio")

    def test_semantic_gate_secondary_metrics_falls_back_to_legacy(self) -> None:
        source_text = "short text"
        text_hash = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
        sections = [
            _section(section_index=0, start_char=0, end_char=3, label="INDEX", section_type="index"),
            _section(section_index=1, start_char=3, end_char=6, label="BIB", section_type="bibliography"),
            _section(section_index=2, start_char=6, end_char=9, label="INDEX", section_type="index"),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.pipeline.OUTPUT_FOLDER", tmpdir), patch("src.pipeline.STRUCTURE_PASS_ENABLED", True), patch(
                "src.pipeline.STRUCTURE_PASS_USE_LLM", False
            ), patch("src.pipeline.STRUCTURAL_CHUNKER_ENABLED", True), patch(
                "src.pipeline.load_book_with_structure", return_value=(source_text, None)
            ), patch(
                "src.pipeline.build_document_map",
                return_value={
                    "version": "1.0",
                    "generator": "structure_pass_v1",
                    "text_hash": text_hash,
                    "source_fingerprint": "books/sample_book.txt",
                    "normalized_text_length": len(source_text),
                    "sections": sections,
                    "headings": [],
                    "stats": {
                        "heading_candidates": 100,
                        "classified_headings": 0,
                        "sections_generated": len(sections),
                        "unknown_sections": 0,
                    },
                },
            ), patch("src.pipeline.split_into_chunks", return_value=["c1"]), patch(
                "src.pipeline.summarize_chunk", side_effect=lambda chunk: f"summary::{chunk}"
            ), patch(
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
            ), patch("src.pipeline.synthesize_compendium", return_value=("compendium::global", 0)):
                process_book("books/sample_book.txt", verbose=False)

            manifest = json.loads(next((Path(tmpdir) / ".checkpoints").glob("**/manifest.json")).read_text(encoding="utf-8"))
            self.assertEqual(manifest["chunking"]["mode"], "legacy")
            self.assertEqual(manifest["fallback_reason"], "semantic_gate_secondary_metrics")

    def test_postcheck_chunk_count_falls_back_to_legacy(self) -> None:
        source_text = "A " * 500
        text_hash = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
        structure_map = {
            "version": "1.0",
            "generator": "structure_pass_v1",
            "text_hash": text_hash,
            "source_fingerprint": "books/sample_book.txt",
            "normalized_text_length": len(source_text),
            "sections": [
                _section(section_index=0, start_char=0, end_char=len(source_text), label="CHAPTER", section_type="chapter"),
                _section(section_index=1, start_char=len(source_text), end_char=len(source_text) + 1, label="2. S", section_type="section"),
            ],
            "headings": [],
            "stats": {
                "heading_candidates": 20,
                "classified_headings": 10,
                "sections_generated": 2,
                "unknown_sections": 0,
            },
        }
        fake_structural = {
            "chunks": [
                {
                    "chunk_index": idx,
                    "chunk_id": f"chunk_{idx}",
                    "section_id": "section_0",
                    "section_index": 0,
                    "start_char": idx,
                    "end_char": idx + 10,
                    "start_page": 1,
                    "end_page": 1,
                    "text": "abcdefghij",
                }
                for idx in range(10)
            ],
            "stats": {
                "total_chunks": 10,
                "avg_chunk_size": 10.0,
                "sections_consumed": 1,
                "sections_split": 1,
                "sections_merged": 0,
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.pipeline.OUTPUT_FOLDER", tmpdir), patch("src.pipeline.STRUCTURE_PASS_ENABLED", True), patch(
                "src.pipeline.STRUCTURE_PASS_USE_LLM", False
            ), patch("src.pipeline.STRUCTURAL_CHUNKER_ENABLED", True), patch(
                "src.pipeline.load_book_with_structure", return_value=(source_text, None)
            ), patch("src.pipeline.build_document_map", return_value=structure_map), patch(
                "src.pipeline.build_structural_chunks", return_value=fake_structural
            ), patch("src.pipeline.split_into_chunks", return_value=["l1", "l2", "l3"]), patch(
                "src.pipeline.summarize_chunk", side_effect=lambda chunk: f"summary::{chunk}"
            ), patch(
                "src.pipeline.synthesize_blocks",
                return_value=(
                    [
                        {
                            "block_index": 1,
                            "chunk_start": 1,
                            "chunk_end": 3,
                            "chunk_indices": [1, 2, 3],
                            "summary_text": "block::1",
                        }
                    ],
                    1,
                ),
            ), patch("src.pipeline.synthesize_compendium", return_value=("compendium::global", 0)):
                process_book("books/sample_book.txt", verbose=False)

            manifest = json.loads(next((Path(tmpdir) / ".checkpoints").glob("**/manifest.json")).read_text(encoding="utf-8"))
            self.assertEqual(manifest["fallback_reason"], "postcheck_chunk_count")
            self.assertEqual(manifest["chunking"]["mode"], "legacy")
            self.assertFalse(manifest["structural_postcheck_passed"])

    def test_excluded_types_are_passed_to_structural_chunker(self) -> None:
        source_text = "A " * 200 + "B " * 200
        text_hash = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
        structure_map = {
            "version": "1.0",
            "generator": "structure_pass_v1",
            "text_hash": text_hash,
            "source_fingerprint": "books/sample_book.txt",
            "normalized_text_length": len(source_text),
            "sections": [
                _section(section_index=0, start_char=0, end_char=300, label="CHAPTER", section_type="chapter"),
                _section(section_index=1, start_char=300, end_char=len(source_text), label="INDEX", section_type="index"),
            ],
            "headings": [],
            "stats": {
                "heading_candidates": 20,
                "classified_headings": 10,
                "sections_generated": 2,
                "unknown_sections": 0,
            },
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.pipeline.OUTPUT_FOLDER", tmpdir), patch("src.pipeline.STRUCTURE_PASS_ENABLED", True), patch(
                "src.pipeline.STRUCTURE_PASS_USE_LLM", False
            ), patch("src.pipeline.STRUCTURAL_CHUNKER_ENABLED", True), patch(
                "src.pipeline.STRUCTURAL_CHUNKER_EXCLUDED_TYPES", {"index", "bibliography"}
            ), patch(
                "src.pipeline.STRUCTURAL_CHUNKER_MIN_SIZE", 200
            ), patch("src.pipeline.STRUCTURAL_CHUNKER_TARGET_SIZE", 10000), patch(
                "src.pipeline.load_book_with_structure", return_value=(source_text, None)
            ), patch("src.pipeline.build_document_map", return_value=structure_map), patch(
                "src.pipeline.split_into_chunks", return_value=["l1", "l2"]
            ), patch(
                "src.pipeline.build_structural_chunks",
                return_value={
                    "chunks": [
                        {
                            "chunk_index": 0,
                            "chunk_id": "chunk_0",
                            "section_id": "section_0",
                            "section_index": 0,
                            "start_char": 0,
                            "end_char": 500,
                            "start_page": 1,
                            "end_page": 1,
                            "text": "A" * 500,
                        }
                    ],
                    "stats": {
                        "total_chunks": 1,
                        "avg_chunk_size": 500.0,
                        "sections_consumed": 1,
                        "sections_split": 0,
                        "sections_merged": 0,
                    },
                },
            ) as structural_mock, patch("src.pipeline.summarize_chunk", return_value="summary"), patch(
                "src.pipeline.synthesize_blocks",
                return_value=(
                    [
                        {
                            "block_index": 1,
                            "chunk_start": 1,
                            "chunk_end": 1,
                            "chunk_indices": [1],
                            "summary_text": "block",
                        }
                    ],
                    1,
                ),
            ), patch("src.pipeline.synthesize_compendium", return_value=("compendium", 0)):
                process_book("books/sample_book.txt", verbose=False)

            self.assertEqual(structural_mock.call_count, 1)
            call_kwargs = structural_mock.call_args.kwargs
            self.assertEqual(call_kwargs["excluded_section_types"], {"index", "bibliography"})
            manifest = json.loads(next((Path(tmpdir) / ".checkpoints").glob("**/manifest.json")).read_text(encoding="utf-8"))
            self.assertEqual(manifest["excluded_section_types_active"], ["bibliography", "index"])
            self.assertEqual(manifest["excluded_sections_count"], 1)


if __name__ == "__main__":
    unittest.main()
