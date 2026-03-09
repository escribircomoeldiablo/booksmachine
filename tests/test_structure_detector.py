from __future__ import annotations

import unittest

from src.structure_detector import detect_headings_and_segments


class StructureDetectorTests(unittest.TestCase):
    def test_ignores_index_entries_while_keeping_real_headings(self) -> None:
        text = (
            "INDEX\n"
            "W\n"
            "Z\n"
            "Walter, Marie-Therese 949\n"
            "X\n"
            "Xenocrates 784\n\n"
            "CHAPTER 1 INTRODUCTION\n"
            "Body text.\n"
        )
        headings, _segments = detect_headings_and_segments(text, min_heading_score=0.55)
        heading_texts = {item["text"] for item in headings}

        self.assertIn("INDEX", heading_texts)
        self.assertIn("CHAPTER 1 INTRODUCTION", heading_texts)
        self.assertNotIn("W", heading_texts)
        self.assertNotIn("X", heading_texts)
        self.assertNotIn("Z", heading_texts)
        self.assertNotIn("Walter, Marie-Therese 949", heading_texts)
        self.assertNotIn("Xenocrates 784", heading_texts)

    def test_ignores_index_entry_with_part_substring_in_name(self) -> None:
        text = (
            "INDEX\n"
            "Partridge, John 17\n"
            "CHAPTER 2 PRACTICE\n"
            "Body text.\n"
        )
        headings, _segments = detect_headings_and_segments(text, min_heading_score=0.55)
        heading_texts = {item["text"] for item in headings}

        self.assertIn("INDEX", heading_texts)
        self.assertIn("CHAPTER 2 PRACTICE", heading_texts)
        self.assertNotIn("Partridge, John 17", heading_texts)

    def test_ignores_table_of_contents_like_line(self) -> None:
        text = (
            "PART SEVEN: DOWN TO EARTH 595 61. DOWN TO EARTH 597\n"
            "Chapter 2.............................. 61\n"
            "CHAPTER 1 INTRODUCTION\n"
            "APPENDIX A TABLES\n"
            "Body text.\n"
        )
        headings, _segments = detect_headings_and_segments(text, min_heading_score=0.55)
        heading_texts = {item["text"] for item in headings}

        self.assertNotIn("PART SEVEN: DOWN TO EARTH 595 61. DOWN TO EARTH 597", heading_texts)
        self.assertNotIn("Chapter 2.............................. 61", heading_texts)
        self.assertIn("CHAPTER 1 INTRODUCTION", heading_texts)
        self.assertIn("APPENDIX A TABLES", heading_texts)


if __name__ == "__main__":
    unittest.main()
