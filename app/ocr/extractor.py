"""Document extraction orchestration."""
from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pytesseract
from tqdm import tqdm

from app.config import load_config
from app.ocr.ocr_engine import OCREngine
from app.ocr.preprocessor import preprocess_image
from app.parser.pdf_loader import PDFProtectedError, detect_needs_ocr, iter_native_text, render_pdf_pages
from app.parser.text_cleaner import clean_text

BATCH_SIZE = 50


def _process_ocr_page(page_number: int, image, engine: OCREngine, raw_dump_dir: Path) -> dict:
    processed = preprocess_image(image)
    result = engine.recognize(processed)
    raw_path = raw_dump_dir / f"page_{page_number:04d}.txt"
    raw_path.write_text(result.text, encoding="utf-8")
    clean = clean_text(result.text)
    confidence = round(result.confidence, 2) if clean else 0.0
    if not clean:
        logging.warning("Texto OCR vacío en página %s", page_number)
    return {
        "page_number": page_number,
        "raw_text": result.text,
        "clean_text": clean,
        "ocr_confidence": confidence,
        "word_count": len(clean.split()),
        "boxes": result.boxes,
    }


def extract_document(pdf_path: Path, temp_dir: Path) -> dict:
    """Extract PDF text using native text first and OCR fallback."""
    cfg = load_config()
    dpi = cfg.getint("ocr", "dpi")
    language = cfg.get("ocr", "language")
    ocr_threshold = cfg.getfloat("ocr", "confidence_threshold")

    temp_dir.mkdir(parents=True, exist_ok=True)
    raw_dump_dir = temp_dir / f"{pdf_path.stem}_raw"
    raw_dump_dir.mkdir(parents=True, exist_ok=True)

    try:
        needs_ocr = detect_needs_ocr(pdf_path)
    except PDFProtectedError:
        raise

    pages: list[dict] = []
    if not needs_ocr:
        for page_number, raw_text in iter_native_text(pdf_path):
            clean = clean_text(raw_text)
            pages.append(
                {
                    "page_number": page_number,
                    "raw_text": raw_text,
                    "clean_text": clean,
                    "ocr_confidence": 100.0 if clean else 0.0,
                    "word_count": len(clean.split()),
                }
            )
    else:
        try:
            engine = OCREngine(
                language=language,
                oem=cfg.getint("ocr", "tesseract_oem"),
                psm=cfg.getint("ocr", "tesseract_psm"),
                confidence_threshold=ocr_threshold,
            )
        except pytesseract.TesseractNotFoundError as exc:
            raise RuntimeError(
                "Tesseract no está instalado. Instálalo y agrega el binario al PATH."
            ) from exc

        total_pages = sum(1 for _ in iter_native_text(pdf_path))
        workers = max(1, (os.cpu_count() or 2) - 1)
        for batch_start in range(1, total_pages + 1, BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE - 1, total_pages)
            try:
                rendered = render_pdf_pages(pdf_path, dpi=dpi, first_page=batch_start, last_page=batch_end)
            except Exception as exc:
                logging.exception("Lote OCR corrupto %s-%s: %s", batch_start, batch_end, exc)
                continue

            with ThreadPoolExecutor(max_workers=workers) as ex:
                futures = [
                    ex.submit(_process_ocr_page, batch_start + idx, image, engine, raw_dump_dir)
                    for idx, image in enumerate(rendered)
                ]
                for fut in tqdm(futures, desc=f"OCR {batch_start}-{batch_end}", unit="page"):
                    try:
                        pages.append(fut.result())
                    except Exception as exc:
                        logging.exception("Error procesando página OCR: %s", exc)

    pages.sort(key=lambda p: p["page_number"])
    confidences = [p["ocr_confidence"] for p in pages]
    avg_conf = round(sum(confidences) / len(confidences), 2) if confidences else 0.0

    return {
        "document": {
            "filename": pdf_path.name,
            "total_pages": len(pages),
            "processed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "ocr_engine": "tesseract-5.3",
            "language": language,
            "avg_confidence": avg_conf,
        },
        "pages": pages,
    }
