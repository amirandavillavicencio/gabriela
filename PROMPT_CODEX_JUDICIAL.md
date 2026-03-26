# PROMPT_CODEX_JUDICIAL.md

## Prompt para Codex

Actúa como un ingeniero de software senior especializado en aplicaciones de escritorio para procesamiento documental e indexación local.

Estás trabajando en un repositorio Python ya existente que actualmente:
- recibe un PDF
- extrae texto por página usando PyMuPDF
- genera un JSON estructurado básico

Tu tarea es transformar este proyecto en una aplicación local orientada a expedientes y documentos judiciales, pensada para usuarios no técnicos, que permita:

1. cargar uno o varios PDFs
2. extraer texto sin OCR
3. generar JSON estructurado por documento
4. chunkear el contenido
5. indexarlo localmente
6. buscar dentro de todos los documentos indexados
7. mostrar resultados con documento, página y fragmento coincidente

IMPORTANTE:
- NO agregar OCR en esta etapa
- NO usar servicios en la nube
- TODO debe funcionar localmente
- Debe soportar documentos grandes (hasta 600 páginas)
- Debe priorizar estabilidad, trazabilidad y búsqueda útil
- Debe mantenerse la funcionalidad actual de extracción a JSON
- Entregar archivos completos, no fragmentos

## Objetivo del producto

Construir una aplicación local de escritorio para indexar y buscar contenido dentro de PDFs judiciales sin OCR.
Si un PDF no tiene texto embebido, debe quedar marcado como no indexable sin OCR, pero no debe romper el flujo.

## Arquitectura esperada

El proyecto debe quedar modularizado y claro.

Crear o refactorizar con esta estructura lógica:

- main.py
- extractor_pdf.py
- normalizador.py
- chunker.py
- indexador.py
- buscador.py
- ui.py
- utils.py

Si algún archivo ya existe, reutilízalo y mejóralo sin romper compatibilidad.

## Funcionalidad 1: Extracción

Mantener y mejorar la extracción actual:
- leer PDF por página
- extraer texto embebido
- limpiar texto
- detectar páginas sin texto
- generar documento.json

Formato esperado por documento:
`salida/<nombre_documento>/documento.json`

Debe incluir al menos:
- id
- source_name
- page_count
- created_at
- ocr_enabled = false
- has_extractable_text
- extraction_warnings
- pages[]
- clean_full_text

Cada página debe incluir:
- page_number
- has_text
- text_source
- raw_text
- clean_text

## Funcionalidad 2: Chunking

Crear `chunker.py` para dividir el contenido en fragmentos buscables.

Requisitos:
- chunking por bloques razonables de sentido
- fallback por longitud si no hay separadores claros
- no cortar frases a la mitad si se puede evitar
- chunks entre 500 y 1000 caracteres aprox
- incluir referencia de página inicial y final
- ignorar páginas vacías

Guardar en:
`salida/<nombre_documento>/chunks.json`

Formato:

```json
[
  {
    "chunk_id": "doc_x_chunk_0001",
    "doc_id": "doc_x",
    "source_name": "archivo.pdf",
    "page_start": 1,
    "page_end": 2,
    "text": "contenido del chunk",
    "length": 742
  }
]
```

## Funcionalidad 3: Indexación local

Crear `indexador.py` usando SQLite con FTS5.

Objetivo:
- generar una base local buscable por documento
- búsqueda rápida por texto
- escalable para varios PDFs

Guardar en:
- `salida/<nombre_documento>/indice.sqlite`
- `salida/indice_global.sqlite`

La tabla debe contener al menos:
- chunk_id
- doc_id
- source_name
- page_start
- page_end
- text

Usar FTS5 para indexar el texto del chunk.

## Funcionalidad 4: Buscador

Crear `buscador.py` con funciones para consultar el índice.

Debe permitir:
- búsqueda por palabra
- búsqueda por frase
- límite de resultados
- devolver resultados con:
  - nombre del documento
  - página inicial
  - página final
  - fragmento del texto
  - chunk_id

Formato esperado de resultados:

```json
[
  {
    "source_name": "causa_001.pdf",
    "page_start": 17,
    "page_end": 18,
    "chunk_id": "doc_001_chunk_0008",
    "snippet": ".... texto coincidente ...."
  }
]
```

## Funcionalidad 5: Interfaz gráfica

Crear una interfaz simple en Tkinter o CustomTkinter.
Priorizar que funcione bien en Windows.

La app debe tener:
- botón para seleccionar uno o varios PDFs
- lista de archivos cargados
- botón “Procesar”
- checkbox:
  - Generar JSON
  - Generar chunks
  - Indexar
- campo de búsqueda
- botón “Buscar”
- panel de resultados
- barra o texto de estado del proceso

Los resultados de búsqueda deben mostrar:
- documento
- páginas
- fragmento
- idealmente opción para abrir carpeta de salida

No hacer una interfaz recargada.
Debe verse sobria, funcional y orientada a oficina/juzgado.

## Funcionalidad 6: Flujo

El flujo esperado de usuario es:

1. seleccionar PDFs
2. procesarlos
3. generar documento.json
4. generar chunks.json
5. generar índice sqlite
6. buscar términos dentro de los documentos indexados

## Funcionalidad 7: Modo CLI

Mantener también ejecución por línea de comandos.

Ejemplos esperados:

```bash
python main.py archivo.pdf --json
python main.py archivo.pdf --json --chunks
python main.py archivo.pdf --json --chunks --index
python main.py --batch carpeta_con_pdfs --json --chunks --index
python main.py --search "medida cautelar"
```

Si se usa `--search`, debe consultar el índice global si existe.

## Manejo de errores

Agregar manejo claro de errores:
- PDF inexistente
- PDF inválido
- PDF sin texto extraíble
- índice no encontrado
- búsqueda vacía
- duplicados al indexar

No romper la ejecución completa por un solo archivo fallido.

## Restricciones técnicas

- No usar OCR
- No usar APIs externas
- No usar nube
- No usar embeddings
- No usar IA generativa
- No usar frameworks web
- Mantener dependencias al mínimo

## Dependencias razonables

Puedes usar:
- pymupdf
- sqlite3
- tkinter o customtkinter
- pathlib
- json
- os
- re

Evita agregar dependencias innecesarias.

## Salida final esperada

El repositorio debe quedar listo para:
- procesar PDFs locales
- generar JSON
- generar chunks
- indexar contenido
- buscar dentro de documentos indexados
- usarse mediante interfaz gráfica y CLI

## Estructura de salida

```text
salida/
  indice_global.sqlite
  <nombre_documento_1>/
    documento.json
    chunks.json
    indice.sqlite
  <nombre_documento_2>/
    documento.json
    chunks.json
    indice.sqlite
```

## Criterios de “done”

Considera el trabajo terminado solo si:
1. la extracción actual sigue funcionando
2. se generan chunks correctamente
3. se crea el índice sqlite con FTS5
4. la búsqueda devuelve resultados útiles
5. existe interfaz gráfica funcional
6. funciona con PDFs grandes sin OCR
7. el código queda modular y legible
8. entregas archivos completos, no fragmentos

## Prefacio recomendado antes de pegar el prompt

Primero analiza el repositorio, resume el estado actual y propón un plan de implementación por etapas. No escribas código todavía. Cuando termines el plan, recién empieza a modificar archivos.
