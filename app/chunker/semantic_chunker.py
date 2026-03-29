"""Semantic chunking strategies."""
from __future__ import annotations

from typing import Iterable


def _split_paragraphs(text: str) -> list[str]:
    return [p.strip() for p in text.replace("\r\n", "\n").split("\n\n") if p.strip()]


def _sliding_words(words: list[str], chunk_size: int, overlap: int) -> Iterable[list[str]]:
    step = max(1, chunk_size - overlap)
    for start in range(0, len(words), step):
        part = words[start : start + chunk_size]
        if not part:
            break
        yield part
        if start + chunk_size >= len(words):
            break


def build_chunks(pages: list[dict], filename: str, max_chunk_words: int = 200, overlap_words: int = 50, min_chunk_words: int = 30, strategy: str = "paragraph_sliding") -> list[dict]:
    """Build chunks preserving page traceability."""
    chunks: list[dict] = []
    chunk_index = 1
    for page in pages:
        page_num = page["page_number"]
        text = page.get("clean_text", "").strip()
        if not text:
            continue

        pieces: list[str] = []
        paragraphs = _split_paragraphs(text)
        if strategy in {"paragraph_only", "paragraph_sliding"} and paragraphs:
            for p in paragraphs:
                words = p.split()
                if len(words) <= max_chunk_words:
                    pieces.append(p)
                else:
                    for part in _sliding_words(words, max_chunk_words, overlap_words):
                        pieces.append(" ".join(part))
        else:
            words = text.split()
            for part in _sliding_words(words, max_chunk_words, overlap_words):
                pieces.append(" ".join(part))

        for piece in pieces:
            wc = len(piece.split())
            if wc < min_chunk_words:
                continue
            chunk_id = f"{filename}_chunk_{chunk_index:04d}"
            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "page_start": page_num,
                    "page_end": page_num,
                    "char_start": 0,
                    "char_end": len(piece),
                    "text": piece,
                    "word_count": wc,
                    "chunk_index": chunk_index,
                }
            )
            chunk_index += 1
    return chunks
