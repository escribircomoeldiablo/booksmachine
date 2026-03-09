from __future__ import annotations

import unittest

from src.chunker_structural import build_structural_chunks


class StructuralChunkerTests(unittest.TestCase):
    def test_assigns_deterministic_chunk_index_and_chunk_id(self) -> None:
        text = "A" * 40 + "\n\n" + "B" * 40 + "\n\n" + "C" * 40
        document_map = {
            "version": "1.0",
            "generator": "structure_pass_v1",
            "text_hash": "unused",
            "source_fingerprint": "books/sample_book.txt",
            "normalized_text_length": len(text),
            "sections": [
                {
                    "section_index": 0,
                    "id": "section_0",
                    "label": "S1",
                    "type": "chapter",
                    "start_page": 1,
                    "end_page": 1,
                    "start_char": 0,
                    "end_char": len(text),
                    "confidence": 1.0,
                }
            ],
            "headings": [],
            "stats": {
                "heading_candidates": 0,
                "classified_headings": 0,
                "sections_generated": 1,
                "unknown_sections": 0,
            },
        }

        chunk_set = build_structural_chunks(
            text,
            document_map,  # type: ignore[arg-type]
            target_size=45,
            min_size=10,
            split_window=30,
        )
        chunks = chunk_set["chunks"]
        self.assertGreaterEqual(len(chunks), 2)
        for expected_index, chunk in enumerate(chunks):
            self.assertEqual(chunk["chunk_index"], expected_index)
            self.assertEqual(
                chunk["chunk_id"],
                f"chunk_{expected_index}_{chunk['start_char']}_{chunk['end_char']}",
            )

    def test_never_crosses_section_boundaries(self) -> None:
        text = ("A " * 200).strip() + "\n\n" + ("B " * 200).strip()
        cut = len(("A " * 200).strip()) + 2
        document_map = {
            "version": "1.0",
            "generator": "structure_pass_v1",
            "text_hash": "unused",
            "source_fingerprint": "books/sample_book.txt",
            "normalized_text_length": len(text),
            "sections": [
                {
                    "section_index": 0,
                    "id": "section_0",
                    "label": "A",
                    "type": "chapter",
                    "start_page": 1,
                    "end_page": 1,
                    "start_char": 0,
                    "end_char": cut,
                    "confidence": 1.0,
                },
                {
                    "section_index": 1,
                    "id": f"section_{cut}",
                    "label": "B",
                    "type": "chapter",
                    "start_page": 2,
                    "end_page": 2,
                    "start_char": cut,
                    "end_char": len(text),
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
        }

        chunk_set = build_structural_chunks(
            text,
            document_map,  # type: ignore[arg-type]
            target_size=120,
            min_size=20,
            split_window=40,
        )
        for chunk in chunk_set["chunks"]:
            if chunk["section_index"] == 0:
                self.assertLessEqual(chunk["end_char"], cut)
            else:
                self.assertGreaterEqual(chunk["start_char"], cut)


if __name__ == "__main__":
    unittest.main()
