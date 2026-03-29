from __future__ import annotations

import base64
import io
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path
from typing import Any

import fitz
from flask import Blueprint, Response, jsonify, request, stream_with_context
from PIL import Image

from pipeline.preprocessor import get_default_config_descriptions, preprocess_page
from pipeline.preprocessor_config import PreprocessConfig
from pipeline.preprocessor_types import PreprocessConfigError, PreprocessError

LOGGER = logging.getLogger(__name__)

preprocess_bp = Blueprint("preprocess", __name__)


def _load_config_from_payload(raw: str | None) -> PreprocessConfig:
    if not raw:
        cfg = PreprocessConfig()
        cfg.validate()
        return cfg
    try:
        overrides = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PreprocessConfigError(f"Invalid config JSON: {exc}") from exc
    cfg = PreprocessConfig(**overrides)
    cfg.validate()
    return cfg


def _file_to_image(file_storage: Any) -> Image.Image:
    filename = (file_storage.filename or "").lower()
    data = file_storage.read()
    if not data:
        raise PreprocessError("Uploaded file is empty")
    if filename.endswith(".pdf"):
        with fitz.open(stream=data, filetype="pdf") as doc:
            if len(doc) == 0:
                raise PreprocessError("PDF has no pages")
            page = doc[0]
            pix = page.get_pixmap(matrix=fitz.Matrix(300 / 72.0, 300 / 72.0), alpha=False)
            mode = "RGB" if pix.n >= 3 else "L"
            return Image.frombytes(mode, [pix.width, pix.height], pix.samples)
    return Image.open(io.BytesIO(data)).copy()


def _result_json(result: Any) -> dict[str, Any]:
    img_bytes = io.BytesIO()
    result.image.save(img_bytes, format="PNG")
    image_b64 = base64.b64encode(img_bytes.getvalue()).decode("utf-8")
    return {
        "success": True,
        "image_b64": image_b64,
        "image_dimensions": [result.output_size[0], result.output_size[1]],
        "quality": asdict(result.quality),
        "steps": [asdict(step) for step in result.steps],
        "total_ms": result.total_ms,
        "was_upscaled": result.was_upscaled,
        "effective_dpi": result.effective_dpi,
        "pipeline_version": result.pipeline_version,
    }


@preprocess_bp.post("")
def post_preprocess() -> Any:
    try:
        file_storage = request.files.get("file")
        if file_storage is None:
            raise PreprocessError("Missing required form field 'file'")
        config = _load_config_from_payload(request.form.get("config"))
        page_num = request.form.get("page_num", type=int)
        source = request.form.get("source")
        layer = request.form.get("extraction_layer", default="surya")
        if layer not in {"native", "surya", "paddleocr"}:
            raise PreprocessConfigError("extraction_layer must be native|surya|paddleocr")
        image = _file_to_image(file_storage)
        result = preprocess_page(image=image, config=config, page_number=page_num, source_file=source, extraction_layer=layer)
        return jsonify(_result_json(result))
    except (PreprocessError, PreprocessConfigError) as exc:
        partial = exc.partial_result if isinstance(exc, PreprocessError) else None
        payload = {
            "success": False,
            "error_type": exc.__class__.__name__,
            "message": str(exc),
            "partial_result": None,
        }
        if partial is not None:
            payload["partial_result"] = {
                "original_size": list(partial.original_size),
                "output_size": list(partial.output_size),
                "quality": asdict(partial.quality),
                "steps": [asdict(s) for s in partial.steps],
                "total_ms": partial.total_ms,
                "was_upscaled": partial.was_upscaled,
                "effective_dpi": partial.effective_dpi,
                "pipeline_version": partial.pipeline_version,
            }
        return jsonify(payload), 422


@preprocess_bp.get("/config")
def get_preprocess_config() -> Any:
    return jsonify({"success": True, "defaults": get_default_config_descriptions()})


@preprocess_bp.post("/batch")
def post_preprocess_batch() -> Response:
    payload = request.get_json(silent=True) or {}
    pdf_path = payload.get("pdf_path")
    if not pdf_path:
        return Response(json.dumps({"success": False, "error": "pdf_path is required"}) + "\n", status=422, content_type="application/x-ndjson")

    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        return Response(json.dumps({"success": False, "error": f"PDF not found: {pdf_path}"}) + "\n", status=422, content_type="application/x-ndjson")

    try:
        config = PreprocessConfig(**(payload.get("config") or {}))
        config.validate()
    except PreprocessConfigError as exc:
        return Response(json.dumps({"success": False, "error": str(exc)}) + "\n", status=422, content_type="application/x-ndjson")

    page_range = payload.get("page_range")
    workers = max(1, int(payload.get("workers", 4)))

    with fitz.open(str(pdf_file)) as doc:
        start_page = 1
        end_page = len(doc)
        if isinstance(page_range, list) and len(page_range) == 2:
            start_page = max(1, int(page_range[0]))
            end_page = min(len(doc), int(page_range[1]))
        selected_pages = list(range(start_page, end_page + 1))

    def _process_page(page_num: int) -> dict[str, Any]:
        with fitz.open(str(pdf_file)) as local_doc:
            page = local_doc[page_num - 1]
            pix = page.get_pixmap(matrix=fitz.Matrix(300 / 72.0, 300 / 72.0), alpha=False)
            mode = "RGB" if pix.n >= 3 else "L"
            image = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
            try:
                result = preprocess_page(image=image, config=config, page_number=page_num, source_file=pdf_file.name, extraction_layer="surya")
                return {"page": page_num, "success": True, "quality": asdict(result.quality), "total_ms": result.total_ms}
            except PreprocessError as exc:
                out = {"page": page_num, "success": False, "error_type": exc.__class__.__name__, "message": str(exc)}
                if exc.partial_result:
                    out["partial_quality"] = asdict(exc.partial_result.quality)
                return out

    def _generator() -> Any:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(_process_page, p) for p in selected_pages]
            for fut in as_completed(futures):
                yield json.dumps(fut.result(), ensure_ascii=False) + "\n"

    return Response(stream_with_context(_generator()), content_type="application/x-ndjson")
