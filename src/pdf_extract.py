"""PDF extraction primitives (no normalization)."""

from __future__ import annotations

from pathlib import Path

from .document_types import PdfPageRaw


def extract_pdf_pages(path: str) -> list[PdfPageRaw]:
    """Extract raw text from each PDF page in order."""
    file_path = Path(path)

    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "PDF support requires 'pypdf'. Install it with: pip install pypdf"
        ) from exc

    try:
        reader = PdfReader(str(file_path))
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"PDF file not found: {file_path}") from exc

    pages: list[PdfPageRaw] = []
    for page_index, page in enumerate(reader.pages, start=1):
        raw_text = page.extract_text() or ""
        pages.append(
            PdfPageRaw(
                page_index=page_index,
                raw_text=raw_text,
                raw_lines=raw_text.splitlines(),
            )
        )
    return pages
