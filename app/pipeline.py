"""Shared processing/search pipeline functions."""
from __future__ import annotations

import shutil
from pathlib import Path

from app.chunker.semantic_chunker import build_chunks
from app.config import ROOT, load_config
from app.exporter.json_exporter import export_document_json
from app.indexer.search_index import index_chunks, search_chunks
from app.ocr.extractor import extract_document


def process_file(pdf_path: Path, language: str | None = None, output_root: Path | None = None) -> tuple[dict, Path]:
    """Run full processing pipeline for one PDF."""
    root = output_root or (ROOT / "data/output")
    temp_dir = ROOT / "data/temp"
    cfg = load_config()
    if language:
        cfg.set("ocr", "language", language)
    payload = extract_document(pdf_path, temp_dir=temp_dir)
    chunks = build_chunks(
        payload["pages"],
        filename=pdf_path.stem,
        max_chunk_words=cfg.getint("chunking", "max_chunk_words"),
        overlap_words=cfg.getint("chunking", "overlap_words"),
        min_chunk_words=cfg.getint("chunking", "min_chunk_words"),
        strategy=cfg.get("chunking", "strategy"),
    )
    payload["chunks"] = chunks
    payload["metadata"] = {
        "total_chunks": len(chunks),
        "avg_chunk_size_words": round(sum(c["word_count"] for c in chunks) / len(chunks), 2) if chunks else 0,
        "chunking_strategy": "paragraph_sliding_window",
    }
    json_path = export_document_json(root / "json", payload)
    index_chunks(root / "index", pdf_path.name, chunks)
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)
    return payload, json_path


def run_search(query: str, fuzzy: bool = False, top: int = 10, output_root: Path | None = None) -> list[dict]:
    """Run search against persistent Whoosh index."""
    root = output_root or (ROOT / "data/output")
    return search_chunks(root / "index", query=query, top=top, fuzzy=fuzzy)
