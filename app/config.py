"""Application configuration loader."""
from __future__ import annotations

from configparser import ConfigParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config.ini"


def load_config() -> ConfigParser:
    """Load config.ini with sane defaults if missing values."""
    parser = ConfigParser()
    parser.read_dict(
        {
            "ocr": {
                "language": "spa+eng",
                "dpi": "300",
                "tesseract_oem": "3",
                "tesseract_psm": "6",
                "fallback_easyocr": "true",
                "confidence_threshold": "60",
            },
            "chunking": {
                "max_chunk_words": "200",
                "overlap_words": "50",
                "min_chunk_words": "30",
                "strategy": "paragraph_sliding",
            },
            "logging": {
                "level": "INFO",
                "file": "data/output/app.log",
            },
        }
    )
    if CONFIG_PATH.exists():
        parser.read(CONFIG_PATH, encoding="utf-8")
    return parser
