from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class StepResult:
    step_name: str
    applied: bool
    skipped_reason: str | None
    delta_ms: float
    params_used: dict[str, Any]
    quality_before: float
    quality_after: float


@dataclass(frozen=True)
class QualityScore:
    overall: float
    sharpness: float
    contrast: float
    noise_level: float
    skew_angle_deg: float
    orientation_deg: int
    dark_page: bool
    low_resolution: bool
    has_borders: bool
    text_density: float


@dataclass(frozen=True)
class PreprocessResult:
    image: Any
    original_size: tuple[int, int]
    output_size: tuple[int, int]
    quality: QualityScore
    steps: tuple[StepResult, ...]
    total_ms: float
    was_upscaled: bool
    effective_dpi: int
    pipeline_version: str


class PreprocessError(Exception):
    """Base exception for all preprocessor errors."""

    def __init__(self, message: str, partial_result: PreprocessResult | None = None):
        self.partial_result = partial_result
        super().__init__(message)


class PreprocessInputError(PreprocessError):
    """Raised for invalid, corrupt, or empty input images."""


class PreprocessConfigError(PreprocessError):
    """Raised for invalid parameter combinations in PreprocessConfig."""


class PreprocessQualityError(PreprocessError):
    """Raised when output quality is below critical threshold after all attempts."""
