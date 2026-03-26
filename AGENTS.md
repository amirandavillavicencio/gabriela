# AGENTS.md

## 🧠 Propósito del proyecto

Aplicación local de escritorio para:

- procesar documentos PDF (expedientes, causas, resoluciones)
- extraer texto embebido (sin OCR)
- estructurar contenido en JSON
- generar chunks
- indexar contenido localmente
- permitir búsqueda rápida dentro de múltiples documentos

Este proyecto está orientado a uso judicial y administrativo.

---

## ⚠️ Reglas críticas (NO ROMPER)

## Reglas críticas

- ✅ El sistema debe funcionar localmente
- ✅ Debe soportar PDFs grandes
- ✅ Debe priorizar extracción híbrida:
  - texto embebido primero
  - OCR como fallback si no hay texto útil
- ✅ Debe mantener trazabilidad por documento y página

- ❌ No usar servicios en la nube
- ❌ No usar APIs externas
- ❌ No convertir esto en aplicación web

---

## 🧱 Stack permitido

- Python estándar
- PyMuPDF (fitz)
- sqlite3 (FTS5)
- tkinter o customtkinter
- json, os, pathlib, re

Evitar agregar dependencias nuevas sin justificación clara.

---

## 🧩 Arquitectura esperada

El proyecto debe mantenerse modular:

- main.py → punto de entrada (CLI + integración)
- extractor_pdf.py → lectura de PDF
- normalizador.py → limpieza de texto
- chunker.py → generación de chunks
- indexador.py → creación de índice SQLite
- buscador.py → consultas al índice
- ui.py → interfaz gráfica
- utils.py → funciones auxiliares

---

## 🔄 Flujo funcional esperado

1. Usuario selecciona uno o varios PDFs
2. Se extrae texto por página
3. Se limpia el texto
4. Se genera `documento.json`
5. Se generan `chunks.json`
6. Se crea `indice.sqlite`
7. Usuario puede buscar términos
8. Se muestran resultados con contexto

---

## 📦 Estructura de salida

```text
salida/
  indice_global.sqlite
  <nombre_documento>/
    documento.json
    chunks.json
    indice.sqlite
```

---

## 📄 Estructura de documento.json

Debe contener al menos:

- id
- source_name
- page_count
- created_at
- ocr_enabled = false
- has_extractable_text
- extraction_warnings
- pages[]
- clean_full_text

Cada página:

- page_number
- has_text
- text_source
- raw_text
- clean_text

---

## ✂️ Reglas de chunking

- chunks entre 500 y 1000 caracteres aprox
- evitar cortar frases
- respetar límites de página
- ignorar páginas sin texto
- cada chunk debe tener:
  - chunk_id
  - doc_id
  - source_name
  - page_start
  - page_end
  - text
  - length

---

## 🔍 Indexación

- usar SQLite con FTS5
- indexar contenido de chunks
- permitir múltiples documentos
- evitar duplicados

---

## 🔎 Búsqueda

El sistema debe permitir:

- búsqueda por palabra
- búsqueda por frase
- límite de resultados
- resultados con:
  - nombre documento
  - página inicio/fin
  - fragmento de texto
  - chunk_id

---

## 🖥️ Interfaz

Debe incluir:

- selector de archivos PDF
- lista de documentos cargados
- botón de procesamiento
- opciones:
  - generar JSON
  - generar chunks
  - indexar
- campo de búsqueda
- resultados visibles
- estado del proceso

Interfaz simple, sobria y funcional (no decorativa).

---

## 🧪 Modo CLI (obligatorio mantener)

Ejemplos:

```bash
python main.py archivo.pdf --json
python main.py archivo.pdf --json --chunks
python main.py archivo.pdf --json --chunks --index
python main.py --batch carpeta --json --chunks --index
python main.py --search "texto"
```

---

## ⚠️ Manejo de errores

El sistema debe manejar:

- PDF inexistente
- PDF inválido
- PDF sin texto extraíble
- índice inexistente
- búsqueda vacía

Un error en un archivo no debe detener todo el proceso.

---

## 🧨 Principios de diseño

- código claro y modular
- funciones pequeñas
- evitar sobreingeniería
- evitar dependencias innecesarias
- mantener compatibilidad hacia atrás
- no romper funcionalidad existente

---

## ✅ Definición de “terminado”

Una tarea se considera completa si:

- no rompe extracción existente
- genera JSON correctamente
- genera chunks correctamente
- crea índice SQLite funcional
- búsqueda devuelve resultados útiles
- funciona con PDFs grandes
- funciona tanto en CLI como en UI

---

## 📌 Nota final

Este proyecto NO es un chatbot.

Es un sistema de:

→ extracción  
→ estructuración  
→ indexación  
→ búsqueda  

orientado a documentos judiciales reales.
