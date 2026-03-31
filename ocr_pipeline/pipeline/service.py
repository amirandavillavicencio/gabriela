from __future__ import annotations

import json
import logging
from pathlib import Path

from .chunker import build_chunks
from .extractor import PDFExtractor
from .indexer import WhooshIndexer
from .models import PageExtraction, PipelineResult
from .ocr_engine import HybridOCREngine, OCREngineError

LOGGER = logging.getLogger(__name__)


class OCRPipelineService:
    def __init__(
        self,
        image_dir: str | Path,
        index_dir: str | Path,
        artifacts_dir: str | Path,
        native_char_threshold: int = 120,
        surya_threshold: float = 0.75,
    ) -> None:
        self.extractor = PDFExtractor(native_char_threshold=native_char_threshold)
        self.indexer = WhooshIndexer(index_dir=index_dir)
        self.image_dir = Path(image_dir)
        self.artifacts_dir = Path(artifacts_dir)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        try:
            self.ocr_engine = HybridOCREngine(surya_threshold=surya_threshold)
        except OCREngineError as exc:
            LOGGER.warning("OCR engine unavailable at startup: %s", exc)
            self.ocr_engine = None

    def process_pdf(self, pdf_path: str | Path) -> PipelineResult:
        ingest = self.extractor.ingest(pdf_path, self.image_dir)
        source_name = ingest.pdf_path.name

        result = PipelineResult(source_file=source_name)

        for page_num, native_text in ingest.native_pages.items():
            if page_num not in ingest.needs_ocr_pages and native_text.strip():
                page_obj = PageExtraction(
                    page_number=page_num,
                    text=native_text,
                    extraction_layer="native",
                    confidence=1.0,
                    bbox=None,
                )
                result.pages.append(page_obj)
                result.chunks.extend(
                    build_chunks(
                        source_file=source_name,
                        page=page_num,
                        text=native_text,
                        extraction_layer="native",
                        ocr_confidence=1.0,
                        bbox=None,
                    )
                )
                continue

            image_path = ingest.rendered_images.get(page_num)
            if not image_path:
                result.warnings.append(f"Página {page_num}: sin imagen para OCR")
                continue
            if self.ocr_engine is None:
                result.warnings.append("Motor OCR no disponible para páginas escaneadas")
                continue

            ocr_data = self.ocr_engine.extract_page(image_path)
            final_text = ocr_data["text"].strip() or native_text
            final_conf = float(ocr_data["confidence"] or 0.0)
            layer = "surya"
            if any(line.get("extraction_layer") == "paddleocr" for line in ocr_data.get("lines", [])):
                layer = "paddleocr"

            page_obj = PageExtraction(
                page_number=page_num,
                text=final_text,
                extraction_layer=layer,
                confidence=final_conf,
                bbox=None,
            )
            result.pages.append(page_obj)
            result.chunks.extend(
                build_chunks(
                    source_file=source_name,
                    page=page_num,
                    text=final_text,
                    extraction_layer=layer,
                    ocr_confidence=final_conf,
                    bbox=None,
                )
            )

        self.indexer.add_chunks(result.chunks)
        self._persist_artifacts(ingest.pdf_path, result)
        return result

    def search(self, query: str, source_file: str | None = None, limit: int = 20) -> list[dict]:
        return self.indexer.query(query_text=query, source_file=source_file, limit=limit)

    def status(self) -> dict:
        return {
            "ok": True,
            "indexed_sources": self.indexer.list_sources(),
        }

    def _persist_artifacts(self, pdf_path: Path, result: PipelineResult) -> None:
        stem = pdf_path.stem
        out_dir = self.artifacts_dir / stem
        out_dir.mkdir(parents=True, exist_ok=True)

        payload = result.as_dict()
        with (out_dir / "chunks.json").open("w", encoding="utf-8") as fh:
            json.dump(payload["chunks"], fh, ensure_ascii=False, indent=2)
        with (out_dir / "document.json").open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
