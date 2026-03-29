from __future__ import annotations

import logging
from pathlib import Path

from pdf2image import convert_from_path
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer

from .models import IngestResult

LOGGER = logging.getLogger(__name__)


class PDFExtractor:
    def __init__(self, render_dpi: int = 300, native_char_threshold: int = 120) -> None:
        self.render_dpi = render_dpi
        self.native_char_threshold = native_char_threshold

    def ingest(self, pdf_path: str | Path, image_dir: str | Path) -> IngestResult:
        pdf = Path(pdf_path).expanduser().resolve()
        if not pdf.exists() or pdf.suffix.lower() != ".pdf":
            raise FileNotFoundError(f"PDF inválido o inexistente: {pdf}")

        image_root = Path(image_dir).expanduser().resolve()
        image_root.mkdir(parents=True, exist_ok=True)

        native_pages: dict[int, str] = {}
        needs_ocr_pages: list[int] = []
        rendered_images: dict[int, Path] = {}

        for page_index, page_layout in enumerate(extract_pages(str(pdf)), start=1):
            text_parts: list[str] = []
            for element in page_layout:
                if isinstance(element, LTTextContainer):
                    text_parts.append(element.get_text())
            page_text = "\n".join(text_parts).strip()
            native_pages[page_index] = page_text
            if len(page_text) < self.native_char_threshold:
                needs_ocr_pages.append(page_index)

        if needs_ocr_pages:
            LOGGER.info("Rendering %s pages for OCR", len(needs_ocr_pages))
            images = convert_from_path(
                str(pdf),
                dpi=self.render_dpi,
                first_page=min(needs_ocr_pages),
                last_page=max(needs_ocr_pages),
                fmt="png",
            )
            page_range = list(range(min(needs_ocr_pages), max(needs_ocr_pages) + 1))
            for page_num, image in zip(page_range, images):
                if page_num not in needs_ocr_pages:
                    continue
                output_path = image_root / f"{pdf.stem}_p{page_num}.png"
                image.save(output_path)
                rendered_images[page_num] = output_path

        return IngestResult(
            pdf_path=pdf,
            native_pages=native_pages,
            needs_ocr_pages=needs_ocr_pages,
            rendered_images=rendered_images,
        )
