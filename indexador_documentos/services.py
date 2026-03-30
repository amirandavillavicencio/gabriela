from __future__ import annotations

from pathlib import Path
from typing import Any

from indexador_documentos.buscador import buscar_en_indice
from indexador_documentos.chunker import generar_y_guardar_chunks
from indexador_documentos.extractor_pdf import extraer_pdf
from indexador_documentos.indexador import indexar_documento, reindexar_todos
from indexador_documentos.utils import INDEX_DIR, OUTPUT_DIR, SUPPORTED_EXTENSIONS, ensure_runtime_dirs, read_json


class DocumentProcessingService:
    def __init__(self, output_root: Path | None = None):
        ensure_runtime_dirs()
        self.output_root = output_root or OUTPUT_DIR

    def process_document(self, path: str | Path, force_ocr: bool = False, build_index: bool = True) -> dict[str, Any]:
        input_path = Path(path)
        if not input_path.exists() or not input_path.is_file():
            raise FileNotFoundError(f"Archivo inexistente: {input_path}")
        if input_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise ValueError(f"Extensión no soportada: {input_path.suffix}")

        doc_data = extraer_pdf(
            input_path,
            output_root=self.output_root,
            save_json=True,
            force_ocr=force_ocr,
        )
        chunks = generar_y_guardar_chunks(doc_data, output_root=self.output_root)

        index_stats: dict[str, Any] | None = None
        if build_index:
            index_stats = indexar_documento(chunks, doc_data["document_id"], output_root=self.output_root)

        return {
            "document_id": doc_data["document_id"],
            "status": "processed",
            "pages": doc_data["total_pages"],
            "chunks": len(chunks),
            "warnings": doc_data.get("warnings", []),
            "index": index_stats,
            "document": doc_data,
        }

    def list_documents(self) -> list[dict[str, Any]]:
        documents: list[dict[str, Any]] = []
        for doc_dir in sorted(self.output_root.glob("doc_*")):
            document_json = doc_dir / "extracted" / "document.json"
            if not document_json.exists():
                continue
            data = read_json(document_json)
            documents.append(
                {
                    "document_id": data.get("document_id", doc_dir.name),
                    "source_file": data.get("source_file"),
                    "processed_at": data.get("processed_at"),
                    "total_pages": data.get("total_pages"),
                    "warnings": data.get("warnings", []),
                }
            )
        return documents

    def get_document_status(self, document_id: str) -> dict[str, Any]:
        doc_json = self.output_root / document_id / "extracted" / "document.json"
        chunks_json = self.output_root / document_id / "extracted" / "chunks.json"
        return {
            "document_id": document_id,
            "document_exists": doc_json.exists(),
            "chunks_exists": chunks_json.exists(),
            "indexed_local": (self.output_root / document_id / "index" / "indice.sqlite").exists(),
        }

    def load_document_json(self, document_id: str) -> dict[str, Any]:
        path = self.output_root / document_id / "extracted" / "document.json"
        if not path.exists():
            raise FileNotFoundError(f"No existe document.json para {document_id}")
        return read_json(path)


class IndexService:
    def __init__(self, output_root: Path | None = None):
        self.output_root = output_root or OUTPUT_DIR

    def build_index(self, document_id: str | None = None) -> dict[str, Any]:
        if document_id:
            chunks_path = self.output_root / document_id / "extracted" / "chunks.json"
            if not chunks_path.exists():
                raise FileNotFoundError(f"No existe chunks.json para {document_id}")
            chunks = read_json(chunks_path)
            return indexar_documento(chunks, document_id=document_id, output_root=self.output_root)
        return reindexar_todos(output_root=self.output_root)


class SearchService:
    def __init__(self, index_root: Path | None = None):
        self.index_root = index_root or INDEX_DIR

    def search(self, query: str, limit: int = 20, exact_phrase: bool = False) -> list[dict[str, Any]]:
        db_path = self.index_root / "indice_global.sqlite"
        return buscar_en_indice(db_path, query=query, limit=limit, exact_phrase=exact_phrase)
