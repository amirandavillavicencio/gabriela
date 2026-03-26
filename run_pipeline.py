from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Permite reutilizar la lógica existente sin convertir el proyecto en paquete.
REPO_ROOT = Path(__file__).resolve().parent
MODULES_DIR = REPO_ROOT / "indexador_documentos"
if str(MODULES_DIR) not in sys.path:
    sys.path.insert(0, str(MODULES_DIR))

from chunker import generar_y_guardar_chunks
from extractor_pdf import PDFExtractionError, extraer_pdf
from indexador import indexar_documento


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Pipeline batch OCR para procesar PDFs de input/ y generar resultados en output/"
    )
    parser.add_argument("--input-dir", default="input", help="Carpeta de entrada con PDFs")
    parser.add_argument("--output-dir", default="output", help="Carpeta de salida para JSON/chunks/índices")
    parser.add_argument("--force-ocr", action="store_true", help="Forzar OCR incluso si hay texto embebido útil")
    return parser


def collect_pdfs(input_dir: Path) -> list[Path]:
    return sorted([p for p in input_dir.glob("*.pdf") if p.is_file()])


def process_pdf(pdf_path: Path, output_dir: Path, force_ocr: bool = False) -> dict[str, object]:
    doc_data = extraer_pdf(
        pdf_path,
        output_root=output_dir,
        save_json=True,
        force_ocr=force_ocr,
    )
    chunks = generar_y_guardar_chunks(doc_data, output_root=output_dir)
    index_stats = indexar_documento(chunks, doc_data["source_name"], output_root=output_dir)
    return {"doc": doc_data, "chunks": chunks, "index": index_stats}


def main() -> int:
    args = build_parser().parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    print(f"[INFO] Input: {input_dir.resolve()}")
    print(f"[INFO] Output: {output_dir.resolve()}")

    if not input_dir.exists() or not input_dir.is_dir():
        print(f"[ERROR] Carpeta de entrada inválida: {input_dir}")
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)

    pdfs = collect_pdfs(input_dir)
    if not pdfs:
        print(f"[ERROR] No se encontraron PDFs en: {input_dir}")
        return 1

    ok_count = 0
    fail_count = 0

    for pdf in pdfs:
        print(f"\n[INFO] Procesando: {pdf.name}")
        try:
            result = process_pdf(pdf, output_dir=output_dir, force_ocr=args.force_ocr)
            doc = result["doc"]
            chunks = result["chunks"]
            print(
                "[OK] "
                f"{doc['source_name']} | páginas: {doc['page_count']} | "
                f"ocr_usado: {doc['ocr_used']} | chunks: {len(chunks)}"
            )
            warnings = doc.get("extraction_warnings", [])
            for warning in warnings:
                print(f"  - WARN: {warning}")
            ok_count += 1
        except (FileNotFoundError, PDFExtractionError, RuntimeError, ValueError) as exc:
            print(f"[ERROR] {pdf}: {exc}")
            fail_count += 1
        except Exception as exc:
            print(f"[ERROR] {pdf}: error inesperado: {exc}")
            fail_count += 1

    print("\n[INFO] Pipeline finalizado")
    print(f"[INFO] Correctos: {ok_count}")
    print(f"[INFO] Fallidos: {fail_count}")
    print(f"[INFO] Salida disponible en: {output_dir.resolve()}")

    return 0 if ok_count > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
