from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from utils import INDEX_DIR, OUTPUT_DIR, document_output_dir, ensure_runtime_dirs


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
        doc_id = chunks[0]["doc_id"]
        _remove_doc(conn, doc_id)

        for chunk in chunks:
            try:
                conn.execute(
                    """
                    INSERT INTO chunk_store (chunk_id, doc_id, source_name, page_start, page_end, text)
                    VALUES (?, ?, ?, ?, ?, ?);
                    """,
                    (
                        chunk["chunk_id"],
                        chunk["doc_id"],
                        chunk["source_name"],
                        chunk["page_start"],
                        chunk["page_end"],
                        chunk["text"],
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO chunks_fts (chunk_id, doc_id, source_name, page_start, page_end, text)
                    VALUES (?, ?, ?, ?, ?, ?);
                    """,
                    (
                        chunk["chunk_id"],
                        chunk["doc_id"],
                        chunk["source_name"],
                        chunk["page_start"],
                        chunk["page_end"],
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


def indexar_documento(chunks: list[dict[str, Any]], source_name: str, output_root: Path | None = None) -> dict[str, Any]:
    ensure_runtime_dirs()
    out_dir = document_output_dir(source_name, output_root)
    local_db = out_dir / "indice.sqlite"
    global_db = ((output_root or OUTPUT_DIR) if output_root else INDEX_DIR) / "indice_global.sqlite"

    local_stats = indexar_chunks(chunks, local_db)
    global_stats = indexar_chunks(chunks, global_db)

    return {
        "local_db": str(local_db),
        "global_db": str(global_db),
        "local": local_stats,
        "global": global_stats,
    }
