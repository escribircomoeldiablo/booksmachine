from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.argument_extractor import ExtractionResult
from src.argument_schema import ArgumentChunkV1
from src.pipeline import process_book


def _argument_record(
    *,
    chunk_id: str,
    thesis: str | None = None,
    claim: str | None = None,
    evidence: str | None = None,
    key_term: str | None = None,
) -> ArgumentChunkV1:
    return ArgumentChunkV1(
        schema_version="1.0.0",
        chunk_id=chunk_id,
        source_fingerprint="book_hash",
        section_refs=[],
        theses=[thesis] if thesis else [],
        claims=[claim] if claim else [],
        evidence=[evidence] if evidence else [],
        methods=[],
        authors_or_schools=[],
        key_terms=[key_term] if key_term else [],
        debates=[],
        limitations=[],
    )


class PipelineArgumentativeTests(unittest.TestCase):
    def test_argumentative_profile_generates_argument_artifacts_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                patch("src.pipeline.OUTPUT_FOLDER", tmpdir),
                patch("src.pipeline.STRUCTURE_PASS_ENABLED", False),
                patch("src.pipeline.load_book", return_value="source text"),
                patch("src.pipeline.split_into_chunks", return_value=["c1", "c2"]),
                patch(
                    "src.pipeline.extract_argument_chunk",
                    side_effect=[
                        ExtractionResult(
                            record=_argument_record(chunk_id="legacy_chunk_1", thesis="T1", evidence="E1", key_term="K1"),
                            parse_error=None,
                            used_fallback=False,
                            llm_response_present=True,
                            error_kind=None,
                        ),
                        ExtractionResult(
                            record=_argument_record(chunk_id="legacy_chunk_2"),
                            parse_error=None,
                            used_fallback=False,
                            llm_response_present=True,
                            error_kind=None,
                        ),
                    ],
                ),
                patch(
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
                ),
                patch("src.pipeline.synthesize_compendium", return_value=("compendium::global", 0)),
            ):
                process_book("books/sample_book.txt", verbose=False, profile="argumentative")

            self.assertTrue((Path(tmpdir) / "sample_book_argument_chunks.jsonl").exists())
            self.assertTrue((Path(tmpdir) / "sample_book_argument_audit.jsonl").exists())
            self.assertTrue((Path(tmpdir) / "sample_book_argument_map.json").exists())
            self.assertFalse((Path(tmpdir) / "sample_book_knowledge_chunks.jsonl").exists())

            audit_lines = [
                json.loads(line)
                for line in (Path(tmpdir) / "sample_book_argument_audit.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(audit_lines[0]["decision"], "ok")
            self.assertEqual(audit_lines[1]["decision"], "empty_legitimate")

    def test_profiles_do_not_share_checkpoint_manifests(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            common_patches = (
                patch("src.pipeline.OUTPUT_FOLDER", tmpdir),
                patch("src.pipeline.STRUCTURE_PASS_ENABLED", False),
                patch("src.pipeline.load_book", return_value="source text"),
                patch("src.pipeline.split_into_chunks", return_value=["c1"]),
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
            )
            with common_patches[0], common_patches[1], common_patches[2], common_patches[3], common_patches[4], common_patches[5]:
                with patch("src.pipeline.summarize_chunk", return_value="summary::c1"):
                    process_book("books/sample_book.txt", verbose=False, profile="manual")
            with common_patches[0], common_patches[1], common_patches[2], common_patches[3], common_patches[4], common_patches[5]:
                with patch(
                    "src.pipeline.extract_argument_chunk",
                    return_value=ExtractionResult(
                        record=_argument_record(chunk_id="legacy_chunk_1", thesis="T1", evidence="E1"),
                        parse_error=None,
                        used_fallback=False,
                        llm_response_present=True,
                        error_kind=None,
                    ),
                ):
                    process_book("books/sample_book.txt", verbose=False, profile="argumentative")

            summary_manifests = list((Path(tmpdir) / ".checkpoints").glob("**/summary/**/manifest.json"))
            argumentative_manifests = list((Path(tmpdir) / ".checkpoints").glob("**/argumentative/**/manifest.json"))
            self.assertTrue(summary_manifests)
            self.assertTrue(argumentative_manifests)
            self.assertNotEqual(summary_manifests[0].parent.parent, argumentative_manifests[0].parent.parent)

    def test_mixed_chunk_keeps_argument_signal_without_overfilling_fields(self) -> None:
        record = _argument_record(
            chunk_id="legacy_chunk_1",
            thesis="The archive is an instrument of state formation.",
            evidence="The author cites police files from 1920.",
            key_term="archive",
        )
        self.assertEqual(record.claims, [])
        self.assertEqual(record.methods, [])
        self.assertTrue(record.theses)
        self.assertTrue(record.evidence)


if __name__ == "__main__":
    unittest.main()
