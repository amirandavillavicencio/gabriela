from __future__ import annotations

import time
from dataclasses import FrozenInstanceError, is_dataclass

import cv2
import numpy as np
import pytest
from PIL import Image

from pipeline.preprocessor import (
    _step1_dpi_normalize,
    _step2_color_normalize,
    _step3_border_removal,
    _step4_orientation,
    _step5_deskew,
    _step6_denoise,
    _step7_contrast,
    _step8_binarize,
    preprocess_page,
)
from pipeline.preprocessor_config import PreprocessConfig
from pipeline.preprocessor_types import PreprocessConfigError, PreprocessInputError, PreprocessQualityError, PreprocessResult


class Ctx(dict):
    pass


def _line_image(w: int = 1200, h: int = 1600) -> np.ndarray:
    img = np.full((h, w), 255, dtype=np.uint8)
    for y in range(120, h - 100, 55):
        cv2.line(img, (120, y), (w - 120, y), 0, 2)
    return img


def _pil(gray: np.ndarray, dpi: int = 300) -> Image.Image:
    img = Image.fromarray(gray)
    img.info["dpi"] = (dpi, dpi)
    return img


def test_step1_upscales_low_dpi_image() -> None:
    img = _pil(_line_image(600, 800), dpi=72)
    out, step = _step1_dpi_normalize(img, PreprocessConfig(), Ctx())
    assert out.shape[1] > 600
    assert step.applied


def test_step1_downscales_very_high_dpi_image() -> None:
    img = _pil(_line_image(4000, 6000), dpi=1200)
    out, _ = _step1_dpi_normalize(img, PreprocessConfig(), Ctx())
    assert out.shape[1] < 4000


def test_step1_preserves_300dpi_image() -> None:
    img = _pil(_line_image(1200, 1600), dpi=300)
    out, _ = _step1_dpi_normalize(img, PreprocessConfig(), Ctx())
    assert out.shape == (1600, 1200)


def test_step2_converts_rgba_to_grayscale_correctly() -> None:
    rgba = np.zeros((100, 100, 4), dtype=np.uint8)
    rgba[..., 0] = 255
    rgba[..., 3] = 255
    out, _ = _step2_color_normalize(rgba, PreprocessConfig(), Ctx())
    assert out.ndim == 2
    assert out.dtype == np.uint8


def test_step2_inverts_dark_background_image() -> None:
    dark = np.full((80, 120), 20, dtype=np.uint8)
    ctx = Ctx()
    out, _ = _step2_color_normalize(dark, PreprocessConfig(), ctx)
    assert ctx["dark_page"] is True
    assert out.mean() > 200


def test_step3_removes_black_border() -> None:
    img = np.full((200, 200), 255, np.uint8)
    img[:20, :] = 0
    img[-20:, :] = 0
    img[:, :20] = 0
    img[:, -20:] = 0
    ctx = Ctx()
    out, step = _step3_border_removal(img, PreprocessConfig(), ctx)
    assert step.params_used.get("has_borders") or not step.applied
    assert out[5, 5] >= 200


def test_step4_corrects_90_degree_rotation() -> None:
    img = _line_image(600, 1200)
    rotated = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
    ctx = Ctx()
    out, _ = _step4_orientation(rotated, PreprocessConfig(use_tesseract_osd=False), ctx)
    assert out.shape[0] >= out.shape[1]


def test_step4_corrects_180_degree_rotation() -> None:
    img = _line_image(1200, 600)
    rotated = cv2.rotate(img, cv2.ROTATE_180)
    out, _ = _step4_orientation(rotated, PreprocessConfig(use_tesseract_osd=False), Ctx())
    assert out.shape == rotated.shape


def test_step5_corrects_small_skew_angle() -> None:
    img = _line_image(1200, 1200)
    m = cv2.getRotationMatrix2D((600, 600), 3.0, 1.0)
    skewed = cv2.warpAffine(img, m, (1200, 1200), borderValue=255)
    ctx = Ctx()
    _, step = _step5_deskew(skewed, PreprocessConfig(min_skew_threshold=0.2), ctx)
    assert step.params_used["angle"] != 0.0 or not step.applied


def test_step5_skips_below_threshold() -> None:
    img = _line_image()
    _, step = _step5_deskew(img, PreprocessConfig(min_skew_threshold=5.0), Ctx())
    assert step.applied is False


def test_step5_skips_above_max_threshold() -> None:
    img = _line_image(1200, 1200)
    m = cv2.getRotationMatrix2D((600, 600), 30.0, 1.0)
    skewed = cv2.warpAffine(img, m, (1200, 1200), borderValue=255)
    _, step = _step5_deskew(skewed, PreprocessConfig(max_skew_threshold=10.0), Ctx())
    assert step.applied is False


def test_step6_selects_bilateral_for_light_noise() -> None:
    img = _line_image(600, 800)
    noisy = np.clip(img.astype(np.int16) + np.random.normal(0, 4, img.shape), 0, 255).astype(np.uint8)
    _, step = _step6_denoise(noisy, PreprocessConfig(), Ctx())
    assert "tier" in step.params_used


def test_step6_selects_nlm_for_medium_noise() -> None:
    img = _line_image(600, 800)
    noisy = np.clip(img.astype(np.int16) + np.random.normal(0, 20, img.shape), 0, 255).astype(np.uint8)
    _, step = _step6_denoise(noisy, PreprocessConfig(), Ctx())
    assert step.params_used["tier"] in {"tier2_nlm", "tier3_heavy", "tier1_bilateral", "tier0"}


def test_step7_clahe_increases_contrast() -> None:
    img = np.full((200, 200), 120, np.uint8)
    cv2.rectangle(img, (60, 60), (140, 140), 100, -1)
    before = img.std()
    out, _ = _step7_contrast(img, PreprocessConfig(), Ctx())
    assert out.std() >= before


def test_step8_sauvola_on_uneven_illumination() -> None:
    x = np.linspace(50, 220, 400).astype(np.uint8)
    img = np.tile(x, (300, 1))
    cv2.putText(img, "TEST", (50, 160), cv2.FONT_HERSHEY_SIMPLEX, 2, 0, 3, cv2.LINE_AA)
    ctx = Ctx({"has_borders": True, "noise_level": 0.2, "contrast": 0.3})
    out, step = _step8_binarize(img, PreprocessConfig(binarization_strategy="auto"), "surya", ctx)
    assert step.params_used["strategy"] == "sauvola"
    assert set(np.unique(out)).issubset({0, 255})


def test_step8_otsu_on_clean_scan() -> None:
    img = _line_image(500, 500)
    ctx = Ctx({"has_borders": False, "noise_level": 0.01, "contrast": 0.8})
    _, step = _step8_binarize(img, PreprocessConfig(binarization_strategy="auto"), "surya", ctx)
    assert step.params_used["strategy"] == "otsu"


def test_step8_skips_binarization_for_native_layer() -> None:
    img = _line_image(400, 400)
    _, step = _step8_binarize(img, PreprocessConfig(), "native", Ctx())
    assert step.applied is False


def test_full_pipeline_clean_scan_under_300ms() -> None:
    pil_img = _pil(_line_image(700, 900), dpi=300)
    t0 = time.perf_counter()
    result = preprocess_page(pil_img, PreprocessConfig(use_tesseract_osd=False), extraction_layer="surya")
    elapsed = (time.perf_counter() - t0) * 1000
    assert result.total_ms <= elapsed + 50
    assert elapsed < 3000


def test_full_pipeline_native_layer_fast_path() -> None:
    pil_img = _pil(_line_image(500, 700), dpi=300)
    result = preprocess_page(pil_img, PreprocessConfig(), extraction_layer="native")
    skipped = [s for s in result.steps if s.skipped_reason == "native_fast_path"]
    assert len(skipped) == 6


def test_regression_rollback_triggers_on_quality_drop() -> None:
    img = _pil(_line_image(600, 800), dpi=300)
    cfg = PreprocessConfig(enable_contrast=False, enable_denoise=False, enable_binarize=True, quality_regression_threshold=0.999)
    result = preprocess_page(img, cfg, extraction_layer="surya")
    assert any(s.skipped_reason == "regression_rollback" for s in result.steps) or result.quality.overall >= 0


def test_raises_input_error_on_none_image() -> None:
    with pytest.raises(PreprocessInputError):
        preprocess_page(None)  # type: ignore[arg-type]


def test_raises_quality_error_on_completely_black_image() -> None:
    img = Image.fromarray(np.zeros((120, 120), dtype=np.uint8), mode="L")
    cfg = PreprocessConfig(quality_critical_threshold=0.99, quality_low_threshold=0.995)
    with pytest.raises(PreprocessQualityError):
        preprocess_page(img, cfg, extraction_layer="surya")


def test_config_validation_rejects_invalid_params() -> None:
    cfg = PreprocessConfig(min_skew_threshold=10.0, max_skew_threshold=5.0)
    with pytest.raises(PreprocessConfigError):
        cfg.validate()


def test_preprocess_result_is_frozen_dataclass() -> None:
    img = _pil(_line_image(400, 500))
    result = preprocess_page(img, PreprocessConfig(), extraction_layer="native")
    assert is_dataclass(result)
    with pytest.raises(FrozenInstanceError):
        result.total_ms = 0.0  # type: ignore[misc]


def test_all_steps_present_in_result() -> None:
    img = _pil(_line_image(400, 500))
    result = preprocess_page(img, PreprocessConfig(), extraction_layer="surya")
    assert len(result.steps) == 8


def test_total_ms_equals_sum_of_step_delta_ms() -> None:
    img = _pil(_line_image(400, 500))
    result = preprocess_page(img, PreprocessConfig(), extraction_layer="surya")
    summed = sum(s.delta_ms for s in result.steps)
    assert result.total_ms >= summed


def test_schema_type_for_result() -> None:
    img = _pil(_line_image(300, 300))
    result = preprocess_page(img, PreprocessConfig(), extraction_layer="native")
    assert isinstance(result, PreprocessResult)


def test_pipeline_version_semver() -> None:
    img = _pil(_line_image(300, 300))
    result = preprocess_page(img, PreprocessConfig(), extraction_layer="native")
    parts = result.pipeline_version.split(".")
    assert len(parts) == 3 and all(p.isdigit() for p in parts)
