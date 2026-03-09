"""Load source book text from plain text or PDF files."""

from __future__ import annotations

import os
from pathlib import Path

from .config import OUTPUT_FOLDER
from .document_types import BookDocument
from .pdf_cleaning import assemble_clean_text, clean_pdf_pages
from .pdf_diagnostics import analyze_extraction, write_extraction_report
from .pdf_extract import extract_pdf_pages
from .structure_types import PageUnit


class UnusablePdfTextError(RuntimeError):
    """Raised internally when extracted PDF text is not usable."""


def _diagnostics_enabled() -> bool:
    value = os.getenv("PDF_EXTRACTION_DIAGNOSTICS", "0").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _build_document_from_pdf(path: str) -> BookDocument:
    raw_pages = extract_pdf_pages(path)
    clean_pages = clean_pdf_pages(raw_pages)
    diagnostics = analyze_extraction(raw_pages, clean_pages)

    if _diagnostics_enabled():
        source_path = Path(path)
        report_path = Path(OUTPUT_FOLDER) / f"{source_path.stem}_extraction_report.json"
        write_extraction_report(diagnostics, report_path)

    if not diagnostics.is_usable:
        raise UnusablePdfTextError(diagnostics.unusable_reason or "unusable extracted content")

    return BookDocument(
        source_path=path,
        source_type="pdf",
        clean_text=assemble_clean_text(clean_pages),
        pages_raw=raw_pages,
        pages_clean=clean_pages,
        diagnostics=diagnostics,
    )


def load_text_file(path: str) -> str:
    """Load UTF-8 text content from a .txt file."""
    file_path = Path(path)
    try:
        return file_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Text file not found: {file_path}") from exc


def load_pdf_file(path: str) -> str:
    """Extract, clean, and return text content from a PDF file."""
    try:
        document = _build_document_from_pdf(path)
    except UnusablePdfTextError:
        # Keep pipeline external failure path stable by yielding empty text.
        return ""
    return document.clean_text


def load_book(path: str) -> str:
    """Load a book from a supported file extension."""
    return load_book_with_structure(path)[0]


def _build_page_units(document: BookDocument) -> list[PageUnit] | None:
    if document.pages_clean is None:
        return None
    units: list[PageUnit] = []
    cursor = 0
    for page in document.pages_clean:
        text = page.clean_text.strip()
        if not text:
            continue
        start = cursor
        end = start + len(text)
        units.append(PageUnit(page=page.page_index, start_char=start, end_char=end))
        cursor = end + 2
    return units


def load_book_with_structure(path: str) -> tuple[str, list[PageUnit] | None]:
    """Load a book and return clean text plus optional page units."""
    extension = Path(path).suffix.lower()

    if extension == ".txt":
        return load_text_file(path), None
    if extension == ".pdf":
        try:
            document = _build_document_from_pdf(path)
        except UnusablePdfTextError:
            return "", None
        return document.clean_text, _build_page_units(document)

    raise ValueError(f"Unsupported file extension: {extension or '<none>'}")
