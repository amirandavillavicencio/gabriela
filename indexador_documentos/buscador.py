from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


def _normalize_query(query: str, exact_phrase: bool) -> str:
    q = (query or "").strip()
    if not q:
        raise ValueError("La búsqueda no puede estar vacía.")
    if exact_phrase and not (q.startswith('"') and q.endswith('"')):
        return f'"{q}"'
    return q


def buscar_en_indice(db_path: str | Path, query: str, limit: int = 20, exact_phrase: bool = False) -> list[dict[str, Any]]:
    path = Path(db_path)
    if not path.exists():
        raise FileNotFoundError(f"Índice no encontrado: {path}")

    normalized_query = _normalize_query(query, exact_phrase=exact_phrase)

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row

    try:
        rows = conn.execute(
            """
            SELECT
                chunk_id,
                doc_id,
                source_name,
                page_start,
                page_end,
                chunk_index,
                extraction_layers,
                avg_confidence,
                bm25(chunks_fts) AS score,
                snippet(chunks_fts, 8, '…', '…', '...', 32) AS snippet
            FROM chunks_fts
            WHERE chunks_fts MATCH ?
            ORDER BY bm25(chunks_fts)
            LIMIT ?;
            """,
            (normalized_query, max(1, int(limit))),
        ).fetchall()
    except sqlite3.OperationalError as exc:
        raise RuntimeError(f"Error en búsqueda FTS5: {exc}") from exc
    finally:
        conn.close()

    return [
        {
            "chunk_id": row["chunk_id"],
            "document_id": row["doc_id"],
            "source_file": row["source_name"],
            "page_start": row["page_start"],
            "page_end": row["page_end"],
            "chunk_index": row["chunk_index"],
            "extraction_used": row["extraction_layers"],
            "avg_confidence": row["avg_confidence"],
            "score": row["score"],
            "snippet": row["snippet"],
        }
        for row in rows
    ]
