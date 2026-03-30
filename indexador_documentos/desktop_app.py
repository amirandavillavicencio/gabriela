from __future__ import annotations

import sys
from pathlib import Path

from desktop_api import DesktopAPI
from utils import APP_ROOT, ASSETS_DIR, ensure_runtime_dirs


def _safe_import_webview():
    try:
        import webview
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Falta pywebview. Ejecuta: pip install pywebview") from exc
    return webview


def _resolve_ui_html() -> Path:
    candidates = [
        ASSETS_DIR / "ui" / "ocr-pipeline-mockup.html",
        Path(__file__).resolve().parents[1] / "assets" / "ui" / "ocr-pipeline-mockup.html",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("No se encontró assets/ui/ocr-pipeline-mockup.html")


def run_desktop_app() -> None:
    ensure_runtime_dirs()
    webview = _safe_import_webview()
    api = DesktopAPI()
    ui_html = _resolve_ui_html().as_uri()

    window = webview.create_window(
        "OCR Pipeline Desktop",
        url=ui_html,
        js_api=api,
        width=1520,
        height=920,
        min_size=(1200, 760),
        background_color="#0f172a",
    )
    webview.start(debug=not getattr(sys, "frozen", False), http_server=True)


if __name__ == "__main__":
    run_desktop_app()
