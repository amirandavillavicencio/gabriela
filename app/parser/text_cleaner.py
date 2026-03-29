"""OCR/native text cleaning pipeline."""
from __future__ import annotations

import re

CONTROL_CHARS_RE = re.compile(r"[\x00-\x1F\x7F]")
ARTIFACT_RE = re.compile(r"[|¦]{2,}|_{2,}")
MULTI_SPACE_RE = re.compile(r"[ \t]{2,}")
MULTI_NL_RE = re.compile(r"\n{3,}")
HYPHEN_SPLIT_RE = re.compile(r"(\w+)-\n(\w+)")


def clean_text(text: str) -> str:
    """Apply OCR artifact cleanup and normalize spacing."""
    if not text:
        return ""
    cleaned = CONTROL_CHARS_RE.sub("", text)
    cleaned = HYPHEN_SPLIT_RE.sub(r"\1\2", cleaned)
    cleaned = ARTIFACT_RE.sub(" ", cleaned)
    cleaned = cleaned.replace("“", '"').replace("”", '"').replace("’", "'").replace("–", "-")
    cleaned = MULTI_SPACE_RE.sub(" ", cleaned)
    cleaned = MULTI_NL_RE.sub("\n\n", cleaned)
    return cleaned.strip()
