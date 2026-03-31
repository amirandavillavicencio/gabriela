# AppPortable (.NET 8 / WPF)

Aplicación de escritorio **nativa Windows** para procesamiento documental judicial/administrativo:

**PDF → extracción nativa/OCR → JSON → chunking → indexación SQLite FTS5 → búsqueda local**.

## Solución actual (objetivo principal)

```text
AppPortable.sln
  AppPortable.Desktop        (WPF)
  AppPortable.Core           (modelos, contratos, pipeline)
  AppPortable.Infrastructure (PDF, OCR, JSON, filesystem, chunking)
  AppPortable.Search         (SQLite FTS5)
  AppPortable.Tests
```

## Flujo implementado

1. Cargar PDF.
2. Extraer texto embebido (PdfPig).
3. Ejecutar OCR fallback opcional (Tesseract CLI).
4. Generar `document.json`, `pages.json`, `chunks.json`.
5. Indexar chunks en `indice_global.sqlite` (FTS5).
6. Buscar por palabra/frase y mostrar resultados con snippet.

## Persistencia local

Base: `%LocalAppData%\AppPortable`

```text
input/
output/
  documents/<document_id>/extracted/document.json
  documents/<document_id>/extracted/pages.json
  documents/<document_id>/extracted/chunks.json
  index/indice_global.sqlite
temp/
logs/
```

## Build y publish (Windows)

```bash
dotnet restore AppPortable.sln
dotnet build AppPortable.sln -c Release
dotnet publish AppPortable.Desktop/AppPortable.Desktop.csproj -c Release -r win-x64 --self-contained true /p:PublishSingleFile=true
```

Ejecutable publicado:

`AppPortable.Desktop/bin/Release/net8.0-windows/win-x64/publish/AppPortable.exe`

## Estado de la ruta Python desktop

La ruta Python/PyInstaller fue movida a `legacy/python-desktop/` y **no es el objetivo principal**.
