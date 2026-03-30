# Indexador documental local (backend desktop-ready)

Backend local para procesamiento documental con pipeline real:

**PDF → extracción nativa/OCR → normalización → JSON estructurado → chunking → indexación SQLite FTS5 → búsqueda local**.

## Qué hace ahora

- Ingesta y validación de PDFs.
- Extracción híbrida por página (texto nativo primero, OCR como fallback).
- Normalización de texto robusta para documentos judiciales/administrativos.
- Exportación de `document.json`, `pages.json` y `chunks.json` por documento.
- Indexación local con SQLite FTS5 (índice local por documento + índice global).
- Servicio de búsqueda rankeada sobre chunks ya indexados.
- Servicios de backend listos para integrar con UI de escritorio.

## Arquitectura (módulos principales)

- `indexador_documentos/extractor_pdf.py`: extracción PDF + fallback OCR + trazabilidad por página.
- `indexador_documentos/normalizador.py`: limpieza y validación de texto útil.
- `indexador_documentos/chunker.py`: chunking semántico por párrafo/oración.
- `indexador_documentos/indexador.py`: creación y actualización de índice SQLite FTS5.
- `indexador_documentos/buscador.py`: consultas full-text con score/snippet.
- `indexador_documentos/services.py`: orquestación (`DocumentProcessingService`, `IndexService`, `SearchService`).
- `indexador_documentos/main.py`: entry point CLI.
- `indexador_documentos/utils.py`: rutas, persistencia, IDs, hash y utilidades runtime.

## Estructura de salida

```text
data/
  input/
  output/
    indice_global.sqlite
    documents/
      <document_id>/
        source/
        extracted/
          document.json
          pages.json
          chunks.json
        index/
          indice.sqlite
        logs/
        temp/
  app_state/
  temp/
```

## Comandos CLI

Instalación:

```bash
pip install -r indexador_documentos/requirements.txt
```

Procesar documento:

```bash
python -m indexador_documentos.main process "input/Tomo 09.pdf"
```

Procesar forzando OCR:

```bash
python -m indexador_documentos.main process "input/Tomo 09.pdf" --force-ocr
```

Buscar:

```bash
python -m indexador_documentos.main search "medida cautelar" --limit 10
python -m indexador_documentos.main search "prescripción adquisitiva" --phrase
```

Reindexar:

```bash
python -m indexador_documentos.main reindex
python -m indexador_documentos.main reindex --document-id <document_id>
```

Listar documentos y estado:

```bash
python -m indexador_documentos.main list-docs
python -m indexador_documentos.main status <document_id>
```

## Configuración

Variables de entorno relevantes:

- OCR: `TESSERACT_CMD`, `TESSERACT_LANG`, `OCR_DPI`, `OCR_PSM`, `OCR_OEM`
- Calidad extracción: `MIN_TEXT_CHARS_USEFUL`, `MIN_WORDS_USEFUL`, `MAX_REPEAT_LINE_RATIO`
- Chunking: `CHUNK_MIN_CHARS`, `CHUNK_MAX_CHARS`, `CHUNK_OVERLAP_CHARS`
- Búsqueda: `SEARCH_DEFAULT_LIMIT`

## Limitaciones actuales

- OCR depende de Tesseract instalado localmente con idioma disponible.
- OCR Transformer sigue siendo opcional y pesado (dependencias no obligatorias).
- El backend está desacoplado de UI, pero la UI deberá consumir `services.py` para progreso/estado.


## Build de aplicación portable Windows (PyInstaller)

Entry point desktop:

```bash
python launch_desktop.py
```

Build local (Windows):

```bat
scripts\build_portable_windows.bat
```

Build manual:

```bash
pip install -r requirements-desktop.txt
pyinstaller --noconfirm --clean AppPortable.spec
```

Salida esperada:

```text
dist/AppPortable/AppPortable.exe
```

Workflow dedicado de build Windows:

- `.github/workflows/build_portable_windows.yml`
- artefacto final: `AppPortable_windows_portable`

