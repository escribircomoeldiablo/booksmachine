"""Load source book text from plain text or PDF files."""

from __future__ import annotations

from pathlib import Path


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
    return "\n".join(pages).strip()


def load_book(path: str) -> str:
    """Load a book from a supported file extension."""
    extension = Path(path).suffix.lower()

    if extension == ".txt":
        return load_text_file(path)
    if extension == ".pdf":
        return load_pdf_file(path)

    raise ValueError(f"Unsupported file extension: {extension or '<none>'}")
