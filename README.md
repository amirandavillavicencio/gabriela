# Indexador judicial PDF · Desktop portable Windows

Aplicación local para extracción, chunking, indexación SQLite FTS5 y búsqueda en documentos PDF judiciales.

## Modo de uso

### Desarrollo

```bash
pip install -r indexador_documentos/requirements.txt
python indexador_documentos/main.py --desktop
```

### CLI

```bash
python indexador_documentos/main.py archivo.pdf --json --chunks --index
python indexador_documentos/main.py --batch input --json --chunks --index
python indexador_documentos/main.py --search "medida cautelar"
```

## Carpetas runtime (auto-creadas)

```text
input/
output/
index/
temp/
assets/ui/
```

## Build portable para Windows (.exe)

```bat
scripts\build_portable_windows.bat
```

También puedes ejecutar manualmente:

```bat
pip install -r indexador_documentos\requirements.txt
pip install pyinstaller
pyinstaller --noconfirm AppPortable.spec
```

## Resultado esperado de build

```text
dist/
  AppPortable/
    AppPortable.exe
    _internal/...
    assets/ui/ocr-pipeline-mockup.html
    input/
    output/
    index/
    temp/
```

## OCR

- Usa Tesseract local (autodetección por PATH o `TESSERACT_CMD`).
- Si OCR no está disponible, la app sigue funcionando con texto embebido y muestra warning.

Variables opcionales:
- `TESSERACT_CMD`
- `TESSERACT_LANG` (default `spa`)
- `OCR_DPI`, `OCR_PSM`, `OCR_OEM`

## Notas

- La UI desktop principal está en `assets/ui/ocr-pipeline-mockup.html` y se conecta al backend real vía `pywebview`.
- No depende de GitHub ni de servicios en nube para operar localmente.
