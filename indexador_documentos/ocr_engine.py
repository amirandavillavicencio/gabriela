from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import fitz

from config import OCR_DPI, OCR_OEM, OCR_PSM, TESSERACT_CMD, TESSERACT_LANG
from normalizador import limpiar_texto


@dataclass
class OCRConfig:
    tesseract_cmd: str = TESSERACT_CMD
    lang: str = TESSERACT_LANG
    dpi: int = OCR_DPI
    oem: int = OCR_OEM
    psm: int = OCR_PSM


class OCRUnavailableError(RuntimeError):
    pass


class OCRPageError(RuntimeError):
    pass


def _import_ocr_libs():
    try:
        import pytesseract
        from pytesseract import TesseractError
        from PIL import Image
    except Exception as exc:
        raise OCRUnavailableError(
            "Dependencias OCR no disponibles. Instala pytesseract y Pillow en el entorno activo."
        ) from exc
    return pytesseract, TesseractError, Image


def configurar_tesseract(config: OCRConfig | None = None) -> OCRConfig:
    pytesseract, _, _ = _import_ocr_libs()
    cfg = config or OCRConfig()
    if cfg.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = cfg.tesseract_cmd
    return cfg


def validar_ocr_disponible(config: OCRConfig | None = None) -> OCRConfig:
    pytesseract, _, _ = _import_ocr_libs()
    cfg = configurar_tesseract(config)
    cmd_path = Path(cfg.tesseract_cmd)
    if cfg.tesseract_cmd and not cmd_path.exists():
        raise OCRUnavailableError(f"Tesseract no encontrado en ruta configurada: {cfg.tesseract_cmd}")

    try:
        langs = pytesseract.get_languages(config="")
    except Exception as exc:
        raise OCRUnavailableError(f"No se pudo iniciar Tesseract OCR: {exc}") from exc

    if cfg.lang not in langs:
        available = ", ".join(sorted(langs)) if langs else "(sin idiomas detectados)"
        raise OCRUnavailableError(f"Idioma OCR '{cfg.lang}' no disponible. Idiomas detectados: {available}")

    return cfg


def _page_to_image(page: fitz.Page, dpi: int):
    _, _, Image = _import_ocr_libs()
    zoom = max(72, dpi) / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=matrix, alpha=False)
    mode = "RGB" if pix.n >= 3 else "L"
    image = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
    if image.mode != "L":
        image = image.convert("L")
    return image


def ocr_pagina(page: fitz.Page, config: OCRConfig | None = None) -> str:
    pytesseract, TesseractError, _ = _import_ocr_libs()
    cfg = configurar_tesseract(config)
    image = _page_to_image(page, dpi=cfg.dpi)
    custom_config = f"--oem {cfg.oem} --psm {cfg.psm}"
    try:
        raw_text = pytesseract.image_to_string(image, lang=cfg.lang, config=custom_config)
    except TesseractError as exc:
        raise OCRPageError(str(exc)) from exc
    except Exception as exc:
        raise OCRPageError(f"Error inesperado en OCR: {exc}") from exc

    return limpiar_texto(raw_text)
