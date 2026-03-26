# README.md

Proyecto base para una app local de indexación y búsqueda de PDFs judiciales sin OCR.

## Objetivo

Permitir que un usuario cargue documentos PDF con texto embebido, los convierta a JSON estructurado, genere chunks, cree índices locales y luego busque términos dentro del contenido.

## Alcance de la primera etapa

- extracción de texto embebido
- generación de `documento.json`
- generación de `chunks.json`
- indexación local con SQLite FTS5
- buscador local
- interfaz gráfica simple
- modo CLI

## Restricciones

- sin OCR
- sin nube
- sin APIs externas
- sin embeddings
- sin IA generativa

## Estructura esperada

```text
main.py
extractor_pdf.py
normalizador.py
chunker.py
indexador.py
buscador.py
ui.py
utils.py
AGENTS.md
PROMPT_CODEX_JUDICIAL.md
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

## Uso futuro esperado

```bash
python main.py archivo.pdf --json --chunks --index
python main.py --batch carpeta --json --chunks --index
python main.py --search "medida cautelar"
```
