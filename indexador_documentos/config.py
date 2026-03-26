from __future__ import annotations

import os

TESSERACT_CMD = os.getenv("TESSERACT_CMD", r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe")
TESSERACT_LANG = os.getenv("TESSERACT_LANG", "spa")
OCR_DPI = int(os.getenv("OCR_DPI", "300"))
OCR_PSM = int(os.getenv("OCR_PSM", "6"))
OCR_OEM = int(os.getenv("OCR_OEM", "1"))

MIN_TEXT_CHARS_USEFUL = int(os.getenv("MIN_TEXT_CHARS_USEFUL", "80"))
MIN_WORDS_USEFUL = int(os.getenv("MIN_WORDS_USEFUL", "12"))
MAX_REPEAT_LINE_RATIO = float(os.getenv("MAX_REPEAT_LINE_RATIO", "0.7"))
