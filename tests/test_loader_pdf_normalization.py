from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from src.loader import _normalize_pdf_text, load_book, load_pdf_file, load_text_file


class _FakePage:
    def __init__(self, text: str) -> None:
        self._text = text

    def extract_text(self) -> str:
        return self._text


class _FakePdfReader:
    def __init__(self, _: str) -> None:
        self.pages = [
            _FakePage("The com\nmittees reviewed the proce\ndure.\n"),
            _FakePage("Ex\naltation appears here.\n\nNew paragraph line.\n"),
        ]


class LoaderPdfNormalizationTests(unittest.TestCase):
    def test_normalize_pdf_text_repairs_line_wrapped_words(self) -> None:
        raw = "The com\nmittees reviewed the proce\ndure and Ex\naltation."
        normalized = _normalize_pdf_text(raw)
        self.assertIn("committees", normalized)
        self.assertIn("procedure", normalized)
        self.assertIn("Exaltation", normalized)

    def test_normalize_pdf_text_preserves_paragraph_breaks(self) -> None:
        raw = "Line one.\nLine two.\n\nParagraph two.\nStill two."
        normalized = _normalize_pdf_text(raw)
        self.assertEqual(normalized.count("\n\n"), 1)
        self.assertIn("Line one. Line two.", normalized)
        self.assertIn("Paragraph two. Still two.", normalized)

    def test_load_pdf_file_applies_normalization(self) -> None:
        fake_pypdf = types.SimpleNamespace(PdfReader=_FakePdfReader)
        with patch.dict(sys.modules, {"pypdf": fake_pypdf}):
            text = load_pdf_file("books/any.pdf")

        self.assertIn("committees", text)
        self.assertIn("procedure", text)
        self.assertIn("Exaltation", text)
        self.assertIn("\n\n", text)

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
