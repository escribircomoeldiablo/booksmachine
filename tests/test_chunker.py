from __future__ import annotations

import unittest
from unittest.mock import patch

from src.chunker import split_into_chunks


class ChunkerTests(unittest.TestCase):
    def test_empty_text_returns_empty_list(self) -> None:
        self.assertEqual(split_into_chunks("   "), [])

    def test_text_shorter_than_chunk_size_returns_single_chunk(self) -> None:
        text = "short text"
        chunks = split_into_chunks(text, chunk_size=100, overlap=10)
        self.assertEqual(chunks, [text])

    def test_overlap_must_be_smaller_than_chunk_size(self) -> None:
        with self.assertRaisesRegex(ValueError, r"overlap must be smaller than chunk_size"):
            split_into_chunks("abcdef", chunk_size=10, overlap=10)

    def test_regression_case_terminates_without_empty_chunks(self) -> None:
        text = (
            "This is a small sample book.\n\n"
            "A pipeline transforms source text into meaningful structure.\n"
            "Chunking helps process long inputs safely. Summaries should extract concepts,\n"
            "definitions, principles, and important rules in a clear bullet format."
        )
        chunks = split_into_chunks(text, chunk_size=1800, overlap=200)
        self.assertGreater(len(chunks), 0)
        self.assertTrue(all(chunk.strip() for chunk in chunks))
        self.assertLessEqual(len(chunks), len(text))

    def test_overlap_is_preserved_on_fixed_windows(self) -> None:
        text = "abcdefghijklmnopqrstuvwxyz" * 20
        chunk_size = 50
        overlap = 10
        chunks = split_into_chunks(text, chunk_size=chunk_size, overlap=overlap)
        self.assertGreater(len(chunks), 1)
        for prev_chunk, next_chunk in zip(chunks, chunks[1:]):
            self.assertEqual(prev_chunk[-overlap:], next_chunk[:overlap])

    def test_overlap_near_chunk_size_minus_one_still_terminates(self) -> None:
        text = "0123456789" * 40
        chunks = split_into_chunks(text, chunk_size=20, overlap=19)
        self.assertGreater(len(chunks), 0)
        self.assertTrue(all(chunk.strip() for chunk in chunks))
        self.assertLessEqual(len(chunks), len(text))

    def test_tail_does_not_degrade_into_micro_chunks(self) -> None:
        text = ("alpha beta gamma delta epsilon zeta eta theta iota kappa " * 350).strip()
        chunks = split_into_chunks(text, chunk_size=1800, overlap=200)
        self.assertLess(len(chunks), 40)
        tiny_chunks = [chunk for chunk in chunks if len(chunk) <= 20]
        self.assertLessEqual(len(tiny_chunks), 1)

    def test_no_descending_tail_staircase(self) -> None:
        text = ("lorem ipsum dolor sit amet consectetur adipiscing elit " * 320).strip()
        chunks = split_into_chunks(text, chunk_size=1800, overlap=200)
        tail_lengths = [len(chunk) for chunk in chunks[-10:]]
        self.assertFalse(tail_lengths[-5:] == [5, 4, 3, 2, 1])

    def test_non_terminal_no_progress_condition_does_not_close_all_text(self) -> None:
        text = "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        with patch("src.chunker._find_split_point", return_value=10):
            chunks = split_into_chunks(text, chunk_size=40, overlap=39)
        self.assertGreater(len(chunks), 1)
        self.assertNotEqual(chunks[0], text.strip())

    def test_small_chunk_high_overlap_does_not_close_prematurely(self) -> None:
        text = ("0123456789" * 25).strip()
        chunks = split_into_chunks(text, chunk_size=20, overlap=19)
        self.assertGreater(len(chunks), 1)
        self.assertLess(len(chunks[0]), len(text))
        self.assertTrue(all(chunk.strip() for chunk in chunks))

    def test_terminal_window_closes_tail_in_single_stable_chunk(self) -> None:
        text = "x" * 55

        def fake_split_point(_: str, start: int, target_end: int) -> int:
            if target_end == 55:
                return 45
            if start == 0:
                return 50
            return target_end

        with patch("src.chunker._find_split_point", side_effect=fake_split_point):
            chunks = split_into_chunks(text, chunk_size=50, overlap=20)

        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[-1], text[30:].strip())


if __name__ == "__main__":
    unittest.main()
