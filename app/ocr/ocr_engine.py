"""OCR engines wrapper (Tesseract + EasyOCR fallback)."""
from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Any

import numpy as np
import pytesseract
from PIL import Image


@dataclass
class OCRResult:
    """OCR output result for one page."""

    text: str
    confidence: float
    boxes: list[dict[str, Any]]
    engine: str


class OCREngine:
    """OCR engine with fallback strategy."""

    def __init__(self, language: str, oem: int = 3, psm: int = 6, confidence_threshold: float = 60.0):
        self.language = language
        self.oem = oem
        self.psm = psm
        self.confidence_threshold = confidence_threshold
        self._easy_reader = None

    def _run_tesseract(self, image: Image.Image) -> OCRResult:
        config = f"--oem {self.oem} --psm {self.psm}"
        data = pytesseract.image_to_data(image, lang=self.language, config=config, output_type=pytesseract.Output.DICT)
        words = []
        confidences = []
        boxes = []
        for i, txt in enumerate(data.get("text", [])):
            word = (txt or "").strip()
            conf_raw = data.get("conf", ["-1"])[i]
            conf = float(conf_raw) if str(conf_raw).strip() not in {"", "-1"} else -1.0
            if word:
                words.append(word)
                if conf >= 0:
                    confidences.append(conf)
                boxes.append(
                    {
                        "text": word,
                        "conf": conf,
                        "left": int(data["left"][i]),
                        "top": int(data["top"][i]),
                        "width": int(data["width"][i]),
                        "height": int(data["height"][i]),
                    }
                )
        confidence = mean(confidences) if confidences else 0.0
        return OCRResult(text=" ".join(words), confidence=confidence, boxes=boxes, engine="tesseract-5")

    def _run_easyocr(self, image: Image.Image) -> OCRResult:
        if self._easy_reader is None:
            import easyocr

            langs = ["es", "en"] if "+" in self.language else ["es" if "spa" in self.language else "en"]
            self._easy_reader = easyocr.Reader(langs, gpu=False)
        arr = image.convert("RGB")
        result = self._easy_reader.readtext(np.array(arr), detail=1)
        words = [row[1] for row in result if row[1].strip()]
        confs = [float(row[2]) * 100.0 for row in result]
        boxes = [{"points": row[0], "text": row[1], "conf": float(row[2]) * 100.0} for row in result]
        return OCRResult(text=" ".join(words), confidence=(mean(confs) if confs else 0.0), boxes=boxes, engine="easyocr")

    def recognize(self, image: Image.Image, allow_easyocr_fallback: bool = True) -> OCRResult:
        """Run OCR and fallback to EasyOCR when confidence is low."""
        primary = self._run_tesseract(image)
        if allow_easyocr_fallback and primary.confidence < self.confidence_threshold:
            try:
                return self._run_easyocr(image)
            except Exception:
                return primary
        return primary
