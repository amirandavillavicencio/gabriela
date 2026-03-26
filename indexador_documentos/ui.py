from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from buscador import buscar_en_indice
from chunker import generar_y_guardar_chunks
from extractor_pdf import PDFExtractionError, extraer_pdf
from indexador import indexar_documento
from utils import OUTPUT_DIR, open_folder


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Indexador Judicial de PDFs")
        self.geometry("980x680")

        self.pdfs: list[Path] = []

        self.var_json = tk.BooleanVar(value=True)
        self.var_chunks = tk.BooleanVar(value=True)
        self.var_index = tk.BooleanVar(value=True)
        self.var_status = tk.StringVar(value="Listo")
        self.var_query = tk.StringVar()

        self._build_ui()

    def _build_ui(self) -> None:
        top = ttk.Frame(self, padding=10)
        top.pack(fill=tk.BOTH, expand=True)

        files_frame = ttk.LabelFrame(top, text="Documentos PDF", padding=10)
        files_frame.pack(fill=tk.X)

        controls = ttk.Frame(files_frame)
        controls.pack(fill=tk.X, pady=(0, 8))
        ttk.Button(controls, text="Seleccionar PDFs", command=self._select_pdfs).pack(side=tk.LEFT)
        ttk.Button(controls, text="Abrir carpeta salida", command=lambda: open_folder(OUTPUT_DIR)).pack(side=tk.LEFT, padx=8)

        self.listbox = tk.Listbox(files_frame, height=6)
        self.listbox.pack(fill=tk.X)

        options_frame = ttk.LabelFrame(top, text="Opciones de procesamiento", padding=10)
        options_frame.pack(fill=tk.X, pady=10)

        ttk.Checkbutton(options_frame, text="Generar JSON", variable=self.var_json).pack(side=tk.LEFT)
        ttk.Checkbutton(options_frame, text="Generar chunks", variable=self.var_chunks).pack(side=tk.LEFT, padx=12)
        ttk.Checkbutton(options_frame, text="Indexar", variable=self.var_index).pack(side=tk.LEFT)
        ttk.Button(options_frame, text="Procesar", command=self._start_process).pack(side=tk.RIGHT)

        search_frame = ttk.LabelFrame(top, text="Búsqueda", padding=10)
        search_frame.pack(fill=tk.BOTH, expand=True)

        search_controls = ttk.Frame(search_frame)
        search_controls.pack(fill=tk.X)
        ttk.Entry(search_controls, textvariable=self.var_query).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(search_controls, text="Buscar", command=self._search).pack(side=tk.LEFT, padx=8)

        self.results = tk.Text(search_frame, wrap=tk.WORD, height=18)
        self.results.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        status = ttk.Label(self, textvariable=self.var_status, relief=tk.SUNKEN, anchor=tk.W, padding=6)
        status.pack(fill=tk.X, side=tk.BOTTOM)

    def _select_pdfs(self) -> None:
        files = filedialog.askopenfilenames(filetypes=[("PDF", "*.pdf")])
        if not files:
            return
        self.pdfs = [Path(p) for p in files]
        self.listbox.delete(0, tk.END)
        for p in self.pdfs:
            self.listbox.insert(tk.END, str(p))
        self.var_status.set(f"{len(self.pdfs)} archivo(s) seleccionado(s)")

    def _start_process(self) -> None:
        if not self.pdfs:
            messagebox.showwarning("Sin archivos", "Selecciona uno o más PDFs.")
            return
        if not (self.var_json.get() or self.var_chunks.get() or self.var_index.get()):
            messagebox.showwarning("Sin acciones", "Selecciona al menos una opción de salida.")
            return
        threading.Thread(target=self._process_files, daemon=True).start()

    def _process_files(self) -> None:
        total = len(self.pdfs)
        ok = 0
        for idx, path in enumerate(self.pdfs, start=1):
            self.var_status.set(f"Procesando {idx}/{total}: {path.name}")
            try:
                doc_data = extraer_pdf(path, save_json=self.var_json.get())
                if not doc_data.get("has_extractable_text"):
                    self._append_result(f"[WARN] {path.name}: sin texto extraíble (sin OCR).\n")
                chunks = []
                if self.var_chunks.get() or self.var_index.get():
                    chunks = generar_y_guardar_chunks(doc_data)
                if self.var_index.get() and chunks:
                    stats = indexar_documento(chunks, doc_data["source_name"])
                    self._append_result(
                        f"[OK] {path.name} indexado. Local: {stats['local']['insertados']} | Global: {stats['global']['insertados']}\n"
                    )
                elif self.var_index.get() and not chunks:
                    self._append_result(f"[WARN] {path.name}: sin chunks para indexar.\n")
                ok += 1
            except (FileNotFoundError, PDFExtractionError, RuntimeError) as exc:
                self._append_result(f"[ERROR] {path.name}: {exc}\n")
            except Exception as exc:
                self._append_result(f"[ERROR] {path.name}: error inesperado: {exc}\n")

        self.var_status.set(f"Procesamiento finalizado. Correctos: {ok}/{total}")

    def _search(self) -> None:
        query = self.var_query.get().strip()
        if not query:
            messagebox.showwarning("Búsqueda vacía", "Ingresa un término o frase.")
            return
        db_path = OUTPUT_DIR / "indice_global.sqlite"
        try:
            rows = buscar_en_indice(db_path, query=query, limit=50, exact_phrase=False)
        except Exception as exc:
            messagebox.showerror("Error de búsqueda", str(exc))
            return

        self.results.delete("1.0", tk.END)
        if not rows:
            self.results.insert(tk.END, "Sin resultados.\n")
            return

        for r in rows:
            self.results.insert(
                tk.END,
                f"Documento: {r['source_name']} | Páginas: {r['page_start']}-{r['page_end']}\n"
                f"Chunk: {r['chunk_id']}\n"
                f"Fragmento: {r['snippet']}\n"
                "-" * 100 + "\n",
            )

    def _append_result(self, msg: str) -> None:
        self.results.insert(tk.END, msg)
        self.results.see(tk.END)


def run_ui() -> None:
    app = App()
    app.mainloop()
