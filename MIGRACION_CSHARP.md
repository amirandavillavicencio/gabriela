# Migración real a C#/.NET 8 (Windows nativo)

## Mapeo Python → C#

- `indexador_documentos/extractor_pdf.py` → `AppPortable.Infrastructure/Processing/PdfPigTextExtractor.cs`
- `indexador_documentos/ocr_engine.py` → `AppPortable.Infrastructure/Processing/TesseractCliOcrEngine.cs`
- `indexador_documentos/chunker.py` → `AppPortable.Infrastructure/Processing/SemanticChunker.cs`
- `indexador_documentos/indexador.py` + `buscador.py` → `AppPortable.Search/SqliteFtsIndexer.cs`
- `indexador_documentos/services.py` → `AppPortable.Core/Services/DocumentPipelineService.cs`
- modelos JSON/documento/chunks → `AppPortable.Core/Models/*.cs`
- UI Python desktop (legacy) → `AppPortable.Desktop` (WPF)

## Arquitectura resultante

```text
AppPortable.sln
  AppPortable.Desktop
  AppPortable.Core
  AppPortable.Infrastructure
  AppPortable.Search
  AppPortable.Tests
```

## UI WPF cubierta

- Cargar PDF.
- Procesar documento.
- Estado/progreso.
- Lista de documentos procesados.
- Búsqueda sobre índice global.
- Panel de detalle de documento/chunk.

## OCR elegido

- Tesseract CLI (estable y mantenible en Windows).
- Variables: `TESSERACT_CMD`, `TESSERACT_LANG`.

## Indexación/búsqueda elegida

- SQLite + FTS5 (`Microsoft.Data.Sqlite`).
- Índice global: `output/index/indice_global.sqlite`.

## Build/publicación

```bash
dotnet restore AppPortable.sln
dotnet build AppPortable.sln -c Release
dotnet publish AppPortable.Desktop/AppPortable.Desktop.csproj -c Release -r win-x64 --self-contained true /p:PublishSingleFile=true
```

Salida:

`AppPortable.Desktop/bin/Release/net8.0-windows/win-x64/publish/AppPortable.exe`

## Legacy explícito

- `legacy/python-desktop/AppPortable.spec`
- `legacy/python-desktop/launch_desktop.py`

No se usa PyInstaller para la app desktop final.
