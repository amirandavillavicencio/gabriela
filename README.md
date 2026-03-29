# Portable desktop app for offline PDF OCR + semantic chunking + full-text search.

## Requisitos del sistema
- Python **3.11+**: https://www.python.org/downloads/
- Tesseract OCR 5.x: https://github.com/tesseract-ocr/tesseract
- Poppler (`pdftoppm` para `pdf2image`): https://poppler.freedesktop.org/

## Instalación (3 pasos)
1. Clona el repo y entra a la carpeta.
2. Ejecuta: `python setup.py`
3. Lanza app: `run.bat` (Windows) o `./run.sh` (Linux/macOS)

## Uso CLI
### Procesamiento
```bash
python app/main.py process --input data/input/documento.pdf --lang spa --output data/output
```
Salida esperada:
```text
JSON generado: data/output/json/documento.json
```

### Búsqueda
```bash
python app/main.py search --query "medida cautelar" --fuzzy --top 10
```
Salida esperada:
```text
[12.53] documento.pdf p45 documento_chunk_0042
...MEDIDA CAUTELAR...
```

### Reindexado
```bash
python app/main.py reindex --json data/output/json/documento.json
```

## JSON de salida
Estructura:
- `document`: metadatos globales (archivo, páginas, engine OCR, idioma, promedio de confianza)
- `pages[]`: `page_number`, `raw_text`, `clean_text`, `ocr_confidence`, `word_count`
- `chunks[]`: `chunk_id`, `page_start`, `page_end`, `char_start`, `char_end`, `text`, `word_count`, `chunk_index`
- `metadata`: `total_chunks`, `avg_chunk_size_words`, `chunking_strategy`

## Configuración (`config.ini`)
- `[ocr]`: idioma, DPI, OEM/PSM de Tesseract, fallback EasyOCR, umbral de confianza
- `[chunking]`: `max_chunk_words`, `overlap_words`, `min_chunk_words`, `strategy`
- `[logging]`: nivel y archivo de log

## GUI
Incluye:
- Panel izquierdo: cargar PDF, idioma OCR, procesar, estado, log, ver JSON
- Panel derecho: campo de búsqueda, fuzzy, resultados, visor de chunk

Capturas:
- [screenshot]
- [screenshot]
