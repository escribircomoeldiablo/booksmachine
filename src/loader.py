"""Load source book text from plain text or PDF files."""

from __future__ import annotations

from pathlib import Path
import re


def _normalize_pdf_text(raw_text: str) -> str:
    """Normalize common PDF layout artifacts conservatively for downstream chunking."""
    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")

    # Join words split by visual line breaks when both sides are alphabetic.
    text = re.sub(r"([A-Za-z])\n([A-Za-z])", r"\1\2", text)

    # Preserve paragraph boundaries while flattening intra-paragraph line breaks.
    text = re.sub(r"\n{3,}", "\n\n", text)
    paragraph_marker = "<<PDF_PARA>>"
    text = text.replace("\n\n", paragraph_marker)
    text = text.replace("\n", " ")

    # Collapse horizontal whitespace noise from extraction.
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = text.replace(paragraph_marker, "\n\n")
    text = re.sub(r" *\n\n *", "\n\n", text)
    return text.strip()


def load_text_file(path: str) -> str:
    """Load UTF-8 text content from a .txt file."""
    file_path = Path(path)
    try:
        return file_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Text file not found: {file_path}") from exc


def load_pdf_file(path: str) -> str:
    """Extract and return text content from a PDF file."""
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

    pages: list[str] = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    raw_text = "\n".join(pages).strip()
    return _normalize_pdf_text(raw_text)


def load_book(path: str) -> str:
    """Load a book from a supported file extension."""
    extension = Path(path).suffix.lower()

    if extension == ".txt":
        return load_text_file(path)
    if extension == ".pdf":
        return load_pdf_file(path)

    raise ValueError(f"Unsupported file extension: {extension or '<none>'}")
