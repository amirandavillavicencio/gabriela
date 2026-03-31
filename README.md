# AppPortable (.NET 8 / C#)

Aplicación de escritorio local para procesamiento documental judicial/administrativo.

## Stack

- .NET 8
- C#
- WPF (Desktop)
- SQLite FTS5

## Estructura del repositorio

```text
AppPortable.sln
AppPortable.Application/
AppPortable.Domain/
AppPortable.Infrastructure/
AppPortable.Search/
AppPortable.Desktop/
AppPortable.Tests/
.github/workflows/build_portable_windows.yml
```

## Build local

```bash
dotnet restore AppPortable.sln
dotnet build AppPortable.sln --configuration Release
```

## Publicación

```bash
dotnet publish AppPortable.Desktop/AppPortable.Desktop.csproj \
  --configuration Release \
  --runtime win-x64 \
  --self-contained true \
  -o artifacts/publish
```

## CI/CD

El workflow activo en GitHub Actions compila y publica artefactos de escritorio usando solo .NET 8.
