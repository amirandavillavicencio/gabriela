"""Main CLI/GUI entrypoint."""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

from app.config import ROOT, load_config
from app.indexer.search_index import index_chunks
from app.ocr.extractor import PDFProtectedError
from app.pipeline import process_file, run_search


def setup_logging() -> None:
    """Configure file+console logging."""
    cfg = load_config()
    level = cfg.get("logging", "level", fallback="INFO")
    logfile = ROOT / cfg.get("logging", "file", fallback="data/output/app.log")
    logfile.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(logfile, encoding="utf-8")],
    )


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser."""
    parser = argparse.ArgumentParser(description="Portable PDF OCR + chunking + búsqueda")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("process")
    p.add_argument("--input", required=True)
    p.add_argument("--lang", default="spa+eng")
    p.add_argument("--output", default="data/output")

    s = sub.add_parser("search")
    s.add_argument("--query", required=True)
    s.add_argument("--fuzzy", action="store_true")
    s.add_argument("--top", type=int, default=10)

    r = sub.add_parser("reindex")
    r.add_argument("--json", required=True)

    sub.add_parser("gui")
    return parser


def main() -> int:
    """CLI dispatcher."""
    setup_logging()
    args = build_parser().parse_args()

    if args.command == "gui" or args.command is None:
        from app.ui.gui import launch_gui
        launch_gui()
        return 0

    if args.command == "process":
        try:
            _, out = process_file(Path(args.input), language=args.lang, output_root=Path(args.output))
            print(f"JSON generado: {out}")
            return 0
        except FileNotFoundError:
            print("PDF inexistente.")
            return 1
        except PDFProtectedError as exc:
            print(str(exc))
            return 1

    if args.command == "search":
        rows = run_search(args.query, fuzzy=args.fuzzy, top=args.top)
        for row in rows:
            print(f"[{row['score']:.2f}] {row['filename']} p{row['page_start']} {row['chunk_id']}\n{row['snippet']}")
        return 0

    if args.command == "reindex":
        import json

        data = json.loads(Path(args.json).read_text(encoding="utf-8"))
        filename = data["document"]["filename"]
        index_chunks(ROOT / "data/output/index", filename, data.get("chunks", []))
        print("Reindexación completada.")
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
