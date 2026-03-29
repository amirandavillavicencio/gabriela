from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)


class OCREngineError(RuntimeError):
    pass


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class HybridOCREngine:
    """Surya first, PaddleOCR fallback by low-confidence lines."""

    def __init__(self, surya_threshold: float = 0.75) -> None:
        self.surya_threshold = surya_threshold
        self._surya_reader = self._build_surya()
        self._paddle_reader = self._build_paddle()

    @staticmethod
    def _build_surya() -> Any:
        try:
            from surya.ocr import OCRPredictor

            return OCRPredictor()
        except Exception as exc:
            raise OCREngineError(
                "No se pudo inicializar Surya OCR. Instale `surya-ocr` y sus modelos locales."
            ) from exc

    @staticmethod
    def _build_paddle() -> Any:
        try:
            from paddleocr import PaddleOCR

            return PaddleOCR(use_angle_cls=True, lang="latin", show_log=False)
        except Exception as exc:
            raise OCREngineError(
                "No se pudo inicializar PaddleOCR. Instale `paddleocr` correctamente."
            ) from exc

    def extract_page(self, image_path: str | Path) -> dict[str, Any]:
        image = Path(image_path).expanduser().resolve()
        if not image.exists():
            raise FileNotFoundError(f"Imagen no encontrada para OCR: {image}")

        surya_lines = self._extract_surya_lines(image)
        final_lines: list[dict[str, Any]] = []

        for line in surya_lines:
            confidence = _safe_float(line.get("confidence"), 0.0)
            if confidence >= self.surya_threshold:
                line["extraction_layer"] = "surya"
                final_lines.append(line)
                continue

            fallback = self._extract_paddle_region(image, line.get("bbox"))
            if fallback["text"].strip():
                final_lines.append(
                    {
                        "text": fallback["text"],
                        "bbox": fallback.get("bbox") or line.get("bbox"),
                        "confidence": max(fallback["confidence"], confidence),
                        "extraction_layer": "paddleocr",
                    }
                )
            else:
                line["extraction_layer"] = "surya"
                final_lines.append(line)

        text = "\n".join(item["text"] for item in final_lines if item["text"].strip())
        confidences = [
            _safe_float(item.get("confidence"), 0.0)
            for item in final_lines
            if item.get("text", "").strip()
        ]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

        return {
            "text": text,
            "confidence": avg_conf,
            "lines": final_lines,
        }

    def _extract_surya_lines(self, image_path: Path) -> list[dict[str, Any]]:
        """Defensive adapter across Surya OCR output formats."""
        raw = self._surya_reader([str(image_path)])

        lines: list[dict[str, Any]] = []
        if isinstance(raw, list) and raw:
            first = raw[0]
            candidates = getattr(first, "lines", None) or first.get("lines", []) if isinstance(first, dict) else []
            for line in candidates:
                if isinstance(line, dict):
                    lines.append(
                        {
                            "text": line.get("text", ""),
                            "confidence": _safe_float(line.get("confidence"), 0.0),
                            "bbox": line.get("bbox"),
                        }
                    )
                else:
                    lines.append(
                        {
                            "text": getattr(line, "text", ""),
                            "confidence": _safe_float(getattr(line, "confidence", 0.0), 0.0),
                            "bbox": getattr(line, "bbox", None),
                        }
                    )

        if not lines:
            LOGGER.warning("Surya no devolvió líneas para %s", image_path)
        return lines

    def _extract_paddle_region(self, image_path: Path, bbox: Any) -> dict[str, Any]:
        # Fallback conservador: ejecuta OCR sobre la página completa. Si se desea,
        # se puede mejorar recortando por bbox cuando el formato esté normalizado.
        raw = self._paddle_reader.ocr(str(image_path), cls=True)

        texts: list[str] = []
        confs: list[float] = []
        for block in raw or []:
            for line in block or []:
                if len(line) >= 2:
                    txt, conf = line[1]
                    texts.append(txt)
                    confs.append(_safe_float(conf, 0.0))

        text = "\n".join(t for t in texts if t.strip())
        confidence = sum(confs) / len(confs) if confs else 0.0
        return {"text": text, "confidence": confidence, "bbox": bbox}
