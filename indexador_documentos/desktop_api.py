from __future__ import annotations

import threading
from pathlib import Path
from tkinter import Tk, filedialog
from typing import Any

from buscador import buscar_en_indice
from chunker import generar_y_guardar_chunks
from extractor_pdf import PDFExtractionError, extraer_pdf
from indexador import indexar_documento
from ocr_engine import OCRUnavailableError, validar_ocr_disponible
from utils import INDEX_DIR, OUTPUT_DIR, ensure_runtime_dirs, open_folder


class DesktopAPI:
    def __init__(self) -> None:
        ensure_runtime_dirs()
        self._lock = threading.Lock()
        self.state: dict[str, Any] = {
            "queue": [],
            "processed": [],
            "chunks": [],
            "flags": [],
            "logs": [],
            "progress": {"total": 0, "done": 0, "active": False},
            "metrics": {"documents": 0, "chunks": 0, "warnings": 0, "indexed": 0},
            "search_results": [],
            "selected_chunk": None,
            "theme": "dark",
        }

    def bootstrap(self) -> dict[str, Any]:
        ocr_status = self.get_ocr_status()
        return {
            "paths": {"output": str(OUTPUT_DIR), "index": str(INDEX_DIR)},
            "ocr": ocr_status,
            "state": self.get_state(),
        }

    def select_pdfs(self) -> list[str]:
        root = Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        files = filedialog.askopenfilenames(title="Seleccionar PDFs", filetypes=[("PDF", "*.pdf")])
        root.destroy()
        return [str(Path(p)) for p in files]

    def open_output_folder(self) -> bool:
        open_folder(OUTPUT_DIR)
        return True

    def open_index_folder(self) -> bool:
        open_folder(INDEX_DIR)
        return True

    def get_ocr_status(self) -> dict[str, Any]:
        try:
            cfg = validar_ocr_disponible()
            return {"available": True, "message": f"Tesseract OK ({cfg.lang})", "command": cfg.tesseract_cmd}
        except OCRUnavailableError as exc:
            return {"available": False, "message": str(exc), "command": None}

    def get_state(self) -> dict[str, Any]:
        with self._lock:
            return dict(self.state)

    def set_theme(self, theme: str) -> dict[str, Any]:
        with self._lock:
            self.state["theme"] = "light" if theme == "light" else "dark"
            return {"theme": self.state["theme"]}

    def start_processing(self, pdf_paths: list[str], options: dict[str, Any]) -> dict[str, Any]:
        unique = []
        seen = set()
        for raw in pdf_paths:
            p = str(Path(raw))
            if p not in seen:
                seen.add(p)
                unique.append(p)

        if not unique:
            return {"ok": False, "message": "No hay PDFs seleccionados."}

        with self._lock:
            if self.state["progress"]["active"]:
                return {"ok": False, "message": "Ya hay un procesamiento en ejecución."}
            self.state["queue"] = [{"path": p, "status": "queued"} for p in unique]
            self.state["processed"] = []
            self.state["chunks"] = []
            self.state["flags"] = []
            self.state["logs"] = []
            self.state["search_results"] = []
            self.state["selected_chunk"] = None
            self.state["progress"] = {"total": len(unique), "done": 0, "active": True}
            self.state["metrics"] = {"documents": 0, "chunks": 0, "warnings": 0, "indexed": 0}

        thread = threading.Thread(target=self._worker, args=(unique, options), daemon=True)
        thread.start()
        return {"ok": True, "message": "Procesamiento iniciado."}

    def _worker(self, pdf_paths: list[str], options: dict[str, Any]) -> None:
        generate_json = bool(options.get("json", True))
        generate_chunks = bool(options.get("chunks", True))
        generate_index = bool(options.get("index", True))
        force_ocr = bool(options.get("force_ocr", False))

        for idx, raw in enumerate(pdf_paths):
            path = Path(raw)
            self._set_queue_status(str(path), "processing")
            self._log(f"Procesando: {path.name}")
            try:
                doc = extraer_pdf(path, output_root=OUTPUT_DIR, save_json=generate_json, force_ocr=force_ocr)
                chunks = []
                if generate_chunks or generate_index:
                    chunks = generar_y_guardar_chunks(doc, output_root=OUTPUT_DIR)
                index_stats = None
                if generate_index and chunks:
                    index_stats = indexar_documento(chunks, doc["source_name"], output_root=OUTPUT_DIR)

                flags = doc.get("extraction_warnings", [])
                processed_item = {
                    "source_name": doc["source_name"],
                    "page_count": doc["page_count"],
                    "has_extractable_text": doc["has_extractable_text"],
                    "ocr_pages": doc.get("ocr_pages", 0),
                    "embedded_text_pages": doc.get("embedded_text_pages", 0),
                    "chunks_count": len(chunks),
                    "index_stats": index_stats,
                    "flags": flags,
                    "pages": [
                        {
                            "page_number": p["page_number"],
                            "has_text": p["has_text"],
                            "text_source": p["text_source"],
                            "clean_text": p.get("clean_text", "")[:260],
                        }
                        for p in doc.get("pages", [])
                    ],
                    "chunks": chunks[:200],
                }
                with self._lock:
                    self.state["processed"].append(processed_item)
                    self.state["chunks"].extend(chunks)
                    self.state["flags"].extend({"doc": doc["source_name"], "message": f} for f in flags)
                    self.state["progress"]["done"] = idx + 1
                    self.state["metrics"]["documents"] = len(self.state["processed"])
                    self.state["metrics"]["chunks"] = len(self.state["chunks"])
                    self.state["metrics"]["warnings"] = len(self.state["flags"])
                    self.state["metrics"]["indexed"] = sum(1 for d in self.state["processed"] if d.get("index_stats"))
                self._set_queue_status(str(path), "done")
            except (FileNotFoundError, PDFExtractionError, RuntimeError, ValueError) as exc:
                self._set_queue_status(str(path), "error")
                self._flag(path.name, str(exc))
                with self._lock:
                    self.state["progress"]["done"] = idx + 1
            except Exception as exc:
                self._set_queue_status(str(path), "error")
                self._flag(path.name, f"Error inesperado: {exc}")
                with self._lock:
                    self.state["progress"]["done"] = idx + 1

        with self._lock:
            self.state["progress"]["active"] = False
        self._log("Procesamiento finalizado.")

    def search(self, query: str, limit: int = 20, phrase: bool = False) -> dict[str, Any]:
        try:
            rows = buscar_en_indice(INDEX_DIR / "indice_global.sqlite", query=query, limit=max(1, int(limit)), exact_phrase=phrase)
        except Exception as exc:
            return {"ok": False, "message": str(exc), "rows": []}

        with self._lock:
            self.state["search_results"] = rows
            self.state["selected_chunk"] = rows[0] if rows else None
        return {"ok": True, "rows": rows, "message": f"{len(rows)} resultados"}

    def select_chunk(self, chunk_id: str) -> dict[str, Any]:
        with self._lock:
            for c in self.state.get("chunks", []):
                if c.get("chunk_id") == chunk_id:
                    self.state["selected_chunk"] = c
                    return {"ok": True, "chunk": c}
        return {"ok": False, "message": "Chunk no encontrado."}

    def _set_queue_status(self, path: str, status: str) -> None:
        with self._lock:
            for item in self.state["queue"]:
                if item["path"] == path:
                    item["status"] = status
                    return

    def _log(self, message: str) -> None:
        with self._lock:
            self.state["logs"].append(message)

    def _flag(self, doc_name: str, message: str) -> None:
        with self._lock:
            self.state["flags"].append({"doc": doc_name, "message": message})
            self.state["metrics"]["warnings"] = len(self.state["flags"])
