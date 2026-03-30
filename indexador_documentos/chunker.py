from __future__ import annotations

from pathlib import Path
from typing import Any

from indexador_documentos.config import CHUNK_MAX_CHARS, CHUNK_MIN_CHARS, CHUNK_OVERLAP_CHARS
from indexador_documentos.normalizador import split_paragraphs, split_sentences
from indexador_documentos.utils import document_subdirs, write_json


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


def _overlap_tail(text: str, overlap_chars: int) -> str:
    if overlap_chars <= 0:
        return ""
    return text[-overlap_chars:].strip()


def generar_chunks(
    document_data: dict[str, Any],
    min_chars: int = CHUNK_MIN_CHARS,
    max_chars: int = CHUNK_MAX_CHARS,
    overlap_chars: int = CHUNK_OVERLAP_CHARS,
) -> list[dict[str, Any]]:
    pages = document_data.get("pages", [])
    units: list[tuple[int, str, str, float | None]] = []

    for page in pages:
        page_number = page["page_number"]
        clean_text = (page.get("text") or "").strip()
        if not clean_text:
            continue
        layer = page.get("extraction_layer", "native")
        conf = page.get("ocr_confidence")

        paragraphs = split_paragraphs(clean_text) or [clean_text]
        for p in paragraphs:
            for part in _split_by_length(p, max_chars=max_chars):
                if part.strip():
                    units.append((page_number, part.strip(), layer, conf))

    if not units:
        return []

    chunks: list[dict[str, Any]] = []
    buffer: list[tuple[int, str, str, float | None]] = []
    chunk_index = 1

    def flush(has_overlap: bool = False) -> None:
        nonlocal buffer, chunk_index
        if not buffer:
            return
        text = "\n\n".join(item[1] for item in buffer).strip()
        if not text:
            return

        pages_in_chunk = [item[0] for item in buffer]
        layers = sorted({item[2] for item in buffer})
        confidences = [item[3] for item in buffer if isinstance(item[3], (int, float))]

        chunks.append(
            {
                "chunk_id": f"{document_data['document_id']}_chunk_{chunk_index:04d}",
                "document_id": document_data["document_id"],
                "doc_id": document_data["document_id"],
                "source_file": document_data["source_file"],
                "source_name": document_data["source_file"],
                "page_start": min(pages_in_chunk),
                "page_end": max(pages_in_chunk),
                "chunk_index": chunk_index,
                "text": text,
                "text_length": len(text),
                "length": len(text),
                "extraction_layers_involved": layers,
                "avg_confidence": round(sum(confidences) / len(confidences), 4) if confidences else None,
                "has_overlap": has_overlap,
                "duplicate_flag": False,
                "metadata": {"unit_count": len(buffer)},
            }
        )
        chunk_index += 1

        overlap = _overlap_tail(text, overlap_chars)
        if overlap:
            last_page, _, last_layer, last_conf = buffer[-1]
            buffer = [(last_page, overlap, last_layer, last_conf)]
        else:
            buffer = []

    for unit in units:
        current_text = "\n\n".join(item[1] for item in buffer).strip()
        candidate = f"{current_text}\n\n{unit[1]}".strip() if current_text else unit[1]

        if current_text and len(candidate) > max_chars and len(current_text) >= min_chars:
            flush(has_overlap=bool(chunks and overlap_chars > 0))

        buffer.append(unit)
        current_len = len("\n\n".join(item[1] for item in buffer))
        if current_len >= max_chars:
            flush(has_overlap=bool(chunks and overlap_chars > 0))

    if buffer:
        flush(has_overlap=bool(chunks and overlap_chars > 0))

    return chunks


def generar_y_guardar_chunks(
    document_data: dict[str, Any],
    output_root: Path | None = None,
    min_chars: int = CHUNK_MIN_CHARS,
    max_chars: int = CHUNK_MAX_CHARS,
) -> list[dict[str, Any]]:
    chunks = generar_chunks(document_data, min_chars=min_chars, max_chars=max_chars)
    document_data["chunks"] = chunks

    subdirs = document_subdirs(document_data["document_id"], output_root)
    write_json(subdirs["extracted"] / "chunks.json", chunks)
    write_json(subdirs["extracted"] / "document.json", document_data)
    return chunks
