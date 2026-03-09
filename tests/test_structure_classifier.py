from __future__ import annotations

import unittest
from unittest.mock import patch

from src.structure_classifier import classify_headings
from src.structure_types import HeadingCandidate


class StructureClassifierTests(unittest.TestCase):
    def test_classification_is_index_based_and_limited_by_top_scores(self) -> None:
        headings: list[HeadingCandidate] = [
            {
                "index": 0,
                "id": "heading_0",
                "text": "CHAPTER 1 INTRODUCTION",
                "start_char": 0,
                "end_char": 22,
                "page": None,
                "score": 0.95,
                "pattern": "chapter_pattern",
            },
            {
                "index": 1,
                "id": "heading_1",
                "text": "PART II",
                "start_char": 23,
                "end_char": 30,
                "page": None,
                "score": 0.9,
                "pattern": "part_pattern",
            },
            {
                "index": 2,
                "id": "heading_2",
                "text": "small heading",
                "start_char": 31,
                "end_char": 44,
                "page": None,
                "score": 0.2,
                "pattern": "title_case_short",
            },
        ]
        llm_output = (
            '[{"index":0,"type":"chapter","confidence":0.9},'
            '{"index":2,"type":"section","confidence":0.7}]'
        )
        with patch("src.structure_classifier.ask_llm", return_value=llm_output):
            classified, selected_indexes = classify_headings(
                headings,
                max_headings_for_llm=2,
                use_llm=True,
            )

        self.assertEqual(selected_indexes, {0, 1})
        self.assertIn(0, classified)
        self.assertIn(2, classified)
        self.assertEqual(classified[0]["type"], "chapter")
        self.assertEqual(classified[2]["type"], "section")

    def test_use_llm_false_skips_remote_classification(self) -> None:
        headings: list[HeadingCandidate] = [
            {
                "index": 0,
                "id": "heading_0",
                "text": "CHAPTER 1 INTRODUCTION",
                "start_char": 0,
                "end_char": 22,
                "page": None,
                "score": 0.95,
                "pattern": "chapter_pattern",
            }
        ]
        classified, selected_indexes = classify_headings(
            headings,
            max_headings_for_llm=200,
            use_llm=False,
        )
        self.assertIn(0, classified)
        self.assertEqual(classified[0]["type"], "chapter")
        self.assertEqual(selected_indexes, {0})

    def test_title_case_short_promotes_to_section_not_chapter(self) -> None:
        headings: list[HeadingCandidate] = [
            {
                "index": 0,
                "id": "heading_0",
                "text": "Final Summary",
                "start_char": 0,
                "end_char": 13,
                "page": None,
                "score": 0.6,
                "pattern": "title_case_short",
            }
        ]
        classified, _selected_indexes = classify_headings(
            headings,
            max_headings_for_llm=200,
            use_llm=False,
        )
        self.assertIn(0, classified)
        self.assertEqual(classified[0]["type"], "section")
        self.assertNotEqual(classified[0]["type"], "chapter")

    def test_ambiguous_single_word_title_case_stays_unclassified(self) -> None:
        headings: list[HeadingCandidate] = [
            {
                "index": 0,
                "id": "heading_0",
                "text": "Friends",
                "start_char": 0,
                "end_char": 7,
                "page": None,
                "score": 0.6,
                "pattern": "title_case_short",
            }
        ]
        classified, _selected_indexes = classify_headings(
            headings,
            max_headings_for_llm=200,
            use_llm=False,
        )
        self.assertNotIn(0, classified)

    def test_reference_like_title_case_is_never_promoted_intrinsically(self) -> None:
        headings: list[HeadingCandidate] = [
            {
                "index": 0,
                "id": "heading_0",
                "text": "Astronomica 2.939-46, 2.829-35",
                "start_char": 0,
                "end_char": 30,
                "page": None,
                "score": 0.6,
                "pattern": "title_case_short",
            },
            {
                "index": 1,
                "id": "heading_1",
                "text": "Delineator (1910)",
                "start_char": 31,
                "end_char": 48,
                "page": None,
                "score": 0.6,
                "pattern": "title_case_short",
            },
        ]
        classified, _selected_indexes = classify_headings(
            headings,
            max_headings_for_llm=200,
            use_llm=False,
        )
        self.assertNotIn(0, classified)
        self.assertNotIn(1, classified)


if __name__ == "__main__":
    unittest.main()
