from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from buscador import buscar_en_indice
from chunker import generar_y_guardar_chunks
from extractor_pdf import PDFExtractionError, extraer_pdf
from indexador import indexar_documento
from ui import run_ui
from utils import OUTPUT_DIR


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Indexador local de PDFs judiciales (sin OCR)")
    parser.add_argument("pdf", nargs="*", help="Ruta(s) de PDF a procesar")
    parser.add_argument("--batch", help="Carpeta con PDFs")
    parser.add_argument("--json", action="store_true", dest="save_json", help="Generar documento.json")
    parser.add_argument("--chunks", action="store_true", help="Generar chunks.json")
    parser.add_argument("--index", action="store_true", help="Generar índice local y global SQLite FTS5")
    parser.add_argument("--search", help="Buscar término/frase en indice_global.sqlite")
    parser.add_argument("--phrase", action="store_true", help="Búsqueda exacta por frase")
    parser.add_argument("--limit", type=int, default=20, help="Límite de resultados de búsqueda")
    parser.add_argument("--ui", action="store_true", help="Abrir interfaz gráfica")
    return parser


def gather_pdf_paths(args: argparse.Namespace) -> list[Path]:
    paths: list[Path] = [Path(p) for p in args.pdf]
    if args.batch:
        folder = Path(args.batch)
        if not folder.exists() or not folder.is_dir():
            raise FileNotFoundError(f"Carpeta inválida: {folder}")
        paths.extend(sorted(folder.glob("*.pdf")))
    return paths


def process_one_pdf(path: Path, save_json: bool, create_chunks: bool, create_index: bool) -> dict[str, Any]:
    doc_data = extraer_pdf(path, save_json=save_json)

    chunks: list[dict[str, Any]] = []
    if create_chunks or create_index:
        chunks = generar_y_guardar_chunks(doc_data)

    index_stats = None
    if create_index:
        if chunks:
            index_stats = indexar_documento(chunks, doc_data["source_name"])
        else:
            index_stats = {"warning": "Documento sin texto/chunks; no indexado."}

    return {"doc": doc_data, "chunks": chunks, "index": index_stats}


def run_search(query: str, limit: int, phrase: bool) -> int:
    db_path = OUTPUT_DIR / "indice_global.sqlite"
    rows = buscar_en_indice(db_path, query=query, limit=limit, exact_phrase=phrase)
    if not rows:
        print("Sin resultados.")
        return 0

    for idx, row in enumerate(rows, start=1):
        print(
            f"{idx:02d}. {row['source_name']} | páginas {row['page_start']}-{row['page_end']} | "
            f"{row['chunk_id']}\n    {row['snippet']}"
        )
    return len(rows)


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.ui:
        run_ui()
        return 0

    if args.search:
        try:
            run_search(args.search, limit=args.limit, phrase=args.phrase)
            return 0
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            print(f"[ERROR] {exc}")
            return 1

    save_json = args.save_json
    create_chunks = args.chunks
    create_index = args.index

    if not any([save_json, create_chunks, create_index]):
        save_json = True

    try:
        paths = gather_pdf_paths(args)
    except FileNotFoundError as exc:
        print(f"[ERROR] {exc}")
        return 1

    if not paths:
        parser.print_help()
        return 1

    processed = 0
    failed = 0

    for path in paths:
        try:
            if not path.exists() or not path.is_file():
                raise FileNotFoundError(f"PDF inexistente: {path}")
            result = process_one_pdf(path, save_json, create_chunks, create_index)
            doc = result["doc"]
            print(f"[OK] {doc['source_name']} | páginas: {doc['page_count']} | texto: {doc['has_extractable_text']}")
            if doc["extraction_warnings"]:
                for w in doc["extraction_warnings"]:
                    print(f"  - WARN: {w}")
            if result["index"]:
                print(f"  - Índice: {result['index']}")
            processed += 1
        except (FileNotFoundError, PDFExtractionError, RuntimeError, ValueError) as exc:
            print(f"[ERROR] {path}: {exc}")
            failed += 1
        except Exception as exc:
            print(f"[ERROR] {path}: error inesperado: {exc}")
            failed += 1

    print(f"Finalizado. Correctos: {processed} | Fallidos: {failed}")
    return 0 if processed > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
