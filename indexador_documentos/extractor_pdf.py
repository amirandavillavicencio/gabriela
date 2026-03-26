from __future__ import annotations

from pathlib import Path
from typing import Any

import fitz

from normalizador import limpiar_paginas_con_ruido, limpiar_texto
from utils import build_doc_id, document_output_dir, utc_now_iso, write_json


class PDFExtractionError(Exception):
    pass


def extraer_pdf(pdf_path: str | Path, output_root: Path | None = None, save_json: bool = True) -> dict[str, Any]:
    path = Path(pdf_path)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"PDF inexistente: {path}")

    try:
        doc = fitz.open(path)
    except Exception as exc:
        raise PDFExtractionError(f"PDF inválido o corrupto: {path}") from exc

    pages: list[dict[str, Any]] = []
    warnings: list[str] = []

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
                }
            )
    finally:
        doc.close()

    pages, cleaning_stats = limpiar_paginas_con_ruido(pages)
    full_parts = [p["clean_text"] for p in pages if p.get("clean_text")]

    has_extractable_text = any(p["has_text"] for p in pages)
    if not has_extractable_text:
        warnings.append("Documento sin texto extraíble. Requiere OCR para indexación.")

    result: dict[str, Any] = {
        "id": build_doc_id(path.name),
        "source_name": path.name,
        "page_count": len(pages),
        "created_at": utc_now_iso(),
        "ocr_enabled": False,
        "has_extractable_text": has_extractable_text,
        "extraction_warnings": warnings,
        "cleaning_stats": cleaning_stats,
        "pages": pages,
        "clean_full_text": "\n\n".join(full_parts),
    }

    if save_json:
        out_dir = document_output_dir(path.name, output_root)
        write_json(out_dir / "documento.json", result)

    return result
