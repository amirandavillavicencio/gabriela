# Indexador local de PDFs judiciales (híbrido: texto embebido + OCR)

Aplicación local para extracción, chunking, indexación SQLite FTS5 y búsqueda sobre PDFs judiciales.

## Requisitos

1. Python 3.10+
2. Instalar dependencias:

```bash
pip install -r requirements.txt
```

3. Instalar **Tesseract OCR** en Windows (ejemplo: `C:\Program Files\Tesseract-OCR\tesseract.exe`).
4. Asegurar idioma español (`spa`) instalado en Tesseract.

## Configuración OCR

Editar `config.py` (o usar variables de entorno):

```python
TESSERACT_CMD = r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
TESSERACT_LANG = "spa"
OCR_DPI = 300
```

Variables compatibles: `TESSERACT_CMD`, `TESSERACT_LANG`, `OCR_DPI`, `OCR_PSM`, `OCR_OEM`.

## Flujo híbrido automático

Por cada página:

1. Extrae texto embebido
2. Limpia ruido repetitivo
3. Evalúa si el texto es útil
4. Si no es útil, aplica OCR
5. Usa el mejor resultado como texto final

`documento.json` incluye:

- `text_source` por página: `embedded_text`, `ocr` o `none`
- `ocr_enabled`
- `ocr_used`
- `ocr_pages`
- `embedded_text_pages`
- `cleaning_stats`

## CLI

```bash
python main.py archivo.pdf --json
python main.py archivo.pdf --json --chunks
python main.py archivo.pdf --json --chunks --index
python main.py --batch carpeta_con_pdfs --json --chunks --index
python main.py --input-dir carpeta_con_pdfs --output-dir salida_ci --json --chunks --index
python main.py --search "medida cautelar"
python main.py --search "medida cautelar" --phrase
python main.py archivo.pdf --json --chunks --index --force-ocr
```

## GUI

```bash
python main.py --ui
```

Incluye opción **Forzar OCR**.

## Salida esperada

```text
salida/
  indice_global.sqlite
  <nombre_documento>/
    documento.json
    chunks.json
    indice.sqlite
```

## Limitaciones OCR

- OCR puede reducir precisión con escaneos borrosos, inclinados o de baja resolución.
- Si falta Tesseract o el idioma configurado, se reporta advertencia y el proceso continúa.
- Errores OCR por página no detienen el procesamiento completo del documento o lote.
