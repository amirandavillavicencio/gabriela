# Indexador local de PDFs judiciales (legacy Python)

> Este módulo Python se conserva por compatibilidad histórica.
> La app desktop objetivo/final está en `AppPortable.sln` (.NET 8 + WPF).

## CLI legacy (Python)

```bash
python main.py archivo.pdf --json
python main.py archivo.pdf --json --chunks
python main.py archivo.pdf --json --chunks --index
python main.py --batch carpeta_con_pdfs --json --chunks --index
python main.py --search "medida cautelar"
```

## Desktop final (Windows nativo)

Compilar/publicar desde la solución .NET:

```bash
dotnet build ../AppPortable.sln -c Release
dotnet publish ../AppPortable.Desktop/AppPortable.Desktop.csproj -c Release -r win-x64 --self-contained true /p:PublishSingleFile=true
```

Salida esperada del ejecutable:

`../AppPortable.Desktop/bin/Release/net8.0-windows/win-x64/publish/AppPortable.exe`
