from __future__ import annotations

import logging
from pathlib import Path

from flask import Flask, jsonify, request
from werkzeug.utils import secure_filename

from pipeline.service import OCRPipelineService

logging.basicConfig(level=logging.INFO)

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
DATA_DIR = BASE_DIR / "data"
INDEX_DIR = DATA_DIR / "whoosh_index"
IMAGE_DIR = DATA_DIR / "rendered_pages"
ARTIFACTS_DIR = DATA_DIR / "artifacts"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
service = OCRPipelineService(
    image_dir=IMAGE_DIR,
    index_dir=INDEX_DIR,
    artifacts_dir=ARTIFACTS_DIR,
)


@app.post("/upload")
def upload_pdf():
    if "file" not in request.files:
        return jsonify({"error": "Missing file field"}), 400

    file = request.files["file"]
    if not file or not file.filename:
        return jsonify({"error": "Missing filename"}), 400

    filename = secure_filename(file.filename)
    if not filename.lower().endswith(".pdf"):
        return jsonify({"error": "Only PDF files are allowed"}), 400

    pdf_path = UPLOAD_DIR / filename
    file.save(pdf_path)

    try:
        result = service.process_pdf(pdf_path)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 500

    return jsonify(
        {
            "source_file": result.source_file,
            "pages": len(result.pages),
            "chunks_indexed": len(result.chunks),
            "warnings": result.warnings,
        }
    )


@app.post("/query")
def query_chunks():
    payload = request.get_json(silent=True) or {}
    query = str(payload.get("query", "")).strip()
    source_file = payload.get("source_file")
    limit = int(payload.get("limit", 20))

    if not query:
        return jsonify({"error": "query is required"}), 400

    results = service.search(query=query, source_file=source_file, limit=limit)
    return jsonify({"query": query, "count": len(results), "results": results})


@app.get("/status")
def status():
    return jsonify(service.status())


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5353, debug=False)
