from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class PageExtraction:
    page_number: int
    text: str
    extraction_layer: str
    confidence: float
    bbox: list[float] | None = None
    language_detected: str = "und"


@dataclass
class ChunkRecord:
    chunk_id: str
    source_file: str
    page: int
    text: str
    extraction_layer: str
    ocr_confidence: float
    language_detected: str
    bbox: list[float] | None
    chunk_index: int
    window_overlap: bool


@dataclass
class PipelineResult:
    source_file: str
    pages: list[PageExtraction] = field(default_factory=list)
    chunks: list[ChunkRecord] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_file": self.source_file,
            "pages": [vars(p) for p in self.pages],
            "chunks": [vars(c) for c in self.chunks],
            "warnings": self.warnings,
        }


@dataclass
class IngestResult:
    pdf_path: Path
    native_pages: dict[int, str]
    needs_ocr_pages: list[int]
    rendered_images: dict[int, Path]
