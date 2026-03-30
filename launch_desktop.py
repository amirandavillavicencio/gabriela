from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "indexador_documentos"))

from desktop_app import run_desktop_app


if __name__ == "__main__":
    run_desktop_app()
