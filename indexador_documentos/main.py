from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from buscador import buscar_en_indice
from chunker import generar_y_guardar_chunks
from extractor_pdf import PDFExtractionError, extraer_pdf
from indexador import indexar_documento
from ui import run_ui
from utils import OUTPUT_DIR


def log(level: str, message: str) -> None:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    print(f"[{timestamp}] [{level}] {message}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Indexador local de PDFs judiciales (híbrido: texto embebido + OCR)")
    parser.add_argument("pdf", nargs="*", help="Ruta(s) de PDF a procesar")
    parser.add_argument("--batch", help="Carpeta con PDFs")
    parser.add_argument("--input-dir", help="Alias de --batch para ejecución en CI")
    parser.add_argument("--output-dir", help="Carpeta de salida (por defecto: salida)")
    parser.add_argument("--json", action="store_true", dest="save_json", help="Generar documento.json")
    parser.add_argument("--chunks", action="store_true", help="Generar chunks.json")
    parser.add_argument("--index", action="store_true", help="Generar índice local y global SQLite FTS5")
    parser.add_argument("--search", help="Buscar término/frase en indice_global.sqlite")
    parser.add_argument("--phrase", action="store_true", help="Búsqueda exacta por frase")
    parser.add_argument("--limit", type=int, default=20, help="Límite de resultados de búsqueda")
    parser.add_argument("--ui", action="store_true", help="Abrir interfaz gráfica")
    parser.add_argument("--force-ocr", action="store_true", help="Forzar OCR por página aunque exista texto embebido")
    return parser


def gather_pdf_paths(args: argparse.Namespace) -> list[Path]:
    paths: list[Path] = [Path(p) for p in args.pdf]

    batch_dir = args.batch or args.input_dir
    if batch_dir:
        folder = Path(batch_dir)
        if not folder.exists() or not folder.is_dir():
            raise FileNotFoundError(f"Carpeta inválida: {folder}")
        pdfs = sorted(folder.glob("*.pdf")) + sorted(folder.glob("*.PDF"))
        if not pdfs:
            log("WARN", f"No se encontraron PDFs en carpeta batch: {folder}")
        paths.extend(pdfs)

    unique_paths: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        key = path.resolve() if path.exists() else path
        if key in seen:
            continue
        seen.add(key)
        unique_paths.append(path)

    return unique_paths


def validate_output_root(raw_output_dir: str | None) -> Path:
    output_root = Path(raw_output_dir) if raw_output_dir else OUTPUT_DIR
    if output_root.exists() and not output_root.is_dir():
        raise ValueError(f"Ruta de salida inválida (no es carpeta): {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    return output_root


def validate_input_path(path: Path) -> None:
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"PDF inexistente: {path}")
    if path.suffix.lower() != ".pdf":
        raise ValueError(f"Archivo no PDF: {path}")


def process_one_pdf(
    path: Path,
    save_json: bool,
    create_chunks: bool,
    create_index: bool,
    force_ocr: bool = False,
    output_root: Path | None = None,
) -> dict[str, Any]:
    doc_data = extraer_pdf(path, output_root=output_root, save_json=save_json, force_ocr=force_ocr)

    chunks: list[dict[str, Any]] = []
    if create_chunks or create_index:
        chunks = generar_y_guardar_chunks(doc_data, output_root=output_root)

    index_stats = None
    if create_index:
        if chunks:
            index_stats = indexar_documento(chunks, doc_data["source_name"], output_root=output_root)
        else:
            index_stats = {"warning": "Documento sin texto/chunks; no indexado."}

    return {"doc": doc_data, "chunks": chunks, "index": index_stats}


def run_search(query: str, limit: int, phrase: bool, output_root: Path | None = None) -> int:
    db_path = (output_root or OUTPUT_DIR) / "indice_global.sqlite"
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
    try:
        output_root = validate_output_root(args.output_dir)
    except ValueError as exc:
        log("ERROR", str(exc))
        return 1

    if args.ui:
        log("INFO", "Iniciando interfaz gráfica.")
        run_ui()
        return 0

    if args.search:
        try:
            log("INFO", f"Ejecutando búsqueda (phrase={args.phrase}, limit={args.limit}).")
            run_search(args.search, limit=args.limit, phrase=args.phrase, output_root=output_root)
            return 0
        except (FileNotFoundError, ValueError, RuntimeError) as exc:
            log("ERROR", str(exc))
            return 1

    save_json = args.save_json
    create_chunks = args.chunks
    create_index = args.index

    if not any([save_json, create_chunks, create_index]):
        save_json = True

    try:
        paths = gather_pdf_paths(args)
    except FileNotFoundError as exc:
        log("ERROR", str(exc))
        return 1

    if not paths:
        log("WARN", "No se recibieron rutas de entrada. No hay nada para procesar.")
        log("INFO", "Finalizado. Correctos: 0 | Fallidos: 0")
        return 0

    processed = 0
    failed = 0

    for path in paths:
        try:
            validate_input_path(path)
            log("INFO", f"Procesando: {path}")
            result = process_one_pdf(
                path,
                save_json,
                create_chunks,
                create_index,
                force_ocr=args.force_ocr,
                output_root=output_root,
            )
            doc = result["doc"]
            log(
                "OK",
                f"{doc['source_name']} | páginas: {doc['page_count']} | texto_extraible: {doc['has_extractable_text']}",
            )
            if doc["extraction_warnings"]:
                for w in doc["extraction_warnings"]:
                    log("WARN", w)
            if result["index"]:
                log("INFO", f"Índice: {result['index']}")
            processed += 1
        except (FileNotFoundError, PDFExtractionError, RuntimeError, ValueError) as exc:
            log("ERROR", f"{path}: {exc}")
            failed += 1
        except Exception as exc:
            log("ERROR", f"{path}: error inesperado: {exc}")
            failed += 1

    status = "OK" if failed == 0 else "WARN"
    log(status, f"Finalizado. Correctos: {processed} | Fallidos: {failed}")
    return 0 if processed > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
