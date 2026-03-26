from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import logging

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
    fallback_lang: str | None = None
    retry_psm: int = 11
    aggressive: bool = False
    apply_sharpen: bool = False


class OCRUnavailableError(RuntimeError):
    pass


class OCRPageError(RuntimeError):
    pass


LOGGER = logging.getLogger("ocr_engine")


def _import_transformer_libs():
    try:
        import torch
        from PIL import Image
        from transformers import TrOCRProcessor, VisionEncoderDecoderModel
    except Exception as exc:
        raise OCRUnavailableError(
            "Dependencias de OCR Transformer no disponibles. "
            "Instala transformers, torch y Pillow en el entorno activo."
        ) from exc
    return torch, Image, TrOCRProcessor, VisionEncoderDecoderModel


def _import_ocr_libs():
    try:
        import pytesseract
        from pytesseract import TesseractError
        from PIL import Image, ImageEnhance, ImageFilter
    except Exception as exc:
        raise OCRUnavailableError(
            "Dependencias OCR no disponibles. Instala pytesseract y Pillow en el entorno activo."
        ) from exc
    return pytesseract, TesseractError, Image, ImageEnhance, ImageFilter


def configurar_tesseract(config: OCRConfig | None = None) -> OCRConfig:
    pytesseract, _, _, _, _ = _import_ocr_libs()
    cfg = config or OCRConfig()
    if cfg.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = cfg.tesseract_cmd
    return cfg


def validar_ocr_disponible(config: OCRConfig | None = None) -> OCRConfig:
    pytesseract, _, _, _, _ = _import_ocr_libs()
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
    _, _, Image, _, _ = _import_ocr_libs()
    zoom = max(72, dpi) / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=matrix, alpha=False)
    mode = "RGB" if pix.n >= 3 else "L"
    image = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
    if image.mode != "L":
        image = image.convert("L")
    return image


def _preprocess_image(image: Any, apply_sharpen: bool = False):
    _, _, _, ImageEnhance, ImageFilter = _import_ocr_libs()
    gray = image.convert("L")
    high_contrast = ImageEnhance.Contrast(gray).enhance(1.8)
    threshold = 170
    binarized = high_contrast.point(lambda p: 255 if p > threshold else 0)
    if apply_sharpen:
        return binarized.filter(ImageFilter.SHARPEN)
    return binarized


def _extract_with_single_config(image: Any, lang: str, oem: int, psm: int) -> str:
    pytesseract, TesseractError, _, _, _ = _import_ocr_libs()
    custom_config = f"--oem {oem} --psm {psm}"
    try:
        raw_text = pytesseract.image_to_string(image, lang=lang, config=custom_config)
    except TesseractError as exc:
        raise OCRPageError(str(exc)) from exc
    except Exception as exc:
        raise OCRPageError(f"Error inesperado en OCR: {exc}") from exc
    return limpiar_texto(raw_text)


def _generar_confianza(scores: list[Any], torch_module: Any) -> float:
    if not scores:
        return 0.0
    token_confidences: list[float] = []
    for score in scores:
        probs = torch_module.softmax(score, dim=-1)
        token_confidences.extend(probs.max(dim=-1).values.detach().cpu().tolist())
    return float(sum(token_confidences) / len(token_confidences)) if token_confidences else 0.0


def _imagen_baja_resolucion(image: Any, min_width: int = 900, min_height: int = 900) -> bool:
    width, height = image.size
    return width < min_width or height < min_height


def extract_text_with_transformer(
    pdf_path: str,
    model_name: str = "microsoft/trocr-large-printed",
    dpi: int = 300,
) -> list[dict[str, Any]]:
    """
    Ejecuta OCR con TrOCR página por página y devuelve resultados estructurados.

    Args:
        pdf_path: Ruta del PDF escaneado.
        model_name: Modelo TrOCR (printed o handwritten).
        dpi: Resolución de renderizado por página.

    Returns:
        Lista de dicts: {"page": int, "text": str, "confidence": float}.
    """
    pdf = Path(pdf_path)
    if not pdf.exists() or not pdf.is_file():
        raise FileNotFoundError(f"PDF inexistente: {pdf}")

    torch, _, TrOCRProcessor, VisionEncoderDecoderModel = _import_transformer_libs()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    processor = TrOCRProcessor.from_pretrained(model_name)
    model = VisionEncoderDecoderModel.from_pretrained(model_name)
    model.to(device)
    model.eval()

    resultados: list[dict[str, Any]] = []
    with fitz.open(pdf) as doc:
        for page_number, page in enumerate(doc, start=1):
            image = _page_to_image(page, dpi=max(300, dpi))
            if _imagen_baja_resolucion(image):
                resultados.append({"page": page_number, "text": "", "confidence": 0.0})
                continue
            try:
                pixel_values = processor(images=image, return_tensors="pt").pixel_values.to(device)
                with torch.no_grad():
                    generated = model.generate(
                        pixel_values,
                        return_dict_in_generate=True,
                        output_scores=True,
                    )
                decoded = processor.batch_decode(generated.sequences, skip_special_tokens=True)[0]
                clean_text = limpiar_texto(decoded)
                confidence = _generar_confianza(generated.scores, torch)
                resultados.append(
                    {
                        "page": page_number,
                        "text": clean_text,
                        "confidence": round(confidence, 4),
                    }
                )
            except Exception:
                resultados.append({"page": page_number, "text": "", "confidence": 0.0})
    return resultados


def concatenar_texto_transformer(
    pdf_path: str,
    model_name: str = "microsoft/trocr-large-printed",
    dpi: int = 300,
) -> str:
    """
    Concatena el texto extraído por TrOCR de todas las páginas del PDF.
    """
    page_results = extract_text_with_transformer(pdf_path, model_name=model_name, dpi=dpi)
    partes = [item["text"] for item in page_results if item.get("text")]
    return "\n\n".join(partes)


def ocr_pagina(page: fitz.Page, config: OCRConfig | None = None) -> str:
    cfg = configurar_tesseract(config)
    image = _page_to_image(page, dpi=cfg.dpi)
    preprocessed = _preprocess_image(image, apply_sharpen=cfg.apply_sharpen or cfg.aggressive)
    return _extract_with_single_config(preprocessed, lang=cfg.lang, oem=cfg.oem, psm=cfg.psm)


def ocr_pagina_con_reintentos(page: fitz.Page, page_number: int, config: OCRConfig | None = None) -> tuple[str, str | None]:
    cfg = configurar_tesseract(config)
    image = _page_to_image(page, dpi=cfg.dpi)
    preprocessed = _preprocess_image(image, apply_sharpen=cfg.apply_sharpen or cfg.aggressive)

    attempts: list[tuple[int, str]] = [(cfg.psm, cfg.lang), (cfg.retry_psm, cfg.lang)]
    if cfg.fallback_lang:
        attempts.extend([(cfg.psm, cfg.fallback_lang), (cfg.retry_psm, cfg.fallback_lang)])

    first_error: OCRPageError | None = None
    for idx, (psm, lang) in enumerate(attempts, start=1):
        LOGGER.info("página %s: OCR intento %s psm %s", page_number, idx, psm)
        try:
            text = _extract_with_single_config(preprocessed, lang=lang, oem=cfg.oem, psm=psm)
        except OCRPageError as exc:
            if first_error is None:
                first_error = exc
            continue
        if text:
            LOGGER.info("página %s: OCR exitoso con %s", page_number, lang)
            return text, lang

    if first_error is not None:
        raise first_error
    return "", None
