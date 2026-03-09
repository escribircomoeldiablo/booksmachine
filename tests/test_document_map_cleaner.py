from __future__ import annotations

import unittest

from src.document_map_cleaner import clean_document_map, clean_document_map_sidecar_payload


class DocumentMapCleanerTests(unittest.TestCase):
    def test_cleaner_merges_letter_marker_and_fills_pages(self) -> None:
        document_map = {
            "version": "1.0",
            "generator": "structure_pass_v1",
            "text_hash": "x" * 64,
            "source_fingerprint": "books/sample_book.txt",
            "normalized_text_length": 34,
            "headings": [],
            "sections": [
                {
                    "section_index": 0,
                    "id": "section_0",
                    "label": "A",
                    "type": "unknown",
                    "start_page": 10,
                    "end_page": 10,
                    "start_char": 0,
                    "end_char": 2,
                    "confidence": 0.0,
                },
                {
                    "section_index": 1,
                    "id": "section_2",
                    "label": "Aristotle 17, 42",
                    "type": "unknown",
                    "start_page": 10,
                    "end_page": None,
                    "start_char": 2,
                    "end_char": 10,
                    "confidence": 0.0,
                },
                {
                    "section_index": 2,
                    "id": "section_10",
                    "label": "CHAPTER 1 INTRODUCTION",
                    "type": "chapter",
                    "start_page": 11,
                    "end_page": 11,
                    "start_char": 10,
                    "end_char": 34,
                    "confidence": 0.9,
                },
            ],
            "stats": {
                "heading_candidates": 3,
                "classified_headings": 1,
                "sections_generated": 3,
                "unknown_sections": 2,
            },
        }

        cleaned = clean_document_map(document_map)
        self.assertEqual(len(cleaned["sections"]), 2)
        self.assertEqual(cleaned["sections"][0]["start_char"], 0)
        self.assertEqual(cleaned["sections"][0]["label"], "Aristotle 17, 42")
        self.assertEqual(cleaned["sections"][0]["end_page"], 11)
        self.assertEqual(cleaned["sections"][0]["id"], "section_0")
        self.assertEqual(cleaned["sections"][1]["section_index"], 1)
        self.assertEqual(cleaned["stats"]["sections_generated"], 2)

    def test_clean_sidecar_adds_postprocess_metadata(self) -> None:
        payload = {
            "metadata": {"pipeline_version": "booksmachine_0.9"},
            "document_map": {
                "version": "1.0",
                "generator": "structure_pass_v1",
                "text_hash": "y" * 64,
                "source_fingerprint": "books/sample_book.txt",
                "normalized_text_length": 3,
                "headings": [],
                "sections": [
                    {
                        "section_index": 0,
                        "id": "section_0",
                        "label": "unknown",
                        "type": "unknown",
                        "start_page": 1,
                        "end_page": 1,
                        "start_char": 0,
                        "end_char": 3,
                        "confidence": 0.0,
                    }
                ],
                "stats": {
                    "heading_candidates": 0,
                    "classified_headings": 0,
                    "sections_generated": 1,
                    "unknown_sections": 1,
                },
            },
        }
        cleaned = clean_document_map_sidecar_payload(payload)
        self.assertEqual(cleaned["metadata"]["postprocess"], "document_map_cleaner_v1")


if __name__ == "__main__":
    unittest.main()
