# Indexador local de PDFs judiciales (híbrido)

## Ejecutar app desktop (UI tipo dashboard)

```bash
python main.py --desktop
```

## Ejecutar GUI Tk clásica

```bash
python main.py --ui
```

## CLI

```bash
python main.py archivo.pdf --json
python main.py archivo.pdf --json --chunks
python main.py archivo.pdf --json --chunks --index
python main.py --batch carpeta_con_pdfs --json --chunks --index
python main.py --search "medida cautelar"
```

## Build Windows portable

Usar `../scripts/build_portable_windows.bat` con `PyInstaller` y el spec `../AppPortable.spec`.

## Salida esperada

```text
output/
  <nombre_documento>/
    documento.json
    chunks.json
    indice.sqlite
index/
  indice_global.sqlite
```
