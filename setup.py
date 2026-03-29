"""One-step environment bootstrapper."""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV_DIR = ROOT / "venv"


def _run(cmd: list[str]) -> None:
    subprocess.check_call(cmd)


def ensure_venv() -> Path:
    if not VENV_DIR.exists():
        _run([sys.executable, "-m", "venv", str(VENV_DIR)])
    scripts = "Scripts" if os.name == "nt" else "bin"
    return VENV_DIR / scripts / ("python.exe" if os.name == "nt" else "python")


def check_tool(name: str) -> bool:
    return shutil.which(name) is not None


def check_tesseract_languages() -> None:
    if not check_tool("tesseract"):
        print("[ERROR] Tesseract no está instalado.")
        print("Instala desde: https://github.com/tesseract-ocr/tesseract")
        return
    out = subprocess.check_output(["tesseract", "--list-langs"], text=True, stderr=subprocess.STDOUT)
    if "spa" not in out:
        print("[WARN] Falta idioma 'spa' en Tesseract.")


def check_poppler() -> None:
    if check_tool("pdftoppm"):
        print("[OK] Poppler detectado.")
    else:
        print("[WARN] Poppler no detectado. Instala desde https://poppler.freedesktop.org/")


def write_launchers() -> None:
    (ROOT / "run.bat").write_text("@echo off\ncall venv\\Scripts\\activate\npython app\\main.py\npause\n", encoding="utf-8")
    run_sh = ROOT / "run.sh"
    run_sh.write_text("#!/bin/bash\nsource venv/bin/activate\npython app/main.py\n", encoding="utf-8")
    run_sh.chmod(0o755)


def main() -> None:
    print(f"Sistema operativo: {platform.system()}")
    py = ensure_venv()
    _run([str(py), "-m", "pip", "install", "--upgrade", "pip"])
    _run([str(py), "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")])
    check_tesseract_languages()
    check_poppler()
    write_launchers()
    print("Instalación completa. Ejecuta run.bat o run.sh")


if __name__ == "__main__":
    main()
