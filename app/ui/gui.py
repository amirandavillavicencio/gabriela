"""Tkinter desktop interface."""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

from app.pipeline import process_file, run_search


class AppGUI:
    """Desktop GUI with processing and search panels."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("PDF OCR + Chunking + Búsqueda")
        self.selected_pdf: Path | None = None
        self.last_json: Path | None = None
        self._build()

    def _build(self) -> None:
        main = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        main.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(main, padding=8)
        right = ttk.Frame(main, padding=8)
        main.add(left, weight=1)
        main.add(right, weight=1)

        ttk.Button(left, text="Cargar PDF", command=self.load_pdf).pack(fill=tk.X)
        self.lang = tk.StringVar(value="spa+eng")
        ttk.Combobox(left, textvariable=self.lang, values=["spa", "eng", "spa+eng"], state="readonly").pack(fill=tk.X, pady=6)
        ttk.Button(left, text="Procesar", command=self.process).pack(fill=tk.X)
        self.progress_label = ttk.Label(left, text="Estado: esperando")
        self.progress_label.pack(fill=tk.X, pady=6)
        self.log = tk.Text(left, height=18)
        self.log.pack(fill=tk.BOTH, expand=True)
        ttk.Button(left, text="Ver JSON generado", command=self.open_json).pack(fill=tk.X, pady=6)

        self.query = tk.StringVar()
        entry = ttk.Entry(right, textvariable=self.query)
        entry.insert(0, "Busca en el documento…")
        entry.pack(fill=tk.X)
        entry.bind("<Return>", lambda _: self.search())
        self.fuzzy = tk.BooleanVar(value=True)
        ttk.Checkbutton(right, text="Búsqueda fuzzy", variable=self.fuzzy).pack(anchor="w")
        ttk.Button(right, text="Buscar", command=self.search).pack(fill=tk.X, pady=6)
        self.results = tk.Listbox(right, height=14)
        self.results.pack(fill=tk.BOTH, expand=True)
        self.results.bind("<<ListboxSelect>>", self.show_chunk)

        self.chunk_view = tk.Text(right, height=10)
        self.chunk_view.pack(fill=tk.BOTH, expand=True, pady=6)
        self.chunk_meta = ttk.Label(right, text="página/chunk/palabras")
        self.chunk_meta.pack(fill=tk.X)

        self._hits: list[dict] = []

    def _append_log(self, message: str) -> None:
        self.log.insert(tk.END, f"{message}\n")
        self.log.see(tk.END)

    def load_pdf(self) -> None:
        selected = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")])
        if selected:
            self.selected_pdf = Path(selected)
            self._append_log(f"PDF cargado: {self.selected_pdf}")

    def process(self) -> None:
        if not self.selected_pdf:
            self._append_log("Selecciona un PDF primero.")
            return
        self.progress_label.config(text="Procesando...")
        payload, out_path = process_file(self.selected_pdf, language=self.lang.get())
        self.last_json = out_path
        self.progress_label.config(text=f"Procesado {payload['document']['total_pages']} páginas")
        self._append_log(f"JSON generado: {out_path}")

    def open_json(self) -> None:
        if self.last_json and self.last_json.exists():
            self._append_log(str(self.last_json))
        else:
            self._append_log("No hay JSON generado todavía.")

    def search(self) -> None:
        q = self.query.get().strip()
        if not q or q == "Busca en el documento…":
            self._append_log("Consulta vacía.")
            return
        self._hits = run_search(q, fuzzy=self.fuzzy.get())
        self.results.delete(0, tk.END)
        for i, row in enumerate(self._hits, start=1):
            self.results.insert(tk.END, f"{i}. p{row['page_start']} | {row['score']:.2f} | {row['snippet'][:90]}")

    def show_chunk(self, _event=None) -> None:
        if not self.results.curselection():
            return
        idx = self.results.curselection()[0]
        item = self._hits[idx]
        self.chunk_view.delete("1.0", tk.END)
        self.chunk_view.insert(tk.END, item["text"])
        self.chunk_meta.config(text=f"Página {item['page_start']} | {item['chunk_id']} | {len(item['text'].split())} palabras")


def launch_gui() -> None:
    """Start Tkinter GUI."""
    root = tk.Tk()
    root.geometry("1200x700")
    AppGUI(root)
    root.mainloop()
