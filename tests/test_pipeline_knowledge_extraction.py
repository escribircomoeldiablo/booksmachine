from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from src.knowledge_extractor import ExtractionResult
from src.knowledge_schema import ChunkKnowledgeV1, SectionRef
from src.pipeline import _is_non_glossarial_definition, process_book


def _record(chunk_id: str, source_fingerprint: str) -> ChunkKnowledgeV1:
    return ChunkKnowledgeV1(
        schema_version="1.0.0",
        chunk_id=chunk_id,
        source_fingerprint=source_fingerprint,
        section_refs=[SectionRef(label="Intro", type="chapter", start_char=0, end_char=100)],
        concepts=["C1"],
        definitions=["D1"],
        technical_rules=["R1"],
        procedures=["P1"],
        terminology=["T1"],
        relationships=[],
        examples=[],
        ambiguities=[],
    )


def _record_concept_only(chunk_id: str, source_fingerprint: str) -> ChunkKnowledgeV1:
    return ChunkKnowledgeV1(
        schema_version="1.0.0",
        chunk_id=chunk_id,
        source_fingerprint=source_fingerprint,
        section_refs=[SectionRef(label="Intro", type="chapter", start_char=0, end_char=100)],
        concepts=["C1", "C2", "C3"],
        definitions=[],
        technical_rules=[],
        procedures=[],
        terminology=["T1", "T2"],
        relationships=[],
        examples=[],
        ambiguities=["amb1"],
    )


def _record_editorial_rule_only(chunk_id: str, source_fingerprint: str) -> ChunkKnowledgeV1:
    return ChunkKnowledgeV1(
        schema_version="1.0.0",
        chunk_id=chunk_id,
        source_fingerprint=source_fingerprint,
        section_refs=[SectionRef(label="Intro", type="chapter", start_char=0, end_char=100)],
        concepts=["C1"],
        definitions=[],
        technical_rules=["All rights reserved."],
        procedures=[],
        terminology=[],
        relationships=[],
        examples=[],
        ambiguities=[],
    )


class PipelineKnowledgeExtractionTests(unittest.TestCase):
    def test_non_glossarial_definition_requires_operational_signal(self) -> None:
        self.assertFalse(_is_non_glossarial_definition("Ascendant: rising sign of the chart."))
        self.assertTrue(
            _is_non_glossarial_definition(
                "House strength: when a planet is angular, its effects are stronger."
            )
        )

    def test_pipeline_old_mode_remains_intact(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.pipeline.OUTPUT_FOLDER", tmpdir), patch("src.pipeline.KNOWLEDGE_EXTRACTION_ENABLED", False):
                with patch("src.pipeline.load_book", return_value="source text"):
                    with patch("src.pipeline.split_into_chunks", return_value=["c1"]):
                        with patch("src.pipeline.summarize_chunk", return_value="summary::c1") as summarize_mock:
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
                            ), patch("src.pipeline.synthesize_compendium", return_value=("compendium::global", 0)):
                                process_book("books/sample_book.txt", verbose=False)

            self.assertEqual(summarize_mock.call_count, 1)
            self.assertTrue((Path(tmpdir) / "sample_book_summary_chunks.txt").exists())
            self.assertFalse((Path(tmpdir) / "sample_book_knowledge_chunks.jsonl").exists())

    def test_pipeline_knowledge_mode_generates_jsonl_and_invariants(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.pipeline.OUTPUT_FOLDER", tmpdir), patch("src.pipeline.KNOWLEDGE_EXTRACTION_ENABLED", True):
                with patch("src.pipeline.load_book", return_value="source text"):
                    with patch("src.pipeline.split_into_chunks", return_value=["c1", "c2"]):
                        with patch(
                            "src.pipeline.extract_chunk_knowledge",
                            side_effect=lambda **kwargs: ExtractionResult(
                                record=_record(kwargs["chunk_id"], kwargs["source_fingerprint"]),
                                parse_error=None,
                                used_fallback=False,
                            ),
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
                            ), patch("src.pipeline.synthesize_compendium", return_value=("compendium::global", 0)):
                                process_book("books/sample_book.txt", verbose=False)

            jsonl_path = Path(tmpdir) / "sample_book_knowledge_chunks.jsonl"
            audit_path = Path(tmpdir) / "sample_book_knowledge_audit.jsonl"
            self.assertTrue(jsonl_path.exists())
            self.assertTrue(audit_path.exists())
            lines = [line for line in jsonl_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(lines), 2)
            for line in lines:
                record = json.loads(line)
                self.assertIn("chunk_id", record)
                self.assertIn("source_fingerprint", record)
                self.assertIn("section_refs", record)
                self.assertEqual(record["schema_version"], "2.0.0")
                self.assertIn("concepts", record)
                self.assertIn("technical_rules", record)
            audit_lines = [line for line in audit_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(len(audit_lines), 2)

    def test_pipeline_passes_knowledge_language_to_extractor_and_persists_it_in_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                patch("src.pipeline.OUTPUT_FOLDER", tmpdir),
                patch("src.pipeline.KNOWLEDGE_EXTRACTION_ENABLED", True),
                patch("src.pipeline.KNOWLEDGE_PRECHECK_ENABLED", False),
            ):
                with patch("src.pipeline.load_book", return_value="source text"):
                    with patch("src.pipeline.split_into_chunks", return_value=["c1"]):
                        with patch(
                            "src.pipeline.extract_chunk_knowledge",
                            return_value=ExtractionResult(
                                record=_record("legacy_chunk_1", "book_hash"),
                                parse_error=None,
                                used_fallback=False,
                            ),
                        ) as extract_mock:
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
                            ), patch("src.pipeline.synthesize_compendium", return_value=("compendium::global", 0)):
                                process_book(
                                    "books/sample_book.txt",
                                    verbose=False,
                                    output_language="es",
                                    knowledge_language="original",
                                )

            self.assertEqual(extract_mock.call_args.kwargs["knowledge_language"], "original")
            manifest_path = next((Path(tmpdir) / ".checkpoints").glob("**/knowledge/**/manifest.json"))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["output_language"], "es")
            self.assertEqual(manifest["knowledge_language"], "original")

    def test_checkpoint_namespaces_are_separated_by_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.pipeline.OUTPUT_FOLDER", tmpdir):
                with patch("src.pipeline.load_book", return_value="source text"):
                    with patch("src.pipeline.split_into_chunks", return_value=["c1"]):
                        with patch("src.pipeline.KNOWLEDGE_EXTRACTION_ENABLED", False):
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
                                ), patch("src.pipeline.synthesize_compendium", return_value=("compendium::global", 0)):
                                    process_book("books/sample_book.txt", verbose=False)

                        with patch("src.pipeline.KNOWLEDGE_EXTRACTION_ENABLED", True):
                            with patch(
                                "src.pipeline.extract_chunk_knowledge",
                                return_value=ExtractionResult(
                                    record=_record("legacy_chunk_1", "book_hash"),
                                    parse_error=None,
                                    used_fallback=False,
                                ),
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
                                ), patch("src.pipeline.synthesize_compendium", return_value=("compendium::global", 0)):
                                    process_book("books/sample_book.txt", verbose=False)

            summary_manifests = list((Path(tmpdir) / ".checkpoints").glob("**/summary/**/manifest.json"))
            knowledge_manifests = list((Path(tmpdir) / ".checkpoints").glob("**/knowledge/**/manifest.json"))
            self.assertTrue(summary_manifests)
            self.assertTrue(knowledge_manifests)

    def test_knowledge_metric_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.pipeline.OUTPUT_FOLDER", tmpdir), patch("src.pipeline.KNOWLEDGE_EXTRACTION_ENABLED", True):
                with patch("src.pipeline.load_book", return_value="source text"):
                    with patch("src.pipeline.split_into_chunks", return_value=["c1"]):
                        with patch(
                            "src.pipeline.extract_chunk_knowledge",
                            return_value=ExtractionResult(
                                record=_record("legacy_chunk_1", "book_hash"),
                                parse_error=None,
                                used_fallback=False,
                            ),
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
                            ), patch("src.pipeline.synthesize_compendium", return_value=("compendium::global", 0)):
                                capture = io.StringIO()
                                with redirect_stdout(capture):
                                    process_book("books/sample_book.txt", verbose=True)

            self.assertIn("knowledge_avg_items_per_chunk", capture.getvalue())

    def test_policy_degrades_concept_heavy_doctrine_light_and_persists_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                patch("src.pipeline.OUTPUT_FOLDER", tmpdir),
                patch("src.pipeline.KNOWLEDGE_EXTRACTION_ENABLED", True),
                patch("src.pipeline.KNOWLEDGE_DECISION_POLICY_ENABLE", True),
                patch("src.pipeline.KNOWLEDGE_CLAMP_ENABLE", True),
                patch("src.pipeline.KNOWLEDGE_PRECHECK_ENABLED", False),
            ):
                with patch("src.pipeline.load_book", return_value="source text"):
                    with patch("src.pipeline.split_into_chunks", return_value=["c1"]):
                        with patch(
                            "src.pipeline.extract_chunk_knowledge",
                            return_value=ExtractionResult(
                                record=_record_concept_only("legacy_chunk_1", "book_hash"),
                                parse_error=None,
                                used_fallback=False,
                            ),
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
                            ), patch("src.pipeline.synthesize_compendium", return_value=("compendium::global", 0)):
                                process_book("books/sample_book.txt", verbose=False)

            audit_path = Path(tmpdir) / "sample_book_knowledge_audit.jsonl"
            audit = json.loads(audit_path.read_text(encoding="utf-8").strip())
            self.assertEqual(audit["decision"], "extract_degraded")
            self.assertEqual(audit["doctrinal_support_level"], "none")
            self.assertIn("concept_heavy_no_operations", audit["policy_reason_codes"])
            self.assertIn("insufficient_operational_support", audit["policy_reason_codes"])
            self.assertTrue(audit["weak_support_pattern"])

            manifest_path = next((Path(tmpdir) / ".checkpoints").glob("**/knowledge/**/manifest.json"))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["knowledge_decision_state_distribution"]["extract_degraded"], 1)
            self.assertGreater(manifest["concept_heavy_doctrine_light_ratio"], 0.0)
            self.assertIn("extract_degraded", manifest["knowledge_avg_items_per_decision_state"])
            self.assertIn("extract_strong_count", manifest)
            self.assertIn("extract_minimal_count", manifest)
            self.assertIn("concept_heavy_degraded_count", manifest)
            self.assertIn("knowledge_avg_fields_per_decision_state", manifest)

    def test_doctrinal_support_level_is_computed_after_semantic_filter(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                patch("src.pipeline.OUTPUT_FOLDER", tmpdir),
                patch("src.pipeline.KNOWLEDGE_EXTRACTION_ENABLED", True),
                patch("src.pipeline.KNOWLEDGE_DECISION_POLICY_ENABLE", True),
                patch("src.pipeline.KNOWLEDGE_CLAMP_ENABLE", False),
                patch("src.pipeline.KNOWLEDGE_PRECHECK_ENABLED", False),
                patch("src.pipeline.KNOWLEDGE_FILTER_EDITORIAL_ENABLE", True),
            ):
                with patch("src.pipeline.load_book", return_value="source text"):
                    with patch("src.pipeline.split_into_chunks", return_value=["c1"]):
                        with patch(
                            "src.pipeline.extract_chunk_knowledge",
                            return_value=ExtractionResult(
                                record=_record_editorial_rule_only("legacy_chunk_1", "book_hash"),
                                parse_error=None,
                                used_fallback=False,
                            ),
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
                            ), patch("src.pipeline.synthesize_compendium", return_value=("compendium::global", 0)):
                                process_book("books/sample_book.txt", verbose=False)

            audit_path = Path(tmpdir) / "sample_book_knowledge_audit.jsonl"
            audit = json.loads(audit_path.read_text(encoding="utf-8").strip())
            self.assertEqual(audit["doctrinal_support_level"], "none")
            self.assertEqual(audit["decision"], "extract_degraded")
            self.assertIn("semantic_payload_empty_or_near_empty", audit["policy_reason_codes"])
            self.assertIn("insufficient_operational_support", audit["policy_reason_codes"])
            self.assertIn("clear_editorial_technical_rules", audit["semantic_filter_actions"])


if __name__ == "__main__":
    unittest.main()
