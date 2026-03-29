from __future__ import annotations

import logging
import math
import time
from dataclasses import replace
from functools import lru_cache
from typing import Literal

import cv2
import numpy as np
from PIL import Image

from pipeline.preprocessor_config import PreprocessConfig
from pipeline.preprocessor_types import (
    PreprocessConfigError,
    PreprocessInputError,
    PreprocessQualityError,
    PreprocessResult,
    QualityScore,
    StepResult,
)

LOGGER = logging.getLogger(__name__)
PIPELINE_VERSION = "1.0.0"


class _StepContext(dict):
    pass


@lru_cache(maxsize=128)
def _quality_threshold_cache(config: PreprocessConfig) -> tuple[float, float, float]:
    return (
        config.quality_regression_threshold,
        config.quality_low_threshold,
        config.quality_critical_threshold,
    )


def _now_ms() -> int:
    return time.perf_counter_ns()


def _elapsed_ms(start_ns: int) -> float:
    return (time.perf_counter_ns() - start_ns) / 1_000_000.0


def _to_quality_unit(laplacian_var: float) -> float:
    return float(min(max(laplacian_var / 500.0, 0.0), 1.0))


def _laplacian_quality(gray: np.ndarray) -> float:
    if gray.size == 0:
        return 0.0
    lv = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    return _to_quality_unit(lv)


def _estimate_noise_level(gray: np.ndarray) -> float:
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    median = np.median(lap)
    mad = np.median(np.abs(lap - median))
    sigma = mad / 0.6745 if mad > 0 else 0.0
    return float(min(max(sigma / 30.0, 0.0), 1.0))


def _rms_contrast(gray: np.ndarray) -> float:
    return float(min(max(np.std(gray) / 127.5, 0.0), 1.0))


def _text_density(gray: np.ndarray) -> float:
    total = gray.size
    if total == 0:
        return 0.0
    return float(np.sum(gray < 128) / total)


def _safe_odd(value: int, minimum: int = 3) -> int:
    v = max(value, minimum)
    return v if v % 2 == 1 else v + 1


def _np_to_pil(gray: np.ndarray, dpi: int) -> Image.Image:
    image = Image.fromarray(gray.astype(np.uint8), mode="L")
    image.info["dpi"] = (dpi, dpi)
    return image


def _step_skipped(name: str, reason: str, quality: float, params: dict | None = None) -> StepResult:
    return StepResult(
        step_name=name,
        applied=False,
        skipped_reason=reason,
        delta_ms=0.0,
        params_used=params or {},
        quality_before=quality,
        quality_after=quality,
    )


def _step_result(name: str, start_ns: int, q_before: float, q_after: float, params: dict, applied: bool = True, reason: str | None = None) -> StepResult:
    return StepResult(
        step_name=name,
        applied=applied,
        skipped_reason=reason,
        delta_ms=round(_elapsed_ms(start_ns), 3),
        params_used=params,
        quality_before=q_before,
        quality_after=q_after,
    )


def _ensure_input(image: Image.Image) -> None:
    if image is None:
        raise PreprocessInputError("Input image cannot be None")
    if not isinstance(image, Image.Image):
        raise PreprocessInputError("Input must be a PIL Image")
    if image.size[0] <= 0 or image.size[1] <= 0:
        raise PreprocessInputError("Input image has invalid dimensions")


def _estimate_dpi_from_dimensions(width: int, height: int) -> int:
    min_inches = min(8.27, 11.0)
    return int(round(min(width, height) / min_inches))


def _rotate_90(gray: np.ndarray, angle: int) -> np.ndarray:
    if angle == 90:
        return cv2.rotate(gray, cv2.ROTATE_90_CLOCKWISE)
    if angle == 180:
        return cv2.rotate(gray, cv2.ROTATE_180)
    if angle == 270:
        return cv2.rotate(gray, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return gray


def _projection_variance_for_angle(binary: np.ndarray) -> float:
    profile = np.sum(binary == 0, axis=1).astype(np.float32)
    return float(np.var(profile))


def _threshold_desc(config: PreprocessConfig) -> dict[str, str]:
    return {
        "target_dpi": "Target normalized DPI used for OCR preprocessing.",
        "min_dpi": "If effective DPI is below this value, the image is upscaled.",
        "max_dpi": "If effective DPI is above this value, the image is downscaled.",
        "enable_dpi_normalize": "Enable/disable step 1 DPI normalization.",
        "enable_color_normalize": "Enable/disable step 2 grayscale and inversion normalization.",
        "enable_border_removal": "Enable/disable step 3 border and artifact cleanup.",
        "enable_orientation": "Enable/disable step 4 orientation correction.",
        "enable_deskew": "Enable/disable step 5 deskew correction.",
        "enable_denoise": "Enable/disable step 6 denoise stage.",
        "enable_contrast": "Enable/disable step 7 contrast enhancement.",
        "enable_binarize": "Enable/disable step 8 binarization.",
        "enable_validation": "Enable/disable step 9 quality validation and rollback.",
        "min_skew_threshold": "Angles below this threshold are ignored as non-actionable.",
        "max_skew_threshold": "Angles above this threshold are ignored as unstable.",
        "denoise_tier_light_h": "NLM strength parameter for light denoise tier.",
        "denoise_tier_medium_h": "NLM strength parameter for medium/heavy denoise tiers.",
        "bilateral_d": "Bilateral neighborhood diameter.",
        "bilateral_sigma_color": "Bilateral sigma color.",
        "bilateral_sigma_space": "Bilateral sigma space.",
        "binarization_strategy": "auto/sauvola/otsu/niblack strategy selector.",
        "sauvola_window_ratio": "Window ratio for Sauvola and Niblack local thresholds.",
        "sauvola_k": "Sauvola k parameter.",
        "surya_prefers_binary": "Whether Surya path should receive binary image.",
        "clahe_clip_limit": "CLAHE clip limit.",
        "clahe_tile_grid": "CLAHE tile grid size.",
        "use_tesseract_osd": "Attempt Tesseract OSD orientation detection first.",
        "quality_regression_threshold": "Minimum ratio output/input sharpness allowed.",
        "quality_low_threshold": "Below this overall quality, page is flagged low quality.",
        "quality_critical_threshold": "Below this quality, raise error if emergency enhancement fails.",
        "max_page_pixels": "Hard cap for page pixels before automatic downscale.",
        "parallel_steps": "Reserved for future use; processing remains sequential.",
        "_active_thresholds": str(_quality_threshold_cache(config)),
    }


def _step1_dpi_normalize(img: Image.Image, config: PreprocessConfig, ctx: _StepContext) -> tuple[np.ndarray, StepResult]:
    q_before = _laplacian_quality(np.array(img.convert("L"), dtype=np.uint8))
    if not config.enable_dpi_normalize:
        arr = np.array(img.convert("L"), dtype=np.uint8)
        return arr, _step_skipped("dpi_normalize", "disabled", q_before)

    start = _now_ms()
    width, height = img.size
    dpi_info = img.info.get("dpi")
    original_dpi = int(round(dpi_info[0])) if isinstance(dpi_info, tuple) and dpi_info else _estimate_dpi_from_dimensions(width, height)
    effective_dpi = original_dpi
    was_upscaled = False

    if width * height > config.max_page_pixels:
        scale = math.sqrt(config.max_page_pixels / float(width * height))
        new_w, new_h = max(1, int(width * scale)), max(1, int(height * scale))
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        width, height = img.size
        effective_dpi = int(max(72, effective_dpi * scale))

    if effective_dpi < config.min_dpi:
        scale = config.target_dpi / float(max(effective_dpi, 1))
        new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
        img = img.resize(new_size, Image.Resampling.LANCZOS)
        effective_dpi = config.target_dpi
        was_upscaled = True
        ctx["low_resolution"] = True
    elif effective_dpi > config.max_dpi:
        scale = config.target_dpi / float(effective_dpi)
        new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
        img = img.resize(new_size, Image.Resampling.LANCZOS)
        effective_dpi = config.target_dpi

    arr = np.array(img.convert("L"), dtype=np.uint8)
    q_after = _laplacian_quality(arr)
    ctx["effective_dpi"] = int(effective_dpi)
    ctx["was_upscaled"] = was_upscaled
    return arr, _step_result(
        "dpi_normalize",
        start,
        q_before,
        q_after,
        {
            "target_dpi": config.target_dpi,
            "original_dpi": original_dpi,
            "effective_dpi": effective_dpi,
            "was_upscaled": was_upscaled,
        },
    )


def _step2_color_normalize(img: np.ndarray, config: PreprocessConfig, ctx: _StepContext) -> tuple[np.ndarray, StepResult]:
    q_before = _laplacian_quality(img.astype(np.uint8))
    if not config.enable_color_normalize:
        return img, _step_skipped("color_normalize", "disabled", q_before)
    start = _now_ms()

    if img.ndim == 3 and img.shape[2] == 4:
        alpha = img[:, :, 3:4].astype(np.float32) / 255.0
        rgb = img[:, :, :3].astype(np.float32)
        imgf = alpha * rgb + (1.0 - alpha) * 255.0
        gray = np.dot(imgf[:, :, :3], np.array([0.299, 0.587, 0.114], dtype=np.float32))
        gray = np.clip(gray, 0, 255).astype(np.uint8)
        source = "rgba"
    elif img.ndim == 3 and img.shape[2] >= 3:
        rgb = img[:, :, :3].astype(np.float32)
        gray = np.dot(rgb, np.array([0.299, 0.587, 0.114], dtype=np.float32))
        gray = np.clip(gray, 0, 255).astype(np.uint8)
        source = "rgb"
    else:
        gray = img.astype(np.uint8)
        source = "gray"

    dark_page = False
    if float(np.median(gray)) < 128.0:
        gray = cv2.bitwise_not(gray)
        dark_page = True
    ctx["dark_page"] = dark_page
    q_after = _laplacian_quality(gray)
    return gray, _step_result("color_normalize", start, q_before, q_after, {"source": source, "dark_page": dark_page})


def _step3_border_removal(img: np.ndarray, config: PreprocessConfig, ctx: _StepContext) -> tuple[np.ndarray, StepResult]:
    q_before = _laplacian_quality(img)
    if not config.enable_border_removal:
        return img, _step_skipped("border_removal", "disabled", q_before)
    start = _now_ms()

    work = img.copy()
    h, w = work.shape[:2]
    black = (work < 30).astype(np.uint8)
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(black, connectivity=8)
    has_borders = False
    border_thickness = 0
    touches_3_edges = False
    largest_label = -1
    largest_area = 0
    for label in range(1, num_labels):
        x, y, ww, hh, area = stats[label]
        touch = [x <= 0, y <= 0, x + ww >= w, y + hh >= h]
        if area > largest_area:
            largest_area = int(area)
            largest_label = label
            touches_3_edges = sum(touch) >= 3
            border_thickness = max(ww, hh)

    if largest_label > 0 and touches_3_edges and largest_area >= int(0.08 * w * h):
        work[labels == largest_label] = 255
        has_borders = True

    if has_borders:
        margin = max(1, int(w * 0.05))
        roi = work[:, :margin].copy()
        circles = cv2.HoughCircles(roi, cv2.HOUGH_GRADIENT, dp=1.2, minDist=30, param1=200, param2=30, minRadius=15, maxRadius=50)
        if circles is not None:
            for c in np.round(circles[0]).astype(int):
                cx, cy, rad = c
                cv2.circle(work, (int(cx), int(cy)), int(rad), 255, -1)
        roi_r = work[:, w - margin :].copy()
        circles_r = cv2.HoughCircles(roi_r, cv2.HOUGH_GRADIENT, dp=1.2, minDist=30, param1=200, param2=30, minRadius=15, maxRadius=50)
        if circles_r is not None:
            for c in np.round(circles_r[0]).astype(int):
                cx, cy, rad = c
                cv2.circle(work, (int(cx + w - margin), int(cy)), int(rad), 255, -1)

        left_zone = int(max(1, w * 0.03))
        right_zone = int(max(1, w * 0.97))
        center = work[:, int(w * 0.1) : int(w * 0.9)]
        center_med = float(np.median(center)) if center.size else 255.0
        for x in range(left_zone):
            col_med = float(np.median(work[:, x]))
            if col_med > 1:
                factor = center_med / col_med
                work[:, x] = np.clip(work[:, x].astype(np.float32) * factor, 0, 255).astype(np.uint8)
        for x in range(right_zone, w):
            col_med = float(np.median(work[:, x]))
            if col_med > 1:
                factor = center_med / col_med
                work[:, x] = np.clip(work[:, x].astype(np.float32) * factor, 0, 255).astype(np.uint8)
    else:
        q_after = _laplacian_quality(work)
        ctx["has_borders"] = False
        return work, _step_result("border_removal", start, q_before, q_after, {"has_borders": False}, applied=False, reason="no_borders_detected")

    ctx["has_borders"] = has_borders
    q_after = _laplacian_quality(work)
    return work, _step_result("border_removal", start, q_before, q_after, {"has_borders": has_borders, "border_thickness_px": border_thickness})


def _orientation_from_osd(img: np.ndarray) -> int | None:
    try:
        import pytesseract

        text = pytesseract.image_to_osd(Image.fromarray(img), config="--psm 0")
        for line in text.splitlines():
            if "Orientation in degrees" in line:
                return int(line.split(":")[-1].strip())
    except (RuntimeError, ValueError, ImportError):
        return None
    return None


def _orientation_from_projection(img: np.ndarray) -> int:
    small = cv2.resize(img, None, fx=0.25, fy=0.25, interpolation=cv2.INTER_AREA)
    _, binary = cv2.threshold(small, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    angles = [0, 90, 180, 270]
    best_angle, best_score = 0, -1.0
    for angle in angles:
        rot = _rotate_90(binary, angle)
        score = _projection_variance_for_angle(rot)
        if score > best_score:
            best_angle, best_score = angle, score
    return best_angle


def _step4_orientation(img: np.ndarray, config: PreprocessConfig, ctx: _StepContext) -> tuple[np.ndarray, StepResult]:
    q_before = _laplacian_quality(img)
    if not config.enable_orientation:
        return img, _step_skipped("orientation", "disabled", q_before)
    start = _now_ms()
    orient_a = _orientation_from_osd(img) if config.use_tesseract_osd else None
    orient_b = _orientation_from_projection(img)
    orient_c = 90 if img.shape[1] > img.shape[0] * 1.4 else 0
    orientation = orient_a if orient_a is not None else orient_b
    if orient_a is None and orient_b == 0:
        orientation = orient_c

    if orientation not in {0, 90, 180, 270}:
        orientation = 0
    corrected = _rotate_90(img, orientation)
    ctx["orientation_deg"] = int(orientation)
    q_after = _laplacian_quality(corrected)
    if orientation == 0:
        return corrected, _step_result(
            "orientation",
            start,
            q_before,
            q_after,
            {"method_a": orient_a, "method_b": orient_b, "method_c": orient_c, "chosen": orientation},
            applied=False,
            reason="already_upright",
        )
    return corrected, _step_result("orientation", start, q_before, q_after, {"method_a": orient_a, "method_b": orient_b, "method_c": orient_c, "chosen": orientation})


def _weighted_median(values: np.ndarray, weights: np.ndarray) -> float:
    sorter = np.argsort(values)
    values, weights = values[sorter], weights[sorter]
    cumsum = np.cumsum(weights)
    cutoff = weights.sum() / 2.0
    return float(values[np.searchsorted(cumsum, cutoff)])


def _projection_entropy(binary: np.ndarray) -> float:
    proj = np.sum(binary == 0, axis=1).astype(np.float64)
    total = proj.sum()
    if total <= 0:
        return 10.0
    p = proj / total
    p = p[p > 0]
    return float(-np.sum(p * np.log2(p)))


def _deskew_projection_fallback(gray: np.ndarray) -> float:
    best_angle = 0.0
    best_entropy = float("inf")
    h, w = gray.shape
    center = (w // 2, h // 2)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    for angle in np.arange(-15.0, 15.1, 0.1):
        m = cv2.getRotationMatrix2D(center, angle, 1.0)
        rot = cv2.warpAffine(binary, m, (w, h), flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_REPLICATE)
        ent = _projection_entropy(rot)
        if ent < best_entropy:
            best_entropy = ent
            best_angle = float(angle)
    return best_angle


def _step5_deskew(img: np.ndarray, config: PreprocessConfig, ctx: _StepContext) -> tuple[np.ndarray, StepResult]:
    q_before = _laplacian_quality(img)
    if not config.enable_deskew:
        return img, _step_skipped("deskew", "disabled", q_before)
    start = _now_ms()

    small = cv2.resize(img, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
    _, binary = cv2.threshold(small, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    kernel_w = max(1, small.shape[1] // 80)
    kernel = np.ones((1, kernel_w), np.uint8)
    dilated = cv2.dilate(255 - binary, kernel, iterations=1)

    lines = cv2.HoughLinesP(dilated, rho=1, theta=np.pi / 180, threshold=100, minLineLength=int(small.shape[1] * 0.3), maxLineGap=20)

    angle = 0.0
    method = "hough"
    if lines is not None and len(lines) >= 5:
        angles = []
        lengths = []
        for line in lines[:, 0, :]:
            x1, y1, x2, y2 = map(float, line)
            this_angle = math.degrees(math.atan2(y2 - y1, x2 - x1))
            if abs(this_angle) > 45:
                continue
            angles.append(this_angle)
            lengths.append(math.hypot(x2 - x1, y2 - y1))
        if angles:
            angle = _weighted_median(np.array(angles, dtype=np.float64), np.array(lengths, dtype=np.float64))
        else:
            method = "projection"
            angle = _deskew_projection_fallback(small)
    else:
        method = "projection"
        angle = _deskew_projection_fallback(small)

    ctx["skew_angle_deg"] = float(angle)
    if abs(angle) < config.min_skew_threshold:
        q_after = _laplacian_quality(img)
        return img, _step_result("deskew", start, q_before, q_after, {"angle": angle, "method": method}, applied=False, reason="below_threshold")
    if abs(angle) > config.max_skew_threshold:
        q_after = _laplacian_quality(img)
        return img, _step_result("deskew", start, q_before, q_after, {"angle": angle, "method": method}, applied=False, reason="angle_too_large")

    h, w = img.shape
    m = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), -angle, 1.0)
    deskewed = cv2.warpAffine(img, m, (w, h), flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REPLICATE, borderValue=255)
    q_after = _laplacian_quality(deskewed)
    return deskewed, _step_result("deskew", start, q_before, q_after, {"angle": angle, "method": method})


def _step6_denoise(img: np.ndarray, config: PreprocessConfig, ctx: _StepContext) -> tuple[np.ndarray, StepResult]:
    q_before = _laplacian_quality(img)
    if not config.enable_denoise:
        return img, _step_skipped("denoise", "disabled", q_before)
    start = _now_ms()
    noise = _estimate_noise_level(img)
    ctx["noise_level"] = noise
    den = img
    tier = "tier0"
    if noise < 0.05:
        q_after = _laplacian_quality(den)
        return den, _step_result("denoise", start, q_before, q_after, {"tier": tier, "noise_level": noise}, applied=False, reason="low_noise")
    if noise < 0.20:
        tier = "tier1_bilateral"
        den = cv2.bilateralFilter(img, d=config.bilateral_d, sigmaColor=config.bilateral_sigma_color, sigmaSpace=config.bilateral_sigma_space)
    elif noise < 0.50:
        tier = "tier2_nlm"
        local_std = cv2.blur((img.astype(np.float32) - cv2.blur(img.astype(np.float32), (7, 7))) ** 2, (7, 7)) ** 0.5
        mask = local_std > np.percentile(local_std, 60)
        nlm = cv2.fastNlMeansDenoising(img, None, h=config.denoise_tier_medium_h, templateWindowSize=7, searchWindowSize=21)
        den = img.copy()
        den[mask] = nlm[mask]
    else:
        tier = "tier3_heavy"
        opened = cv2.morphologyEx(img, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
        den = cv2.fastNlMeansDenoising(opened, None, h=config.denoise_tier_medium_h, templateWindowSize=7, searchWindowSize=21)
        ctx["human_review"] = True
    q_after = _laplacian_quality(den)
    return den, _step_result("denoise", start, q_before, q_after, {"tier": tier, "noise_level": noise})


def _step7_contrast(img: np.ndarray, config: PreprocessConfig, ctx: _StepContext) -> tuple[np.ndarray, StepResult]:
    q_before = _laplacian_quality(img)
    if not config.enable_contrast:
        return img, _step_skipped("contrast", "disabled", q_before)
    start = _now_ms()

    clahe = cv2.createCLAHE(clipLimit=config.clahe_clip_limit, tileGridSize=(config.clahe_tile_grid, config.clahe_tile_grid))
    out = clahe.apply(img)

    p20 = np.percentile(out, 20)
    dark_mask = out <= p20
    mean_dark = float(out[dark_mask].mean()) if np.any(dark_mask) else 128.0
    gamma_applied = False
    if mean_dark < 60 and mean_dark > 1:
        gamma = math.log(128.0) / math.log(mean_dark)
        table = np.array([((i / 255.0) ** (1.0 / gamma)) * 255 for i in range(256)]).astype(np.uint8)
        out = cv2.LUT(out, table)
        gamma_applied = True

    h, w = out.shape
    gh, gw = 4, 4
    tile_h, tile_w = max(1, h // gh), max(1, w // gw)
    global_mean = float(out.mean())
    needs_local = False
    tile_means: list[float] = []
    for ty in range(gh):
        for tx in range(gw):
            y1, y2 = ty * tile_h, h if ty == gh - 1 else (ty + 1) * tile_h
            x1, x2 = tx * tile_w, w if tx == gw - 1 else (tx + 1) * tile_w
            m = float(out[y1:y2, x1:x2].mean())
            tile_means.append(m)
            if abs(m - global_mean) > 40:
                needs_local = True
    if needs_local:
        outf = out.astype(np.float32)
        for ty in range(gh):
            for tx in range(gw):
                y1, y2 = ty * tile_h, h if ty == gh - 1 else (ty + 1) * tile_h
                x1, x2 = tx * tile_w, w if tx == gw - 1 else (tx + 1) * tile_w
                tile = outf[y1:y2, x1:x2]
                mean_tile = float(tile.mean())
                if mean_tile > 0:
                    outf[y1:y2, x1:x2] = np.clip(tile / (mean_tile / max(global_mean, 1e-6)), 0, 255)
        out = outf.astype(np.uint8)

    ctx["contrast"] = _rms_contrast(out)
    q_after = _laplacian_quality(out)
    return out, _step_result("contrast", start, q_before, q_after, {"gamma_applied": gamma_applied, "local_norm": needs_local, "tile_means": tile_means[:4]})


def _choose_binarization_strategy(img: np.ndarray, config: PreprocessConfig, ctx: _StepContext) -> str:
    if config.binarization_strategy != "auto":
        return config.binarization_strategy
    contrast = ctx.get("contrast", _rms_contrast(img))
    noise = ctx.get("noise_level", _estimate_noise_level(img))
    has_borders = bool(ctx.get("has_borders", False))
    uneven = np.std(np.array_split(img.mean(axis=0), 4)) > 20
    if uneven or has_borders:
        return "sauvola"
    if contrast > 0.4 and noise < 0.2 and not has_borders:
        return "otsu"
    if noise > 0.4 or contrast < 0.2:
        return "niblack"
    return "sauvola"


def _step8_binarize(img: np.ndarray, config: PreprocessConfig, extraction_layer: Literal["native", "surya", "paddleocr"], ctx: _StepContext) -> tuple[np.ndarray, StepResult]:
    q_before = _laplacian_quality(img)
    if not config.enable_binarize:
        return img, _step_skipped("binarize", "disabled", q_before)
    if extraction_layer == "native":
        return img, _step_skipped("binarize", "native_extraction_layer", q_before)
    if extraction_layer == "surya" and not config.surya_prefers_binary:
        return img, _step_skipped("binarize", "surya_prefers_grayscale", q_before)

    start = _now_ms()
    strategy = _choose_binarization_strategy(img, config, ctx)
    h, w = img.shape
    if strategy == "otsu":
        _, binary = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        is_table_like = False
    elif strategy == "niblack":
        window = _safe_odd(w // 40, 15)
        fimg = img.astype(np.float32)
        mean = cv2.boxFilter(fimg, -1, (window, window))
        mean_sq = cv2.boxFilter(fimg * fimg, -1, (window, window))
        std = np.sqrt(np.maximum(mean_sq - mean * mean, 0.0))
        thresh = mean + (-0.1) * std
        binary = (fimg > thresh).astype(np.uint8) * 255
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, np.ones((2, 2), np.uint8))
        is_table_like = False
    else:
        window = _safe_odd(w // config.sauvola_window_ratio, 15)
        fimg = img.astype(np.float32)
        mean = cv2.boxFilter(fimg, -1, (window, window))
        mean_sq = cv2.boxFilter(fimg * fimg, -1, (window, window))
        std = np.sqrt(np.maximum(mean_sq - mean * mean, 0.0))
        thresh = mean * (1 + config.sauvola_k * (std / 128.0 - 1.0))
        binary = (fimg > thresh).astype(np.uint8) * 255
        is_table_like = cv2.HoughLinesP(255 - binary, 1, np.pi / 180, threshold=150, minLineLength=int(w * 0.4), maxLineGap=5) is not None

    if not is_table_like:
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, np.ones((1, 1), np.uint8))
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, np.ones((2, 2), np.uint8))

    q_after = _laplacian_quality(binary)
    return binary.astype(np.uint8), _step_result("binarize", start, q_before, q_after, {"strategy": strategy, "is_table_like": is_table_like})


def _build_quality_score(img: np.ndarray, ctx: _StepContext, overall_override: float | None = None) -> QualityScore:
    sharp = _laplacian_quality(img)
    contrast = _rms_contrast(img)
    noise = _estimate_noise_level(img)
    density = _text_density(img)
    overall = (
        0.35 * sharp
        + 0.30 * contrast
        + 0.20 * (1.0 - noise)
        + 0.15 * min(density / 0.15, 1.0)
    )
    if overall_override is not None:
        overall = overall_override
    return QualityScore(
        overall=float(min(max(overall, 0.0), 1.0)),
        sharpness=float(sharp),
        contrast=float(contrast),
        noise_level=float(noise),
        skew_angle_deg=float(ctx.get("skew_angle_deg", 0.0)),
        orientation_deg=int(ctx.get("orientation_deg", 0)),
        dark_page=bool(ctx.get("dark_page", False)),
        low_resolution=bool(ctx.get("low_resolution", False)),
        has_borders=bool(ctx.get("has_borders", False)),
        text_density=float(density),
    )


def _step9_validate(img_original: np.ndarray, img_final: np.ndarray, steps: list[StepResult], config: PreprocessConfig, ctx: _StepContext) -> tuple[np.ndarray, QualityScore, list[StepResult]]:
    if not config.enable_validation:
        return img_final, _build_quality_score(img_final, ctx), steps

    input_quality = _build_quality_score(img_original, ctx)
    output_quality = _build_quality_score(img_final, ctx)
    threshold_ratio, _, critical = _quality_threshold_cache(config)

    if output_quality.sharpness < input_quality.sharpness * threshold_ratio:
        rollback_idx = max((i for i, s in enumerate(steps) if s.applied), default=None)
        if rollback_idx is not None:
            old = steps[rollback_idx]
            steps[rollback_idx] = replace(old, applied=False, skipped_reason="regression_rollback")
            LOGGER.warning(
                "[PREPROCESS REGRESSION — step %s degraded sharpness from %.3f to %.3f. Rolled back.]",
                old.step_name,
                input_quality.sharpness,
                output_quality.sharpness,
            )
        return img_original, _build_quality_score(img_original, ctx), steps

    if output_quality.overall < critical:
        emergency = cv2.bilateralFilter(img_final, d=9, sigmaColor=75, sigmaSpace=75)
        emergency_quality = _build_quality_score(emergency, ctx)
        if emergency_quality.overall >= critical:
            return emergency, emergency_quality, steps
        raise PreprocessQualityError(
            f"Quality score {emergency_quality.overall:.3f} below critical threshold {critical:.3f}"
        )

    return img_final, output_quality, steps


def preprocess_page(
    image: Image.Image,
    config: PreprocessConfig | None = None,
    page_number: int | None = None,
    source_file: str | None = None,
    extraction_layer: Literal["native", "surya", "paddleocr"] = "surya",
) -> PreprocessResult:
    cfg = config or PreprocessConfig()
    try:
        cfg.validate()
    except PreprocessConfigError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise PreprocessConfigError(str(exc)) from exc

    _ensure_input(image)
    start_total = _now_ms()
    steps: list[StepResult] = []
    ctx = _StepContext(
        {
            "effective_dpi": int((image.info.get("dpi") or (cfg.target_dpi, cfg.target_dpi))[0]),
            "was_upscaled": False,
            "dark_page": False,
            "low_resolution": False,
            "has_borders": False,
            "orientation_deg": 0,
            "skew_angle_deg": 0.0,
            "noise_level": 0.0,
            "contrast": 0.0,
            "human_review": False,
        }
    )

    original_size = image.size
    original_gray = np.array(image.convert("L"), dtype=np.uint8)
    current_img: np.ndarray = np.array(image)

    try:
        current_img, step = _step1_dpi_normalize(image, cfg, ctx)
        steps.append(step)
        LOGGER.debug("step=%s params=%s ms=%.3f quality_delta=%.4f", step.step_name, step.params_used, step.delta_ms, step.quality_after - step.quality_before)
        del image

        current_img, step = _step2_color_normalize(current_img, cfg, ctx)
        steps.append(step)
        LOGGER.debug("step=%s params=%s ms=%.3f quality_delta=%.4f", step.step_name, step.params_used, step.delta_ms, step.quality_after - step.quality_before)

        fast_native = extraction_layer == "native"
        if fast_native:
            for step_name in ["border_removal", "orientation", "deskew", "denoise", "contrast", "binarize"]:
                q = _laplacian_quality(current_img)
                steps.append(_step_skipped(step_name, "native_fast_path", q))
        else:
            current_img, step = _step3_border_removal(current_img, cfg, ctx)
            steps.append(step)
            LOGGER.debug("step=%s params=%s ms=%.3f quality_delta=%.4f", step.step_name, step.params_used, step.delta_ms, step.quality_after - step.quality_before)

            current_img, step = _step4_orientation(current_img, cfg, ctx)
            steps.append(step)
            LOGGER.debug("step=%s params=%s ms=%.3f quality_delta=%.4f", step.step_name, step.params_used, step.delta_ms, step.quality_after - step.quality_before)

            current_img, step = _step5_deskew(current_img, cfg, ctx)
            steps.append(step)
            LOGGER.debug("step=%s params=%s ms=%.3f quality_delta=%.4f", step.step_name, step.params_used, step.delta_ms, step.quality_after - step.quality_before)

            current_img, step = _step6_denoise(current_img, cfg, ctx)
            steps.append(step)
            LOGGER.debug("step=%s params=%s ms=%.3f quality_delta=%.4f", step.step_name, step.params_used, step.delta_ms, step.quality_after - step.quality_before)

            current_img, step = _step7_contrast(current_img, cfg, ctx)
            steps.append(step)
            LOGGER.debug("step=%s params=%s ms=%.3f quality_delta=%.4f", step.step_name, step.params_used, step.delta_ms, step.quality_after - step.quality_before)

            current_img, step = _step8_binarize(current_img, cfg, extraction_layer, ctx)
            steps.append(step)
            LOGGER.debug("step=%s params=%s ms=%.3f quality_delta=%.4f", step.step_name, step.params_used, step.delta_ms, step.quality_after - step.quality_before)

        current_img, quality, steps = _step9_validate(original_gray, current_img, steps, cfg, ctx)

        total_ms = round(_elapsed_ms(start_total), 3)
        out_pil = _np_to_pil(current_img, int(ctx.get("effective_dpi", cfg.target_dpi)))
        result = PreprocessResult(
            image=out_pil,
            original_size=original_size,
            output_size=(int(out_pil.width), int(out_pil.height)),
            quality=quality,
            steps=tuple(steps),
            total_ms=total_ms,
            was_upscaled=bool(ctx.get("was_upscaled", False)),
            effective_dpi=int(ctx.get("effective_dpi", cfg.target_dpi)),
            pipeline_version=PIPELINE_VERSION,
        )
        if quality.overall < cfg.quality_critical_threshold:
            raise PreprocessQualityError(
                f"Critical quality below threshold: {quality.overall:.3f}",
                partial_result=result,
            )
        return result
    except PreprocessQualityError as exc:
        partial = PreprocessResult(
            image=_np_to_pil(current_img if isinstance(current_img, np.ndarray) else original_gray, int(ctx.get("effective_dpi", cfg.target_dpi))),
            original_size=original_size,
            output_size=(int(current_img.shape[1]), int(current_img.shape[0])) if isinstance(current_img, np.ndarray) else original_size,
            quality=_build_quality_score(current_img if isinstance(current_img, np.ndarray) else original_gray, ctx),
            steps=tuple(steps),
            total_ms=round(_elapsed_ms(start_total), 3),
            was_upscaled=bool(ctx.get("was_upscaled", False)),
            effective_dpi=int(ctx.get("effective_dpi", cfg.target_dpi)),
            pipeline_version=PIPELINE_VERSION,
        )
        LOGGER.error("preprocess quality error page=%s source=%s error=%s", page_number, source_file, exc)
        raise PreprocessQualityError(str(exc), partial_result=partial) from exc
    except PreprocessConfigError:
        raise
    except Exception as exc:  # noqa: BLE001
        partial = PreprocessResult(
            image=_np_to_pil(original_gray, int(ctx.get("effective_dpi", cfg.target_dpi))),
            original_size=original_size,
            output_size=(int(original_gray.shape[1]), int(original_gray.shape[0])),
            quality=_build_quality_score(original_gray, ctx),
            steps=tuple(steps),
            total_ms=round(_elapsed_ms(start_total), 3),
            was_upscaled=bool(ctx.get("was_upscaled", False)),
            effective_dpi=int(ctx.get("effective_dpi", cfg.target_dpi)),
            pipeline_version=PIPELINE_VERSION,
        )
        LOGGER.error("preprocess input error page=%s source=%s error=%s", page_number, source_file, exc)
        raise PreprocessInputError(str(exc), partial_result=partial) from exc


def get_default_config_descriptions() -> dict[str, dict[str, str | int | float | bool]]:
    cfg = PreprocessConfig()
    return {
        key: {"value": value, "description": _threshold_desc(cfg).get(key, "")}
        for key, value in cfg.__dict__.items()
    }
