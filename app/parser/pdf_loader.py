"""PDF loading and page rendering utilities."""
from __future__ import annotations

from pathlib import Path
from typing import Iterator

import fitz
from pdf2image import convert_from_path


class PDFProtectedError(RuntimeError):
    """Raised when PDF requires password."""


def iter_native_text(pdf_path: Path) -> Iterator[tuple[int, str]]:
    """Yield page number and extracted native text."""
    with fitz.open(pdf_path) as doc:
        if doc.needs_pass:
            raise PDFProtectedError("El PDF está protegido. Desbloquéalo antes de procesar.")
        for idx, page in enumerate(doc, start=1):
            yield idx, page.get_text("text") or ""


def detect_needs_ocr(pdf_path: Path, threshold: float = 50.0) -> bool:
    """Detect whether OCR is required based on native text density."""
    total_chars = 0
    pages = 0
    for _, text in iter_native_text(pdf_path):
        pages += 1
        total_chars += len(text.strip())
    avg_chars = (total_chars / pages) if pages else 0
    return avg_chars < threshold


def render_pdf_pages(pdf_path: Path, dpi: int, first_page: int | None = None, last_page: int | None = None):
    """Render PDF pages to PIL images."""
    return convert_from_path(
        str(pdf_path),
        dpi=dpi,
        fmt="png",
        first_page=first_page,
        last_page=last_page,
    )
