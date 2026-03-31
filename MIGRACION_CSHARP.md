# Migración a C#/.NET (Windows nativo)

## Stack elegido

- **WPF + .NET 8** para escritorio Windows (estable y mantenible).
- **SQLite FTS5** para indexación/búsqueda local (despliegue simple, sin servidor).
- **PdfPig** para extracción nativa de texto PDF.
- **Tesseract CLI** opcional para OCR fallback sin Python embebido.

## Solución

```text
AppPortable.sln
  AppPortable.Desktop        (UI WPF)
  AppPortable.Application    (casos de uso / orquestación)
  AppPortable.Domain         (modelos)
  AppPortable.Infrastructure (PDF, OCR, JSON, filesystem, chunking)
  AppPortable.Search         (SQLite FTS5)
  AppPortable.Tests          (tests)
```

## Persistencia local

Por defecto en:

`%LocalAppData%\AppPortable`

Estructura:

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

## OCR

`TesseractCliOcrEngine` ejecuta `tesseract` del PATH o `TESSERACT_CMD`.

Variables:

- `TESSERACT_CMD` (ruta opcional al ejecutable)
- `TESSERACT_LANG` (ej. `spa`, `eng`, `spa+eng`)

## Build / publish

Compilar solución:

```bash
dotnet build AppPortable.sln -c Release
```

Publicación Windows (self-contained recomendado):

```bash
dotnet publish AppPortable.Desktop/AppPortable.Desktop.csproj -c Release -r win-x64 --self-contained true /p:PublishSingleFile=true
```

Ejecutable esperado:

`AppPortable.Desktop/bin/Release/net8.0-windows/win-x64/publish/AppPortable.exe`
