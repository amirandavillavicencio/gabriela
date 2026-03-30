from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from indexador_documentos.config import SEARCH_DEFAULT_LIMIT
from indexador_documentos.services import DocumentProcessingService, IndexService, SearchService
from indexador_documentos.utils import OUTPUT_DIR, ensure_runtime_dirs


def log(level: str, message: str) -> None:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    print(f"[{timestamp}] [{level}] {message}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Backend local de procesamiento documental (PDF -> JSON -> chunks -> índice -> búsqueda)")
    subparsers = parser.add_subparsers(dest="command")

    process = subparsers.add_parser("process", help="Procesar un PDF")
    process.add_argument("file", help="Ruta del PDF")
    process.add_argument("--force-ocr", action="store_true", help="Forzar OCR aunque haya texto nativo")
    process.add_argument("--no-index", action="store_true", help="No indexar al finalizar")

    search = subparsers.add_parser("search", help="Buscar en índice global")
    search.add_argument("query", help="Consulta de texto")
    search.add_argument("--phrase", action="store_true", help="Búsqueda por frase exacta")
    search.add_argument("--limit", type=int, default=SEARCH_DEFAULT_LIMIT, help="Cantidad máxima de resultados")

    reindex = subparsers.add_parser("reindex", help="Reindexar documentos procesados")
    reindex.add_argument("--document-id", help="Reindexar solo un documento")

    subparsers.add_parser("list-docs", help="Listar documentos procesados")

    status = subparsers.add_parser("status", help="Estado de un documento")
    status.add_argument("document_id", help="ID del documento")

    parser.add_argument("--output-dir", help="Directorio base de documentos procesados")
    return parser


def main() -> int:
    ensure_runtime_dirs()
    parser = build_parser()
    args = parser.parse_args()

    output_root = Path(args.output_dir) if args.output_dir else OUTPUT_DIR

    processing_service = DocumentProcessingService(output_root=output_root)
    index_service = IndexService(output_root=output_root)
    search_service = SearchService()

    if args.command == "process":
        result = processing_service.process_document(args.file, force_ocr=args.force_ocr, build_index=not args.no_index)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "search":
        results = search_service.search(args.query, limit=args.limit, exact_phrase=args.phrase)
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0

    if args.command == "reindex":
        result = index_service.build_index(document_id=args.document_id)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "list-docs":
        docs = processing_service.list_documents()
        print(json.dumps(docs, ensure_ascii=False, indent=2))
        return 0

    if args.command == "status":
        status = processing_service.get_document_status(args.document_id)
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
