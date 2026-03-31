# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import os

root = Path(os.getcwd()).resolve()

# Incluye todo el árbol de assets (html/css/js/templates/etc.)
datas = [
    (str(root / "assets"), "assets"),
]

hiddenimports = [
    "fitz",
    "PIL",
    "pytesseract",
    "webview",
    "webview.platforms.winforms",
    "webview.platforms.edgechromium",
    "indexador_documentos.desktop_app",
    "indexador_documentos.desktop_api",
]

a = Analysis(
    [str(root / "launch_desktop.py")],
    pathex=[str(root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["gradio", "torch", "transformers"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AppPortable",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="AppPortable",
)
