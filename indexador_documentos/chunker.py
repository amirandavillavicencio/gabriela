from __future__ import annotations

from pathlib import Path
from typing import Any

from normalizador import split_paragraphs, split_sentences
from utils import document_output_dir, write_json


def _split_by_length(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]

    sentences = split_sentences(text)
    if not sentences:
        return [text[i : i + max_chars] for i in range(0, len(text), max_chars)]

    parts: list[str] = []
    current = ""
    for sentence in sentences:
        candidate = f"{current} {sentence}".strip() if current else sentence
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            parts.append(current)
        if len(sentence) > max_chars:
            parts.extend([sentence[i : i + max_chars] for i in range(0, len(sentence), max_chars)])
            current = ""
        else:
            current = sentence

    if current:
        parts.append(current)

    return parts


def generar_chunks(document_data: dict[str, Any], min_chars: int = 500, max_chars: int = 1000) -> list[dict[str, Any]]:
    pages = document_data.get("pages", [])
    units: list[tuple[int, str]] = []

    for page in pages:
        page_number = page["page_number"]
        clean_text = (page.get("clean_text") or "").strip()
        if not clean_text:
            continue
        paragraphs = split_paragraphs(clean_text)
        if not paragraphs:
            paragraphs = [clean_text]
        for p in paragraphs:
            for part in _split_by_length(p, max_chars=max_chars):
                if part.strip():
                    units.append((page_number, part.strip()))

    if not units:
        return []

    chunks: list[dict[str, Any]] = []
    buffer: list[str] = []
    page_start = units[0][0]
    page_end = units[0][0]

    def flush() -> None:
        if not buffer:
            return
        text = "\n\n".join(buffer).strip()
        if not text:
            return
        idx = len(chunks) + 1
        chunks.append(
            {
                "chunk_id": f"{document_data['id']}_chunk_{idx:04d}",
                "doc_id": document_data["id"],
                "source_name": document_data["source_name"],
                "page_start": page_start,
                "page_end": page_end,
                "text": text,
                "length": len(text),
            }
        )

    for unit_page, unit_text in units:
        current_text = "\n\n".join(buffer).strip()
        candidate = f"{current_text}\n\n{unit_text}".strip() if current_text else unit_text

        if current_text and len(candidate) > max_chars and len(current_text) >= min_chars:
            flush()
            buffer = [unit_text]
            page_start = unit_page
            page_end = unit_page
            continue

        if not buffer:
            page_start = unit_page

        buffer.append(unit_text)
        page_end = unit_page

        if len("\n\n".join(buffer)) >= max_chars:
            flush()
            buffer = []

    if buffer:
        flush()

    return chunks


def generar_y_guardar_chunks(
    document_data: dict[str, Any],
    output_root: Path | None = None,
    min_chars: int = 500,
    max_chars: int = 1000,
) -> list[dict[str, Any]]:
    chunks = generar_chunks(document_data, min_chars=min_chars, max_chars=max_chars)
    out_dir = document_output_dir(document_data["source_name"], output_root)
    write_json(out_dir / "chunks.json", chunks)
    return chunks
