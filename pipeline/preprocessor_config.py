from __future__ import annotations

from dataclasses import dataclass

from pipeline.preprocessor_types import PreprocessConfigError


@dataclass(unsafe_hash=True)
class PreprocessConfig:
    target_dpi: int = 300
    min_dpi: int = 150
    max_dpi: int = 600

    enable_dpi_normalize: bool = True
    enable_color_normalize: bool = True
    enable_border_removal: bool = True
    enable_orientation: bool = True
    enable_deskew: bool = True
    enable_denoise: bool = True
    enable_contrast: bool = True
    enable_binarize: bool = True
    enable_validation: bool = True

    min_skew_threshold: float = 0.3
    max_skew_threshold: float = 15.0

    denoise_tier_light_h: int = 10
    denoise_tier_medium_h: int = 15
    bilateral_d: int = 5
    bilateral_sigma_color: float = 10.0
    bilateral_sigma_space: float = 10.0

    binarization_strategy: str = "auto"
    sauvola_window_ratio: int = 50
    sauvola_k: float = 0.2
    surya_prefers_binary: bool = True

    clahe_clip_limit: float = 2.0
    clahe_tile_grid: int = 8

    use_tesseract_osd: bool = True

    quality_regression_threshold: float = 0.85
    quality_low_threshold: float = 0.65
    quality_critical_threshold: float = 0.45

    max_page_pixels: int = 25_000_000
    parallel_steps: bool = False

    def validate(self) -> None:
        if self.target_dpi <= 0 or self.min_dpi <= 0 or self.max_dpi <= 0:
            raise PreprocessConfigError("DPI values must be positive")
        if self.min_dpi >= self.max_dpi:
            raise PreprocessConfigError("min_dpi must be lower than max_dpi")
        if not (self.min_dpi <= self.target_dpi <= self.max_dpi):
            raise PreprocessConfigError("target_dpi must be between min_dpi and max_dpi")
        if self.min_skew_threshold >= self.max_skew_threshold:
            raise PreprocessConfigError("min_skew_threshold must be lower than max_skew_threshold")
        if self.min_skew_threshold < 0:
            raise PreprocessConfigError("min_skew_threshold cannot be negative")
        if self.max_skew_threshold > 45:
            raise PreprocessConfigError("max_skew_threshold should be <= 45 degrees")
        if self.quality_critical_threshold >= self.quality_low_threshold:
            raise PreprocessConfigError("quality_critical_threshold must be lower than quality_low_threshold")
        if self.quality_regression_threshold <= 0 or self.quality_regression_threshold > 1:
            raise PreprocessConfigError("quality_regression_threshold must be in (0, 1]")
        if self.quality_low_threshold <= 0 or self.quality_low_threshold > 1:
            raise PreprocessConfigError("quality_low_threshold must be in (0, 1]")
        if self.quality_critical_threshold <= 0 or self.quality_critical_threshold >= 1:
            raise PreprocessConfigError("quality_critical_threshold must be in (0, 1)")
        if self.binarization_strategy not in {"auto", "sauvola", "otsu", "niblack"}:
            raise PreprocessConfigError("binarization_strategy must be one of auto|sauvola|otsu|niblack")
        if self.sauvola_window_ratio < 5:
            raise PreprocessConfigError("sauvola_window_ratio must be >= 5")
        if self.clahe_clip_limit <= 0:
            raise PreprocessConfigError("clahe_clip_limit must be > 0")
        if self.clahe_tile_grid < 2:
            raise PreprocessConfigError("clahe_tile_grid must be >= 2")
        if self.max_page_pixels <= 0:
            raise PreprocessConfigError("max_page_pixels must be > 0")
        if self.bilateral_d <= 0:
            raise PreprocessConfigError("bilateral_d must be > 0")
