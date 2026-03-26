# README.md

Proyecto local para indexación y búsqueda de PDFs judiciales con flujo **híbrido automático**:

- texto embebido (PyMuPDF)
- limpieza de ruido repetitivo
- OCR por fallback (Tesseract local)
- chunking
- indexación SQLite FTS5
- búsqueda local

## Requisitos

- Python 3.10+
- Dependencias del proyecto
- Tesseract OCR instalado localmente en Windows
- idioma español `spa` instalado en Tesseract

```bash
pip install -r indexador_documentos/requirements.txt
```

## Configuración OCR

En `indexador_documentos/config.py`:

```python
TESSERACT_CMD = r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
TESSERACT_LANG = "spa"
OCR_DPI = 300
```

También se puede configurar por variables de entorno (`TESSERACT_CMD`, `TESSERACT_LANG`, `OCR_DPI`).

## Flujo híbrido

1. Extrae texto embebido por página
2. Limpia ruido repetitivo
3. Evalúa si el texto es útil
4. Si no es útil, ejecuta OCR
5. Guarda `text_source` por página (`embedded_text`, `ocr`, `none`)

## CLI

```bash
python indexador_documentos/main.py archivo.pdf --json --chunks --index
python indexador_documentos/main.py --batch carpeta --json --chunks --index
python indexador_documentos/main.py --search "texto"
python indexador_documentos/main.py archivo.pdf --json --chunks --index --force-ocr
```

## Limitaciones OCR

- OCR depende de calidad del escaneo.
- Si Tesseract o `spa` no están disponibles, el sistema continúa y reporta advertencias.
- Una página con error OCR no detiene el lote completo.
