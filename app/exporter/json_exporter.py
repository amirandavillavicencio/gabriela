"""JSON export logic."""
from __future__ import annotations

import json
from pathlib import Path


def export_document_json(output_dir: Path, payload: dict) -> Path:
    """Save processed document payload as UTF-8 JSON."""
    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / f"{Path(payload['document']['filename']).stem}.json"
    out_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_file
