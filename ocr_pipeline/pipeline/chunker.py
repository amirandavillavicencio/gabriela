from __future__ import annotations

import hashlib
import re
from typing import Iterable

from .models import ChunkRecord

SENTENCE_SPLIT_RE = re.compile(r"(?<=[\.!?])\s+")
HEADING_BREAK_RE = re.compile(r"\n\s*\n|\n(?=[A-ZÁÉÍÓÚÑ0-9\-\.:]{4,}$)")


def detect_language(text: str) -> str:
    sample = text.lower()[:1000]
    if not sample.strip():
        return "und"
    spanish_hits = sum(sample.count(token) for token in (" el ", " la ", " de ", " que ", " y "))
    english_hits = sum(sample.count(token) for token in (" the ", " and ", " of ", " to ", " is "))
    if spanish_hits > english_hits:
        return "es"
    if english_hits > spanish_hits:
        return "en"
    return "und"


def _stable_chunk_id(source_file: str, page: int, offset: int) -> str:
    payload = f"{source_file}|{page}|{offset}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:12]


def _paragraphs(text: str) -> list[str]:
    chunks = [p.strip() for p in HEADING_BREAK_RE.split(text) if p.strip()]
    return chunks if chunks else [text.strip()] if text.strip() else []


def _sentences(text: str) -> list[str]:
    raw = [s.strip() for s in SENTENCE_SPLIT_RE.split(text) if s.strip()]
    return raw if raw else [text.strip()] if text.strip() else []


def build_chunks(
    source_file: str,
    page: int,
    text: str,
    extraction_layer: str,
    ocr_confidence: float,
    bbox: list[float] | None,
    window_size: int = 5,
    step: int = 4,
) -> list[ChunkRecord]:
    paragraphs = _paragraphs(text)
    out: list[ChunkRecord] = []
    chunk_idx = 0

    for paragraph in paragraphs:
        sentences = _sentences(paragraph)
        if not sentences:
            continue

        for start in range(0, len(sentences), step):
            window = sentences[start : start + window_size]
            if not window:
                continue

            chunk_text = " ".join(window).strip()
            if not chunk_text:
                continue

            out.append(
                ChunkRecord(
                    chunk_id=_stable_chunk_id(source_file, page, chunk_idx),
                    source_file=source_file,
                    page=page,
                    text=chunk_text,
                    extraction_layer=extraction_layer,
                    ocr_confidence=ocr_confidence,
                    language_detected=detect_language(chunk_text),
                    bbox=bbox,
                    chunk_index=chunk_idx,
                    window_overlap=start > 0,
                )
            )
            chunk_idx += 1

            if start + window_size >= len(sentences):
                break

    return out


def chunks_to_dicts(chunks: Iterable[ChunkRecord]) -> list[dict]:
    return [vars(item) for item in chunks]
