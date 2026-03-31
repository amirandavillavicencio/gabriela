from __future__ import annotations

from pathlib import Path

from whoosh import index
from whoosh.fields import ID, NUMERIC, TEXT, BOOLEAN, Schema
from whoosh.qparser import MultifieldParser, OrGroup

from .models import ChunkRecord


class WhooshIndexer:
    def __init__(self, index_dir: str | Path) -> None:
        self.index_dir = Path(index_dir).expanduser().resolve()
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.schema = Schema(
            chunk_id=ID(stored=True, unique=True),
            source_file=ID(stored=True),
            page=NUMERIC(stored=True),
            text=TEXT(stored=True),
            extraction_layer=ID(stored=True),
            ocr_confidence=NUMERIC(stored=True, decimal_places=4, signed=False),
            language_detected=ID(stored=True),
            window_overlap=BOOLEAN(stored=True),
        )
        self.ix = index.create_in(self.index_dir, self.schema) if not index.exists_in(self.index_dir) else index.open_dir(self.index_dir)

    def add_chunks(self, chunks: list[ChunkRecord]) -> int:
        added = 0
        with self.ix.writer() as writer:
            for chunk in chunks:
                writer.update_document(
                    chunk_id=chunk.chunk_id,
                    source_file=chunk.source_file,
                    page=chunk.page,
                    text=chunk.text,
                    extraction_layer=chunk.extraction_layer,
                    ocr_confidence=chunk.ocr_confidence,
                    language_detected=chunk.language_detected,
                    window_overlap=chunk.window_overlap,
                )
                added += 1
        return added

    def query(self, query_text: str, source_file: str | None = None, limit: int = 20) -> list[dict]:
        parser = MultifieldParser(["text", "source_file"], schema=self.ix.schema, group=OrGroup)
        q = parser.parse(query_text)
        out: list[dict] = []
        with self.ix.searcher() as searcher:
            results = searcher.search(q, limit=limit)
            for row in results:
                if source_file and row["source_file"] != source_file:
                    continue
                out.append(dict(row))
        return out

    def list_sources(self) -> list[str]:
        values: set[str] = set()
        with self.ix.searcher() as searcher:
            for fields in searcher.all_stored_fields():
                values.add(fields["source_file"])
        return sorted(values)
