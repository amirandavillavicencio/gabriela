from __future__ import annotations

import sys

from indexador_documentos.desktop_app import run_desktop_app


def main() -> int:
    run_desktop_app()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
