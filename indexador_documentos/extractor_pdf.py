from __future__ import annotations

from pathlib import Path
from typing import Any
import logging

import fitz

from indexador_documentos.normalizador import limpiar_paginas_con_ruido, limpiar_texto, texto_es_util
from indexador_documentos.ocr_engine import (
    OCRConfig,
    OCRPageError,
    OCRUnavailableError,
    extract_text_with_transformer,
    ocr_pagina_con_reintentos,
    validar_ocr_disponible,
)
from indexador_documentos.utils import (
    build_doc_id,
    document_subdirs,
    file_sha256,
    utc_now_iso,
    write_json,
)


class PDFExtractionError(Exception):
    pass


LOGGER = logging.getLogger("extractor_pdf")


def _source_path_for_output(source_path: Path) -> str:
    try:
        return str(source_path.resolve())
    except OSError:
        return str(source_path)


def extraer_pdf(
    pdf_path: str | Path,
    output_root: Path | None = None,
    save_json: bool = True,
    force_ocr: bool = False,
    ocr_aggressive: bool = False,
    ocr_backend: str = "tesseract",
    transformer_model: str = "microsoft/trocr-large-printed",
    ocr_config: OCRConfig | None = None,
) -> dict[str, Any]:
    path = Path(pdf_path)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"PDF inexistente: {path}")

    file_hash = file_sha256(path)
    document_id = build_doc_id(path.name, file_hash)

    try:
        doc = fitz.open(path)
    except Exception as exc:
        raise PDFExtractionError(f"PDF inválido o corrupto: {path}") from exc

    pages: list[dict[str, Any]] = []
    warnings: list[str] = []

    ocr_cfg = ocr_config
    transformer_by_page: dict[int, dict[str, Any]] = {}
    ocr_available = True
    if ocr_backend == "transformer":
        try:
            transformer_results = extract_text_with_transformer(str(path), model_name=transformer_model)
            transformer_by_page = {item["page"]: item for item in transformer_results}
        except OCRUnavailableError as exc:
            ocr_available = False
            warnings.append(str(exc))
        except Exception as exc:
            ocr_available = False
            warnings.append(f"OCR Transformer no disponible: {exc}")
    else:
        try:
            ocr_cfg = validar_ocr_disponible(ocr_cfg)
        except OCRUnavailableError as exc:
            ocr_available = False
            warnings.append(str(exc))

    try:
        for i, page in enumerate(doc, start=1):
            raw_text = page.get_text("text") or ""
            base_clean_text = limpiar_texto(raw_text)
            has_text = bool(base_clean_text)
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

            embedded_is_useful = texto_es_util(clean_text)
            use_embedded = embedded_is_useful and not force_ocr

            page_warnings: list[str] = []
            extraction_layer = "native"
            ocr_confidence: float | None = None

            if use_embedded:
                page_data["has_text"] = True
                page_data["text_source"] = "embedded_text"
                embedded_text_pages += 1
            else:
                if not embedded_is_useful and clean_text:
                    page_warnings.append("texto_nativo_insuficiente")
                    extraction_layer = "fallback"

                if force_ocr and not ocr_available:
                    page_warnings.append("force_ocr_activo_pero_ocr_no_disponible")

                if not ocr_available or page_obj is None:
                    page_data["clean_text"] = clean_text if texto_es_util(clean_text) else ""
                    page_data["has_text"] = bool(page_data["clean_text"])
                    page_data["text_source"] = "embedded_text" if page_data["has_text"] else "none"
                    if page_data["has_text"]:
                        embedded_text_pages += 1
                    else:
                        page_warnings.append("sin_texto_util_y_sin_ocr")
                        extraction_layer = "fallback"
                else:
                    try:
                        if ocr_backend == "transformer":
                            transformer_page = transformer_by_page.get(page_number, {})
                            ocr_text = limpiar_texto(transformer_page.get("text", ""))
                            ocr_confidence = transformer_page.get("confidence")
                        else:
                            if ocr_cfg and ocr_aggressive:
                                ocr_cfg.aggressive = True
                            ocr_text, _ = ocr_pagina_con_reintentos(page_obj, page_number=page_number, config=ocr_cfg)
                    except OCRPageError as exc:
                        page_warnings.append(f"error_ocr:{exc}")
                        page_data["clean_text"] = clean_text if texto_es_util(clean_text) else ""
                        page_data["has_text"] = bool(page_data["clean_text"])
                        page_data["text_source"] = "embedded_text" if page_data["has_text"] else "none"
                        if page_data["has_text"]:
                            embedded_text_pages += 1
                        else:
                            extraction_layer = "fallback"
                    else:
                        if texto_es_util(ocr_text):
                            page_data["raw_text"] = ocr_text
                            page_data["clean_text"] = ocr_text
                            page_data["has_text"] = True
                            page_data["text_source"] = "ocr"
                            ocr_used = True
                            ocr_pages += 1
                            extraction_layer = "ocr" if not clean_text else "mixed"
                        else:
                            page_data["clean_text"] = clean_text if texto_es_util(clean_text) else ""
                            page_data["has_text"] = bool(page_data["clean_text"])
                            page_data["text_source"] = "embedded_text" if page_data["has_text"] else "none"
                            if page_data["has_text"]:
                                embedded_text_pages += 1
                                extraction_layer = "native"
                            else:
                                page_warnings.append("sin_texto_util_tras_ocr")
                                extraction_layer = "fallback"

            page_data["extraction_layer"] = extraction_layer
            page_data["ocr_confidence"] = ocr_confidence
            page_data["warnings"] = page_warnings
            page_data["text"] = page_data.get("clean_text") or ""
            page_data["text_length"] = len(page_data["text"])
            page_data["bbox"] = None

        for page_data in pages:
            page_data.pop("_page_obj", None)
            page_data.pop("raw_text", None)
            page_data.pop("clean_text", None)

    finally:
        doc.close()

    full_parts = [p["text"] for p in pages if p.get("text")]
    has_extractable_text = any(p["has_text"] for p in pages)

    if not has_extractable_text:
        warnings.append("Documento sin texto útil extraíble ni OCR utilizable.")

    extraction_summary = {
        "ocr_enabled": True,
        "ocr_backend": ocr_backend,
        "ocr_used": ocr_used,
        "ocr_available": ocr_available,
        "ocr_pages": ocr_pages,
        "embedded_text_pages": embedded_text_pages,
        "has_extractable_text": has_extractable_text,
    }

    result: dict[str, Any] = {
        "document_id": document_id,
        "id": document_id,
        "source_file": path.name,
        "source_name": path.name,
        "source_path": _source_path_for_output(path),
        "file_hash": file_hash,
        "processed_at": utc_now_iso(),
        "created_at": utc_now_iso(),
        "total_pages": len(pages),
        "page_count": len(pages),
        "extraction_summary": extraction_summary,
        "has_extractable_text": has_extractable_text,
        "extraction_warnings": list(dict.fromkeys(warnings)),
        "warnings": list(dict.fromkeys(warnings)),
        "cleaning_stats": cleaning_stats,
        "pages": pages,
        "clean_full_text": "\n\n".join(full_parts),
        "chunks": [],
    }

    if save_json:
        subdirs = document_subdirs(document_id, output_root)
        write_json(subdirs["extracted"] / "document.json", result)
        write_json(subdirs["extracted"] / "pages.json", pages)

    return result
