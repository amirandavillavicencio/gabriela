from __future__ import annotations

import logging
import math
import re
import statistics
from dataclasses import dataclass
from typing import Any


LOGGER = logging.getLogger("preprocessor")


class PreprocessingUnavailableError(RuntimeError):
    """Raised when optional preprocessing dependencies are not available."""


@dataclass
class PreprocessConfig:
    """Configuration for page image preprocessing before OCR."""

    min_dpi: int = 200
    upscale_target_dpi: int = 300
    gaussian_radius: float = 1.0
    max_skew_angle: float = 5.0
    skew_step: float = 0.5


def _import_pillow():
    try:
        from PIL import Image, ImageFilter
    except Exception as exc:
        raise PreprocessingUnavailableError(
            "Pillow no está disponible. Instala Pillow para usar preprocesamiento de imagen."
        ) from exc
    return Image, ImageFilter


def _import_pytesseract() -> Any:
    try:
        import pytesseract
    except Exception as exc:
        raise PreprocessingUnavailableError(
            "pytesseract no está disponible. Instala pytesseract para detección de orientación."
        ) from exc
    return pytesseract


def _image_dpi(image: Any) -> int | None:
    dpi = image.info.get("dpi")
    if not dpi:
        return None
    if isinstance(dpi, tuple) and dpi:
        return int(dpi[0])
    if isinstance(dpi, (int, float)):
        return int(dpi)
    return None


def upscale_if_low_dpi(image: Any, config: PreprocessConfig | None = None) -> Any:
    """Upscales image with LANCZOS if input DPI is lower than configured minimum."""
    Image, _ = _import_pillow()
    cfg = config or PreprocessConfig()

    detected_dpi = _image_dpi(image)
    if detected_dpi is None or detected_dpi >= cfg.min_dpi:
        return image

    scale_factor = max(1.0, cfg.upscale_target_dpi / max(1, detected_dpi))
    new_size = (
        max(1, int(image.width * scale_factor)),
        max(1, int(image.height * scale_factor)),
    )

    resized = image.resize(new_size, resample=Image.Resampling.LANCZOS)
    resized.info["dpi"] = (cfg.upscale_target_dpi, cfg.upscale_target_dpi)
    LOGGER.info(
        "Upscaling aplicado por DPI bajo: %s -> %s (factor %.2f)",
        detected_dpi,
        cfg.upscale_target_dpi,
        scale_factor,
    )
    return resized


def denoise_gaussian(image: Any, radius: float = 1.0) -> Any:
    """Applies gaussian blur for light denoising."""
    _, ImageFilter = _import_pillow()
    return image.filter(ImageFilter.GaussianBlur(radius=radius))


def _otsu_threshold_value(gray_image: Any) -> int:
    histogram = gray_image.histogram()
    total = gray_image.width * gray_image.height
    if total <= 0:
        return 127

    sum_total = 0.0
    for idx, count in enumerate(histogram[:256]):
        sum_total += idx * count

    sum_background = 0.0
    background_weight = 0
    best_variance = -1.0
    best_threshold = 127

    for threshold, count in enumerate(histogram[:256]):
        background_weight += count
        if background_weight == 0:
            continue

        foreground_weight = total - background_weight
        if foreground_weight == 0:
            break

        sum_background += threshold * count
        mean_background = sum_background / background_weight
        mean_foreground = (sum_total - sum_background) / foreground_weight
        between_class_variance = (
            background_weight
            * foreground_weight
            * (mean_background - mean_foreground) ** 2
        )

        if between_class_variance > best_variance:
            best_variance = between_class_variance
            best_threshold = threshold

    return best_threshold


def binarize_otsu(image: Any) -> Any:
    """Adaptive binarization using Otsu threshold."""
    gray = image.convert("L")
    threshold = _otsu_threshold_value(gray)
    return gray.point(lambda px: 255 if px > threshold else 0, mode="1").convert("L")


def detect_orientation(image: Any) -> int:
    """Detects orientation in 0/90/180/270 degrees using Tesseract OSD."""
    pytesseract = _import_pytesseract()

    try:
        osd = pytesseract.image_to_osd(image)
    except Exception as exc:
        LOGGER.warning("No se pudo detectar orientación con OSD: %s", exc)
        return 0

    match = re.search(r"Rotate:\s*(\d+)", osd)
    if not match:
        return 0

    rotation = int(match.group(1)) % 360
    return rotation if rotation in {0, 90, 180, 270} else 0


def _projection_variance(binary_image: Any) -> float:
    data = binary_image.load()
    row_scores: list[int] = []

    for y in range(binary_image.height):
        black_pixels = 0
        for x in range(binary_image.width):
            if data[x, y] < 128:
                black_pixels += 1
        row_scores.append(black_pixels)

    if len(row_scores) <= 1:
        return 0.0
    return statistics.pvariance(row_scores)


def _estimate_skew_angle(binary_image: Any, max_angle: float = 5.0, step: float = 0.5) -> float:
    if step <= 0:
        return 0.0

    best_angle = 0.0
    best_score = -math.inf

    angle = -abs(max_angle)
    while angle <= abs(max_angle) + 1e-9:
        rotated = binary_image.rotate(angle, expand=True, fillcolor=255)
        score = _projection_variance(rotated)
        if score > best_score:
            best_score = score
            best_angle = angle
        angle += step

    return round(best_angle, 3)


def deskew_auto(image: Any, max_angle: float = 5.0, step: float = 0.5) -> tuple[Any, float]:
    """
    Corrects small scan skew angle.

    Returns:
        (deskewed_image, applied_angle)
    """
    binary = binarize_otsu(image)
    angle = _estimate_skew_angle(binary, max_angle=max_angle, step=step)
    corrected = image.rotate(angle, expand=True, fillcolor=255)
    return corrected, angle


def preprocess_for_ocr(image: Any, config: PreprocessConfig | None = None) -> tuple[Any, dict[str, Any]]:
    """Complete preprocessing pipeline for OCR-ready pages."""
    cfg = config or PreprocessConfig()

    working = image.convert("L") if image.mode != "L" else image
    working = upscale_if_low_dpi(working, cfg)

    orientation = detect_orientation(working)
    if orientation:
        # Tesseract rotate value indicates clockwise correction.
        working = working.rotate(-orientation, expand=True, fillcolor=255)

    working = denoise_gaussian(working, radius=cfg.gaussian_radius)
    working, skew_angle = deskew_auto(
        working,
        max_angle=cfg.max_skew_angle,
        step=cfg.skew_step,
    )
    working = binarize_otsu(working)

    metadata = {
        "orientation_correction": orientation,
        "deskew_angle": skew_angle,
        "dpi": _image_dpi(working),
    }
    return working, metadata
