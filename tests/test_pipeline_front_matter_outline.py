from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.pipeline import process_book


class PipelineFrontMatterOutlineTests(unittest.TestCase):
    def test_generates_front_matter_outline_when_signal_exists(self) -> None:
        text = (
            "Table of Contents\n"
            "Chapter 1 Houses .......... 5\n\n"
            "Preface\n"
            "This book explains natal astrology.\n\n"
            "Introduction\n"
            "The doctrine covers houses, planets, and lots.\n\n"
            "CHAPTER 1 HOUSES\n"
            "Body text.\n"
        )
        llm_payload = {
            "schema_version": "1.0.0",
            "book_title": "ignored",
            "source": {
                "has_toc": True,
                "has_introduction": True,
                "has_preface": True,
                "strategy": "mixed",
            },
            "family_candidates": [
                {
                    "name": "Natal Astrology",
                    "aliases": [],
                    "evidence": ["Preface mentions natal astrology"],
                    "confidence": 0.75,
                    "status": "candidate",
                }
            ],
            "core_concepts_expected": [
                {
                    "name": "houses",
                    "evidence": ["Introduction mentions houses"],
                    "priority": "high",
                }
            ],
            "provisional_taxonomy": [],
            "normalization_hints": [
                {"canonical": "lots", "variants": ["Lot", "Lots"]}
            ],
            "confidence_notes": ["preliminary only"],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                patch("src.pipeline.OUTPUT_FOLDER", tmpdir),
                patch("src.pipeline.FRONT_MATTER_OUTLINE_ENABLED", True),
                patch("src.pipeline.STRUCTURE_PASS_USE_LLM", False),
                patch("src.pipeline.load_book_with_structure", return_value=(text, None)),
                patch("src.pipeline.split_into_chunks", return_value=["c1"]),
                patch("src.pipeline.summarize_chunk", return_value="summary::c1"),
                patch("src.front_matter_extractor.ask_llm", return_value=json.dumps(llm_payload, ensure_ascii=False)),
                patch(
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
                ),
                patch("src.pipeline.synthesize_compendium", return_value=("compendium::global", 0)),
            ):
                process_book("books/sample_book.txt", verbose=False)

            artifact_path = Path(tmpdir) / "sample_book_front_matter_outline.json"
            self.assertTrue(artifact_path.exists())
            payload = json.loads(artifact_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["book_title"], "sample_book")
            self.assertEqual(payload["source"]["strategy"], "mixed")
            self.assertEqual(payload["family_candidates"][0]["name"], "Natal Astrology")
            self.assertEqual(payload["normalization_hints"][0]["variants"], ["Lot", "Lots"])

    def test_fallback_artifact_is_austere_when_no_signal_exists(self) -> None:
        text = "Copyright 2020.\nAll rights reserved.\nSeries page.\n\nAcknowledgements.\n"
        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                patch("src.pipeline.OUTPUT_FOLDER", tmpdir),
                patch("src.pipeline.FRONT_MATTER_OUTLINE_ENABLED", True),
                patch("src.pipeline.STRUCTURE_PASS_ENABLED", False),
                patch("src.pipeline.load_book", return_value=text),
                patch("src.pipeline.split_into_chunks", return_value=["c1"]),
                patch("src.pipeline.summarize_chunk", return_value="summary::c1"),
                patch("src.front_matter_extractor.ask_llm", return_value="not-json"),
                patch(
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
                ),
                patch("src.pipeline.synthesize_compendium", return_value=("compendium::global", 0)),
            ):
                process_book("books/sample_book.txt", verbose=False)

            artifact_path = Path(tmpdir) / "sample_book_front_matter_outline.json"
            payload = json.loads(artifact_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["family_candidates"], [])
            self.assertEqual(payload["core_concepts_expected"], [])
            self.assertEqual(payload["source"]["strategy"], "initial_excerpt")
            self.assertTrue(payload["confidence_notes"])

    def test_no_contamination_of_knowledge_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                patch("src.pipeline.OUTPUT_FOLDER", tmpdir),
                patch("src.pipeline.FRONT_MATTER_OUTLINE_ENABLED", True),
                patch("src.pipeline.STRUCTURE_PASS_ENABLED", False),
                patch("src.pipeline.load_book", return_value="Preface\nIntro text.\n"),
                patch("src.pipeline.split_into_chunks", return_value=["c1"]),
                patch("src.pipeline.summarize_chunk", return_value="summary::c1"),
                patch("src.front_matter_extractor.ask_llm", return_value="{}"),
                patch(
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
                ),
                patch("src.pipeline.synthesize_compendium", return_value=("compendium::global", 0)),
            ):
                process_book("books/sample_book.txt", verbose=False)

            self.assertTrue((Path(tmpdir) / "sample_book_front_matter_outline.json").exists())
            self.assertFalse((Path(tmpdir) / "sample_book_knowledge_concepts.json").exists())
            self.assertFalse((Path(tmpdir) / "sample_book_knowledge_families.json").exists())
            self.assertFalse((Path(tmpdir) / "sample_book_knowledge_ontology.json").exists())

    def test_disabled_flag_skips_front_matter_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                patch("src.pipeline.OUTPUT_FOLDER", tmpdir),
                patch("src.pipeline.FRONT_MATTER_OUTLINE_ENABLED", False),
                patch("src.pipeline.STRUCTURE_PASS_ENABLED", False),
                patch("src.pipeline.load_book", return_value="Preface\nIntro text.\n"),
                patch("src.pipeline.split_into_chunks", return_value=["c1"]),
                patch("src.pipeline.summarize_chunk", return_value="summary::c1"),
                patch(
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
                ),
                patch("src.pipeline.synthesize_compendium", return_value=("compendium::global", 0)),
            ):
                process_book("books/sample_book.txt", verbose=False)

            self.assertFalse((Path(tmpdir) / "sample_book_front_matter_outline.json").exists())

    def test_editorial_noise_produces_low_signal_artifact_without_breaking_pipeline(self) -> None:
        text = (
            "Copyright Page\n"
            "All rights reserved.\n\n"
            "Acknowledgements\n"
            "Thanks to all contributors.\n\n"
            "Series Page\n"
            "Library of Ancient Studies.\n\n"
            "Contents\n"
            "PART SEVEN: DOWN TO EARTH 595 61. DOWN TO EARTH 597\n"
            "Chapter 2.............................. 61\n\n"
            "A Door Opens\n"
            "A rhetorical scene-setting section.\n"
        )
        llm_payload = {
            "schema_version": "1.0.0",
            "book_title": "ignored",
            "source": {
                "has_toc": True,
                "has_introduction": False,
                "has_preface": False,
                "strategy": "mixed",
            },
            "family_candidates": [],
            "core_concepts_expected": [],
            "provisional_taxonomy": [],
            "normalization_hints": [],
            "confidence_notes": ["low confidence due to mostly editorial noise"],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                patch("src.pipeline.OUTPUT_FOLDER", tmpdir),
                patch("src.pipeline.FRONT_MATTER_OUTLINE_ENABLED", True),
                patch("src.pipeline.STRUCTURE_PASS_USE_LLM", False),
                patch("src.pipeline.load_book_with_structure", return_value=(text, None)),
                patch("src.pipeline.split_into_chunks", return_value=["c1"]),
                patch("src.pipeline.summarize_chunk", return_value="summary::c1"),
                patch("src.front_matter_extractor.ask_llm", return_value=json.dumps(llm_payload, ensure_ascii=False)),
                patch(
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
                ),
                patch("src.pipeline.synthesize_compendium", return_value=("compendium::global", 0)),
            ):
                output_path = process_book("books/sample_book.txt", verbose=False)

            self.assertTrue(Path(output_path).exists())
            payload = json.loads((Path(tmpdir) / "sample_book_front_matter_outline.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["family_candidates"], [])
            self.assertTrue(any("low confidence" in note for note in payload["confidence_notes"]))


if __name__ == "__main__":
    unittest.main()
