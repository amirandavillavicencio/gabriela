# OCR Pipeline (offline, local)

## Run

```bash
cd ocr_pipeline
pip install -r requirements.txt
python app.py
```

Server: `http://127.0.0.1:5353`

## API

### `POST /upload`
Form-data with key `file` (`.pdf`).

### `POST /query`
JSON body:

```json
{
  "query": "medida cautelar",
  "source_file": "optional.pdf",
  "limit": 20
}
```

### `GET /status`
Health + indexed source list.

## Notes

- Native extraction via `pdfminer.six` is attempted first.
- OCR runs only for sparse pages (char threshold).
- Surya OCR is primary.
- If Surya line confidence is low (`< 0.75`), PaddleOCR fallback is used.
- Chunks are indexed in Whoosh with metadata.
