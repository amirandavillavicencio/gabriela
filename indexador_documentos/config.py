from __future__ import annotations

import os

TESSERACT_CMD = os.getenv("TESSERACT_CMD")
TESSERACT_LANG = os.getenv("TESSERACT_LANG", "spa")
OCR_DPI = int(os.getenv("OCR_DPI", "300"))
OCR_PSM = int(os.getenv("OCR_PSM", "6"))
OCR_OEM = int(os.getenv("OCR_OEM", "1"))

MIN_TEXT_CHARS_USEFUL = int(os.getenv("MIN_TEXT_CHARS_USEFUL", "80"))
MIN_WORDS_USEFUL = int(os.getenv("MIN_WORDS_USEFUL", "12"))
MAX_REPEAT_LINE_RATIO = float(os.getenv("MAX_REPEAT_LINE_RATIO", "0.7"))

CHUNK_MIN_CHARS = int(os.getenv("CHUNK_MIN_CHARS", "500"))
CHUNK_MAX_CHARS = int(os.getenv("CHUNK_MAX_CHARS", "1000"))
CHUNK_OVERLAP_CHARS = int(os.getenv("CHUNK_OVERLAP_CHARS", "120"))

SEARCH_DEFAULT_LIMIT = int(os.getenv("SEARCH_DEFAULT_LIMIT", "20"))
