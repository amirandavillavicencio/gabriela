"""Whoosh index creation and search."""
from __future__ import annotations

from pathlib import Path

from whoosh import index
from whoosh.fields import ID, NUMERIC, Schema, TEXT
from whoosh.highlight import UppercaseFormatter
from whoosh.qparser import MultifieldParser


def _schema() -> Schema:
    return Schema(
        chunk_id=ID(stored=True, unique=True),
        text=TEXT(stored=True),
        page_start=NUMERIC(stored=True),
        filename=ID(stored=True),
    )


def ensure_index(index_dir: Path):
    """Create/rebuild index when missing/corrupted."""
    index_dir.mkdir(parents=True, exist_ok=True)
    try:
        if index.exists_in(index_dir):
            return index.open_dir(index_dir)
    except Exception:
        pass
    return index.create_in(index_dir, _schema())


def index_chunks(index_dir: Path, filename: str, chunks: list[dict]) -> None:
    """Index chunks for one document."""
    ix = ensure_index(index_dir)
    with ix.writer() as writer:
        for chunk in chunks:
            writer.update_document(
                chunk_id=chunk["chunk_id"],
                text=chunk["text"],
                page_start=chunk["page_start"],
                filename=filename,
            )


def search_chunks(index_dir: Path, query: str, top: int = 10, fuzzy: bool = False) -> list[dict]:
    """Search indexed chunks with phrase/boolean/fuzzy support."""
    ix = ensure_index(index_dir)
    parser = MultifieldParser(["text"], schema=ix.schema)
    query_str = query
    if fuzzy and '"' not in query and " AND " not in query and " OR " not in query and " NOT " not in query:
        query_str = " ".join(f"{term}~2" for term in query.split())
    q = parser.parse(query_str)
    with ix.searcher() as searcher:
        results = searcher.search(q, limit=top)
        results.formatter = UppercaseFormatter()
        out = []
        for row in results:
            out.append(
                {
                    "chunk_id": row["chunk_id"],
                    "filename": row["filename"],
                    "page_start": row["page_start"],
                    "score": float(row.score),
                    "snippet": row.highlights("text") or row["text"][:240],
                    "text": row["text"],
                }
            )
        return out
