from __future__ import annotations

from pathlib import Path
from typing import Any

import fitz

from normalizador import limpiar_paginas_con_ruido, limpiar_texto, texto_es_util
from ocr_engine import OCRPageError, OCRUnavailableError, validar_ocr_disponible, ocr_pagina
from utils import build_doc_id, document_output_dir, utc_now_iso, write_json


class PDFExtractionError(Exception):
    pass


def extraer_pdf(
    pdf_path: str | Path,
    output_root: Path | None = None,
    save_json: bool = True,
    force_ocr: bool = False,
) -> dict[str, Any]:
    path = Path(pdf_path)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"PDF inexistente: {path}")

    try:
        doc = fitz.open(path)
    except Exception as exc:
        raise PDFExtractionError(f"PDF inválido o corrupto: {path}") from exc

    pages: list[dict[str, Any]] = []
    warnings: list[str] = []

    ocr_cfg = None
    ocr_available = True
    try:
        ocr_cfg = validar_ocr_disponible()
    except OCRUnavailableError as exc:
        ocr_available = False
        warnings.append(str(exc))

    try:
        for i, page in enumerate(doc, start=1):
            raw_text = page.get_text("text") or ""
            base_clean_text = limpiar_texto(raw_text)
            has_text = bool(base_clean_text)

            if not has_text:
                warnings.append(f"Página {i} sin texto embebido.")

            pages.append(
                {
                    "page_number": i,
                    "has_text": has_text,
                    "text_source": "embedded_text" if has_text else "none",
                    "raw_text": raw_text,
                    "clean_text": base_clean_text,
                    "_page_obj": page,
                }
            )

        pages, cleaning_stats = limpiar_paginas_con_ruido(pages)

        ocr_used = False
        ocr_pages = 0
        embedded_text_pages = 0

        for page_data in pages:
            page_number = page_data["page_number"]
            page_obj = page_data.get("_page_obj")
            clean_text = (page_data.get("clean_text") or "").strip()

            use_embedded = texto_es_util(clean_text) and not force_ocr

            if use_embedded:
                page_data["has_text"] = True
                page_data["text_source"] = "embedded_text"
                embedded_text_pages += 1
                continue

            if force_ocr and not ocr_available:
                warnings.append(f"Página {page_number}: --force-ocr activo pero OCR no disponible.")

            if not ocr_available or page_obj is None:
                page_data["clean_text"] = clean_text if texto_es_util(clean_text) else ""
                page_data["has_text"] = bool(page_data["clean_text"])
                page_data["text_source"] = "embedded_text" if page_data["has_text"] else "none"
                if page_data["has_text"]:
                    embedded_text_pages += 1
                else:
                    warnings.append(f"Página {page_number} sin texto útil y sin OCR disponible.")
                continue

            try:
                ocr_text = ocr_pagina(page_obj, config=ocr_cfg)
            except OCRPageError as exc:
                warnings.append(f"Página {page_number}: error OCR: {exc}")
                page_data["clean_text"] = clean_text if texto_es_util(clean_text) else ""
                page_data["has_text"] = bool(page_data["clean_text"])
                page_data["text_source"] = "embedded_text" if page_data["has_text"] else "none"
                if page_data["has_text"]:
                    embedded_text_pages += 1
                continue

            if texto_es_util(ocr_text):
                page_data["raw_text"] = ocr_text
                page_data["clean_text"] = ocr_text
                page_data["has_text"] = True
                page_data["text_source"] = "ocr"
                ocr_used = True
                ocr_pages += 1
            else:
                page_data["clean_text"] = clean_text if texto_es_util(clean_text) else ""
                page_data["has_text"] = bool(page_data["clean_text"])
                page_data["text_source"] = "embedded_text" if page_data["has_text"] else "none"
                if page_data["has_text"]:
                    embedded_text_pages += 1
                else:
                    warnings.append(f"Página {page_number} sin texto útil tras OCR.")

        for page_data in pages:
            page_data.pop("_page_obj", None)

    finally:
        doc.close()

    full_parts = [p["clean_text"] for p in pages if p.get("clean_text")]
    has_extractable_text = any(p["has_text"] for p in pages)

    if not has_extractable_text:
        warnings.append("Documento sin texto útil extraíble ni OCR utilizable.")

    result: dict[str, Any] = {
        "id": build_doc_id(path.name),
        "source_name": path.name,
        "page_count": len(pages),
        "created_at": utc_now_iso(),
        "ocr_enabled": True,
        "ocr_used": ocr_used,
        "ocr_pages": ocr_pages,
        "embedded_text_pages": embedded_text_pages,
        "has_extractable_text": has_extractable_text,
        "extraction_warnings": list(dict.fromkeys(warnings)),
        "cleaning_stats": cleaning_stats,
        "pages": pages,
        "clean_full_text": "\n\n".join(full_parts),
    }

    if save_json:
        out_dir = document_output_dir(path.name, output_root)
        write_json(out_dir / "documento.json", result)

    return result
