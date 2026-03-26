# Indexador local de PDFs judiciales (sin OCR)

Aplicación local para extracción, chunking, indexación SQLite FTS5 y búsqueda sobre PDFs con texto embebido.

## Requisitos

```bash
pip install -r requirements.txt
```

## CLI

```bash
python main.py archivo.pdf --json
python main.py archivo.pdf --json --chunks
python main.py archivo.pdf --json --chunks --index
python main.py --batch carpeta_con_pdfs --json --chunks --index
python main.py --search "medida cautelar"
python main.py --search "medida cautelar" --phrase
```

## GUI

```bash
python main.py --ui
```

## Salida esperada

```text
salida/
  indice_global.sqlite
  <nombre_documento>/
    documento.json
    chunks.json
    indice.sqlite
```
