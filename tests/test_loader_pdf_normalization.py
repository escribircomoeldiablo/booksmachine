from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from src.loader import load_book, load_pdf_file, load_text_file
from src.pdf_cleaning import RULE_VERSION, assemble_clean_text, clean_pdf_pages
from src.pdf_diagnostics import analyze_extraction
from src.pdf_extract import extract_pdf_pages


class _FakePage:
    def __init__(self, text: str) -> None:
        self._text = text

    def extract_text(self) -> str:
        return self._text


class _FakePdfReader:
    def __init__(self, _: str) -> None:
        self.pages = [
            _FakePage(
                "HEADER TITLE\n"
                "The proce-\n"
                "dure appears here.\n"
                "Meaning\n"
                "By line break must remain separated.\n"
                "1\n"
            ),
            _FakePage(
                "HEADER TITLE\n"
                "The proce- \n"
                "dure appears here too.\n"
                "Another line\n"
                "continued in lowercase\n"
                "2\n"
            ),
            _FakePage("HEADER TITLE\nBody text.\n3\n"),
            _FakePage("HEADER TITLE\nBody text.\n4\n"),
            _FakePage("HEADER TITLE\nBody text.\n5\n"),
        ]


class _UnusablePdfReader:
    def __init__(self, _: str) -> None:
        self.pages = [_FakePage("   \n\n\t\n") for _ in range(3)]


class LoaderPdfNormalizationTests(unittest.TestCase):
    def test_extract_pdf_pages_keeps_page_structure(self) -> None:
        fake_pypdf = types.SimpleNamespace(PdfReader=_FakePdfReader)
        with patch.dict(sys.modules, {"pypdf": fake_pypdf}):
            pages = extract_pdf_pages("books/any.pdf")

        self.assertEqual(len(pages), 5)
        self.assertEqual(pages[0].page_index, 1)
        self.assertIn("HEADER TITLE", pages[0].raw_text)

    def test_clean_pdf_pages_dehyphenates_with_optional_whitespace(self) -> None:
        fake_pypdf = types.SimpleNamespace(PdfReader=_FakePdfReader)
        with patch.dict(sys.modules, {"pypdf": fake_pypdf}):
            raw_pages = extract_pdf_pages("books/any.pdf")

        clean_pages = clean_pdf_pages(raw_pages)
        clean_text = assemble_clean_text(clean_pages)

        self.assertIn("procedure appears here.", clean_text)
        self.assertIn("procedure appears here too.", clean_text)

    def test_cleaning_does_not_apply_risky_global_letter_newline_join(self) -> None:
        fake_pypdf = types.SimpleNamespace(PdfReader=_FakePdfReader)
        with patch.dict(sys.modules, {"pypdf": fake_pypdf}):
            text = load_pdf_file("books/any.pdf")

        self.assertNotIn("MeaningBy", text)
        self.assertIn("Meaning\nBy", text)

    def test_header_and_page_numbers_are_removed_conservatively(self) -> None:
        fake_pypdf = types.SimpleNamespace(PdfReader=_FakePdfReader)
        with patch.dict(sys.modules, {"pypdf": fake_pypdf}):
            raw_pages = extract_pdf_pages("books/any.pdf")

        clean_pages = clean_pdf_pages(raw_pages)
        diagnostics = analyze_extraction(raw_pages, clean_pages)
        text = assemble_clean_text(clean_pages)

        self.assertNotIn("\n1\n", f"\n{text}\n")
        self.assertNotIn("\n2\n", f"\n{text}\n")
        self.assertNotIn("HEADER TITLE", text)
        self.assertGreaterEqual(diagnostics.removed_header_lines, 5)
        self.assertGreaterEqual(diagnostics.removed_page_numbers, 4)

    def test_diagnostics_contains_rule_version(self) -> None:
        fake_pypdf = types.SimpleNamespace(PdfReader=_FakePdfReader)
        with patch.dict(sys.modules, {"pypdf": fake_pypdf}):
            raw_pages = extract_pdf_pages("books/any.pdf")
        clean_pages = clean_pdf_pages(raw_pages)
        diagnostics = analyze_extraction(raw_pages, clean_pages)

        self.assertEqual(diagnostics.rule_version, RULE_VERSION)
        self.assertTrue(diagnostics.is_usable)

    def test_unusable_pdf_maps_to_empty_text_for_pipeline_compatibility(self) -> None:
        fake_pypdf = types.SimpleNamespace(PdfReader=_UnusablePdfReader)
        with patch.dict(sys.modules, {"pypdf": fake_pypdf}):
            text = load_pdf_file("books/any.pdf")

        self.assertEqual(text, "")

    def test_load_text_file_is_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "input.txt"
            content = "A  line\nwith\tspacing\n\nand paragraph."
            file_path.write_text(content, encoding="utf-8")
            loaded = load_text_file(str(file_path))
        self.assertEqual(loaded, content)

    def test_load_book_txt_path_still_routes_to_text_loader(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "book.txt"
            file_path.write_text("sample text", encoding="utf-8")
            loaded = load_book(str(file_path))
        self.assertEqual(loaded, "sample text")


if __name__ == "__main__":
    unittest.main()
