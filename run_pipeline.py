from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
PROJECT_DIR = REPO_ROOT / "indexador_documentos"
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from chunker import generar_chunks
from extractor_pdf import PDFExtractionError, extraer_pdf
from indexador import indexar_chunks
from ocr_engine import OCRConfig
from utils import ensure_dir, utc_now_iso, write_json


LOGGER = logging.getLogger("run_pipeline")


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )


def iter_pdfs(input_dir: Path) -> list[Path]:
    pdfs = sorted(input_dir.glob("*.pdf")) + sorted(input_dir.glob("*.PDF"))
    return [p for p in pdfs if p.is_file()]


def run_batch(
    input_dir: Path,
    output_dir: Path,
    force_ocr: bool = False,
    ocr_dpi: int = 300,
    ocr_lang: str = "spa",
    ocr_fallback_lang: str | None = None,
    ocr_aggressive: bool = False,
) -> int:
    ensure_dir(output_dir)

    docs_output: list[dict] = []
    all_chunks: list[dict] = []
    failed: list[dict[str, str]] = []

    pdfs = iter_pdfs(input_dir)
    if not pdfs:
        LOGGER.error("No se encontraron PDFs en %s", input_dir)
        return 1

    for pdf in pdfs:
        try:
            ocr_cfg = OCRConfig(
                dpi=ocr_dpi,
                lang=ocr_lang,
                fallback_lang=ocr_fallback_lang,
                oem=1,
                psm=6,
                retry_psm=11,
                aggressive=ocr_aggressive,
                apply_sharpen=ocr_aggressive,
            )
            doc_data = extraer_pdf(
                pdf,
                save_json=False,
                force_ocr=force_ocr,
                ocr_aggressive=ocr_aggressive,
                ocr_config=ocr_cfg,
            )
            doc_data["source_path"] = str(pdf)
            docs_output.append(doc_data)

            chunks = generar_chunks(doc_data)
            all_chunks.extend(chunks)

            LOGGER.info(
                "Procesado %s | páginas=%s | texto=%s | chunks=%s",
                pdf.name,
                doc_data.get("page_count"),
                doc_data.get("has_extractable_text"),
                len(chunks),
            )
        except (PDFExtractionError, FileNotFoundError, ValueError, RuntimeError) as exc:
            LOGGER.exception("Error procesando %s", pdf)
            failed.append({"pdf": str(pdf), "error": str(exc)})
        except Exception as exc:
            LOGGER.exception("Error inesperado procesando %s", pdf)
            failed.append({"pdf": str(pdf), "error": f"error inesperado: {exc}"})

    documento_path = output_dir / "documento.json"
    chunks_path = output_dir / "chunks.json"
    indice_path = output_dir / "indice.sqlite"

    write_json(
        documento_path,
        {
            "generated_at": utc_now_iso(),
            "input_dir": str(input_dir),
            "total_documents": len(docs_output),
            "failed_documents": failed,
            "documents": docs_output,
        },
    )
    write_json(chunks_path, all_chunks)

    if indice_path.exists():
        indice_path.unlink()

    index_stats = indexar_chunks(all_chunks, indice_path)

    if not all_chunks:
        with sqlite3.connect(indice_path):
            pass

    LOGGER.info("documento.json: %s", documento_path)
    LOGGER.info("chunks.json: %s", chunks_path)
    LOGGER.info("indice.sqlite: %s", indice_path)
    LOGGER.info("Indexación final: %s", index_stats)

    if failed:
        LOGGER.warning("Documentos con error: %s", len(failed))

    return 0 if docs_output else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Pipeline batch para CI/GitHub Actions")
    parser.add_argument("--input-dir", default="input", help="Carpeta con PDFs de entrada")
    parser.add_argument("--output-dir", default="output", help="Carpeta de salida")
    parser.add_argument("--force-ocr", action="store_true", help="Forzar OCR aunque haya texto embebido")
    parser.add_argument("--ocr-dpi", type=int, default=300, choices=[300, 400], help="DPI OCR (300 por defecto, 400 opcional)")
    parser.add_argument("--ocr-lang", default="spa", help="Idioma OCR principal (ej: spa)")
    parser.add_argument("--ocr-fallback-lang", default=None, help="Idioma OCR fallback opcional (ej: spa+eng)")
    parser.add_argument("--ocr-aggressive", action="store_true", help="Activa preprocesado y reintentos OCR agresivos")
    return parser


def main() -> int:
    configure_logging()
    args = build_parser().parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    if not input_dir.exists() or not input_dir.is_dir():
        LOGGER.error("Carpeta de entrada inválida: %s", input_dir)
        return 1

    return run_batch(
        input_dir=input_dir,
        output_dir=output_dir,
        force_ocr=args.force_ocr,
        ocr_dpi=args.ocr_dpi,
        ocr_lang=args.ocr_lang,
        ocr_fallback_lang=args.ocr_fallback_lang,
        ocr_aggressive=args.ocr_aggressive,
    )


if __name__ == "__main__":
    raise SystemExit(main())
