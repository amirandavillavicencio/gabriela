from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from indexador_documentos.utils import INDEX_DIR, OUTPUT_DIR, ensure_runtime_dirs, read_json


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA temp_store=MEMORY;")
    return conn


def init_index(db_path: Path) -> None:
    conn = _connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chunk_store (
                chunk_id TEXT PRIMARY KEY,
                doc_id TEXT NOT NULL,
                source_name TEXT NOT NULL,
                page_start INTEGER NOT NULL,
                page_end INTEGER NOT NULL,
                chunk_index INTEGER,
                extraction_layers TEXT,
                avg_confidence REAL,
                text TEXT NOT NULL
            );
            """
        )
        conn.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts
            USING fts5(
                chunk_id UNINDEXED,
                doc_id UNINDEXED,
                source_name UNINDEXED,
                page_start UNINDEXED,
                page_end UNINDEXED,
                chunk_index UNINDEXED,
                extraction_layers UNINDEXED,
                avg_confidence UNINDEXED,
                text,
                tokenize='unicode61'
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


def _remove_doc(conn: sqlite3.Connection, doc_id: str) -> None:
    conn.execute("DELETE FROM chunk_store WHERE doc_id = ?;", (doc_id,))
    conn.execute("DELETE FROM chunks_fts WHERE doc_id = ?;", (doc_id,))


def indexar_chunks(chunks: list[dict[str, Any]], db_path: Path) -> dict[str, int]:
    if not chunks:
        return {"insertados": 0, "omitidos": 0}

    init_index(db_path)
    conn = _connect(db_path)

    insertados = 0
    omitidos = 0

    try:
        doc_id = chunks[0]["document_id"]
        _remove_doc(conn, doc_id)

        for chunk in chunks:
            extraction_layers = ",".join(chunk.get("extraction_layers_involved") or [])
            try:
                conn.execute(
                    """
                    INSERT INTO chunk_store
                    (chunk_id, doc_id, source_name, page_start, page_end, chunk_index, extraction_layers, avg_confidence, text)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        chunk["chunk_id"],
                        chunk["document_id"],
                        chunk["source_file"],
                        chunk["page_start"],
                        chunk["page_end"],
                        chunk.get("chunk_index"),
                        extraction_layers,
                        chunk.get("avg_confidence"),
                        chunk["text"],
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO chunks_fts
                    (chunk_id, doc_id, source_name, page_start, page_end, chunk_index, extraction_layers, avg_confidence, text)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        chunk["chunk_id"],
                        chunk["document_id"],
                        chunk["source_file"],
                        chunk["page_start"],
                        chunk["page_end"],
                        chunk.get("chunk_index"),
                        extraction_layers,
                        chunk.get("avg_confidence"),
                        chunk["text"],
                    ),
                )
                insertados += 1
            except sqlite3.IntegrityError:
                omitidos += 1

        conn.commit()
    finally:
        conn.close()

    return {"insertados": insertados, "omitidos": omitidos}


def indexar_documento(chunks: list[dict[str, Any]], document_id: str, output_root: Path | None = None) -> dict[str, Any]:
    ensure_runtime_dirs()
    docs_root = output_root or OUTPUT_DIR
    doc_root = docs_root / document_id
    local_db = doc_root / "index" / "indice.sqlite"
    global_db = INDEX_DIR / "indice_global.sqlite"

    local_db.parent.mkdir(parents=True, exist_ok=True)
    global_db.parent.mkdir(parents=True, exist_ok=True)

    local_stats = indexar_chunks(chunks, local_db)
    global_stats = indexar_chunks(chunks, global_db)

    return {
        "local_db": str(local_db),
        "global_db": str(global_db),
        "local": local_stats,
        "global": global_stats,
    }


def reindexar_todos(output_root: Path | None = None) -> dict[str, Any]:
    docs_root = output_root or OUTPUT_DIR
    global_db = INDEX_DIR / "indice_global.sqlite"
    if global_db.exists():
        global_db.unlink()
    init_index(global_db)

    total_docs = 0
    total_chunks = 0
    for doc_dir in sorted(docs_root.glob("doc_*")):
        chunks_path = doc_dir / "extracted" / "chunks.json"
        if not chunks_path.exists():
            continue
        chunks = read_json(chunks_path)
        if not chunks:
            continue
        total_docs += 1
        total_chunks += len(chunks)
        indexar_documento(chunks, doc_dir.name, output_root=docs_root)

    return {
        "documents_indexed": total_docs,
        "chunks_indexed": total_chunks,
        "global_db": str(global_db),
    }
