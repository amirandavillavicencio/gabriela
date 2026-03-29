from __future__ import annotations

import html
import io
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import fitz
from PIL import Image

MAX_RESULTS = 100
_PREVIEW_DPI = 130


def _safe_import_gradio():
    try:
        import gradio as gr
    except ImportError as exc:  # pragma: no cover - depende del entorno
        raise RuntimeError(
            "Gradio no está instalado. Ejecuta: pip install gradio"
        ) from exc
    return gr


def _render_page(page: fitz.Page, dpi: int = _PREVIEW_DPI) -> Image.Image:
    pix = page.get_pixmap(dpi=dpi, alpha=False)
    return Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")


def _render_page_with_highlights(page: fitz.Page, query: str, dpi: int = _PREVIEW_DPI) -> Image.Image:
    for rect in page.search_for(query):
        annot = page.add_highlight_annot(rect)
        annot.update()
    return _render_page(page, dpi=dpi)


def _extract_pages(pdf_path: Path) -> list[str]:
    with fitz.open(pdf_path) as doc:
        return [page.get_text("text") or "" for page in doc]


def _build_context(text: str, query: str, window: int = 180) -> str:
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    match = pattern.search(text)
    if not match:
        return html.escape(text[:window]).replace("\n", " ")

    start = max(0, match.start() - window // 2)
    end = min(len(text), match.end() + window // 2)
    context = text[start:end]

    escaped_query = html.escape(match.group(0))
    escaped_context = html.escape(context)
    highlighted = re.sub(re.escape(escaped_query), f"<mark>{escaped_query}</mark>", escaped_context, count=1, flags=re.IGNORECASE)
    return highlighted.replace("\n", " ")


def _search_in_pages(pages: list[str], query: str) -> list[dict[str, Any]]:
    q = (query or "").strip()
    if not q:
        raise ValueError("La búsqueda no puede estar vacía.")

    pattern = re.compile(re.escape(q), re.IGNORECASE)
    results: list[dict[str, Any]] = []

    for idx, text in enumerate(pages, start=1):
        occurrences = len(pattern.findall(text))
        if occurrences == 0:
            continue
        results.append(
            {
                "result_id": len(results) + 1,
                "page": idx,
                "matches": occurrences,
                "context": _build_context(text, q),
            }
        )
        if len(results) >= MAX_RESULTS:
            break

    return results


def run_gradio_ui(server_name: str = "127.0.0.1", server_port: int = 7860) -> None:
    gr = _safe_import_gradio()

    with TemporaryDirectory(prefix="indexador_gradio_") as tmp_dir:
        temp_root = Path(tmp_dir)

        def load_pdf(pdf_file: Any):
            if not pdf_file:
                return None, "", [], None, gr.update(choices=[], value=None)

            src = Path(pdf_file)
            dst = temp_root / src.name
            dst.write_bytes(src.read_bytes())

            with fitz.open(dst) as doc:
                first_preview = _render_page(doc[0]) if doc.page_count else None
                info = f"Documento: {dst.name} | páginas: {doc.page_count}"

            pages = _extract_pages(dst)
            state = {
                "pdf_path": str(dst),
                "pages": pages,
                "results": [],
            }

            return first_preview, info, state, 1, gr.update(choices=[], value=None)

        def preview_page(page_number: int, state: dict[str, Any]):
            if not state or not state.get("pdf_path"):
                return None
            pdf_path = Path(state["pdf_path"])
            with fitz.open(pdf_path) as doc:
                index = max(0, min((page_number or 1) - 1, doc.page_count - 1))
                return _render_page(doc[index])

        def search_query(query: str, state: dict[str, Any]):
            if not state or not state.get("pdf_path"):
                return "Carga un PDF primero.", [], None, gr.update(choices=[], value=None), state

            try:
                results = _search_in_pages(state["pages"], query)
            except ValueError as exc:
                return str(exc), [], None, gr.update(choices=[], value=None), state

            state["results"] = results
            if not results:
                return "Sin resultados.", [], None, gr.update(choices=[], value=None), state

            table = [[r["result_id"], r["page"], r["matches"], r["context"]] for r in results]
            choices = [f"#{r['result_id']} | pág. {r['page']} | matches: {r['matches']}" for r in results]

            first = results[0]
            with fitz.open(state["pdf_path"]) as doc:
                highlighted = _render_page_with_highlights(doc[first["page"] - 1], query)

            return (
                f"Resultados: {len(results)}",
                table,
                highlighted,
                gr.update(choices=choices, value=choices[0]),
                state,
            )

        def show_selected_highlight(selection: str, query: str, state: dict[str, Any]):
            if not selection or not state or not state.get("results"):
                return None

            result_id = int(selection.split("|")[0].strip().replace("#", ""))
            selected = next((r for r in state["results"] if r["result_id"] == result_id), None)
            if not selected:
                return None

            with fitz.open(state["pdf_path"]) as doc:
                return _render_page_with_highlights(doc[selected["page"] - 1], query)

        with gr.Blocks(title="Indexador PDF - Vista previa y búsqueda") as demo:
            gr.Markdown("## Upload PDF → vista previa → búsqueda → highlights")
            state = gr.State({"pdf_path": None, "pages": [], "results": []})

            pdf_input = gr.File(label="PDF", file_types=[".pdf"], type="filepath")
            doc_info = gr.Markdown("Sin documento cargado")
            page_input = gr.Number(label="Página para vista previa", value=1, precision=0)
            preview = gr.Image(label="Vista previa de página", type="pil")

            query_input = gr.Textbox(label="Buscar término o frase")
            search_btn = gr.Button("Buscar")
            status = gr.Markdown()
            results = gr.Dataframe(
                headers=["ID", "Página", "Coincidencias", "Contexto"],
                datatype=["number", "number", "number", "markdown"],
                interactive=False,
                wrap=True,
            )

            selection = gr.Dropdown(label="Resultado para resaltar", choices=[])
            highlighted_preview = gr.Image(label="Página con highlights", type="pil")

            pdf_input.change(
                load_pdf,
                inputs=[pdf_input],
                outputs=[preview, doc_info, state, page_input, selection],
            )
            page_input.change(preview_page, inputs=[page_input, state], outputs=[preview])
            search_btn.click(
                search_query,
                inputs=[query_input, state],
                outputs=[status, results, highlighted_preview, selection, state],
            )
            selection.change(
                show_selected_highlight,
                inputs=[selection, query_input, state],
                outputs=[highlighted_preview],
            )

        demo.launch(server_name=server_name, server_port=server_port)
