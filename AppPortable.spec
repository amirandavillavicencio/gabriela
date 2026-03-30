# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

root = Path.cwd()
datas = [
    (str(root / 'assets' / 'ui'), 'assets/ui'),
]

hiddenimports = [
    'fitz',
    'PIL',
    'pytesseract',
    'pywebview',
]

a = Analysis(
    ['launch_desktop.py'],
    pathex=[str(root), str(root / 'indexador_documentos')],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['gradio', 'torch', 'transformers'],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='AppPortable',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
