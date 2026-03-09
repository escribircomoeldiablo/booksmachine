from __future__ import annotations

import unittest

from src.structure_pass import build_document_map, validate_document_map


class StructurePassTests(unittest.TestCase):
    def test_document_map_assigns_deterministic_ids_labels_and_section_indices(self) -> None:
        text = (
            "Preface text.\n\n"
            "CHAPTER 1 INTRODUCTION\n"
            "Body line one.\n\n"
            "APPENDIX A TABLES\n"
            "Extra data."
        )
        document_map = build_document_map(
            text,
            source_fingerprint="books/sample_book.txt",
            page_units=None,
            use_llm=False,
            max_section_size_chars=200000,
        )

        sections = document_map["sections"]
        self.assertGreaterEqual(len(sections), 2)
        self.assertEqual([section["section_index"] for section in sections], list(range(len(sections))))
        for section in sections:
            self.assertEqual(section["id"], f"section_{section['start_char']}")
            self.assertTrue(section["label"])

        # Unknown preface gap should keep explicit unknown label.
        self.assertEqual(sections[0]["label"], "unknown")
        self.assertEqual(document_map["stats"]["sections_generated"], len(sections))
        validate_document_map(document_map, max_section_size_chars=200000)

    def test_large_section_is_subdivided_with_stable_ids_and_indices(self) -> None:
        text = "a" * 25
        document_map = build_document_map(
            text,
            source_fingerprint="books/sample_book.txt",
            use_llm=False,
            max_section_size_chars=10,
        )

        sections = document_map["sections"]
        self.assertEqual(len(sections), 3)
        self.assertEqual([section["section_index"] for section in sections], [0, 1, 2])
        self.assertEqual([section["id"] for section in sections], ["section_0", "section_10", "section_20"])
        self.assertTrue(all(section["end_char"] - section["start_char"] <= 10 for section in sections))

    def test_validation_rejects_non_contiguous_section_index(self) -> None:
        text = "A short text."
        document_map = build_document_map(
            text,
            source_fingerprint="books/sample_book.txt",
            use_llm=False,
            max_section_size_chars=200000,
        )
        document_map["sections"][0]["section_index"] = 2

        with self.assertRaisesRegex(ValueError, "non-contiguous section_index"):
            validate_document_map(document_map, max_section_size_chars=200000)

    def test_page_assignment_handles_offsets_between_page_units(self) -> None:
        text = "AAA\n\nBBB"
        document_map = build_document_map(
            text,
            source_fingerprint="books/sample_book.txt",
            page_units=[
                {"page": 1, "start_char": 0, "end_char": 3},
                {"page": 2, "start_char": 5, "end_char": 8},
            ],
            use_llm=False,
            max_section_size_chars=200000,
        )
        sections = document_map["sections"]
        self.assertGreaterEqual(len(sections), 1)
        self.assertTrue(all(section["start_page"] is not None for section in sections))
        self.assertTrue(all(section["end_page"] is not None for section in sections))

    def test_contextual_refinement_promotes_ambiguous_title_case_to_section(self) -> None:
        text = (
            "CHAPTER 1 INTRODUCTION\n"
            "Body.\n\n"
            "Method\n"
            "Body.\n\n"
            "2. Timing\n"
            "Body.\n"
        )
        document_map = build_document_map(
            text,
            source_fingerprint="books/sample_book.txt",
            use_llm=False,
            max_section_size_chars=200000,
        )
        section_by_label = {section["label"]: section for section in document_map["sections"]}
        self.assertIn("Method", section_by_label)
        self.assertEqual(section_by_label["Method"]["type"], "section")

    def test_isolated_ambiguous_title_case_remains_unknown(self) -> None:
        text = (
            "Friends\n"
            "Body.\n\n"
            "More body.\n"
        )
        document_map = build_document_map(
            text,
            source_fingerprint="books/sample_book.txt",
            use_llm=False,
            max_section_size_chars=200000,
        )
        section_by_label = {section["label"]: section for section in document_map["sections"]}
        self.assertIn("Friends", section_by_label)
        self.assertEqual(section_by_label["Friends"]["type"], "unknown")

    def test_contextual_refinement_never_promotes_reference_like_title_case(self) -> None:
        text = (
            "CHAPTER 1 INTRODUCTION\n"
            "Body.\n\n"
            "Astronomica 2.939-46, 2.829-35\n"
            "Body.\n\n"
            "2. Timing\n"
            "Body.\n"
        )
        document_map = build_document_map(
            text,
            source_fingerprint="books/sample_book.txt",
            use_llm=False,
            max_section_size_chars=200000,
        )
        section_by_label = {section["label"]: section for section in document_map["sections"]}
        self.assertIn("Astronomica 2.939-46, 2.829-35", section_by_label)
        self.assertEqual(section_by_label["Astronomica 2.939-46, 2.829-35"]["type"], "unknown")


if __name__ == "__main__":
    unittest.main()
