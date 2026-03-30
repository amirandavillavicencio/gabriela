from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _resolve_app_root() -> Path:
    env_root = os.getenv("APP_PORTABLE_ROOT")
    if env_root:
        return Path(env_root).resolve()
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


APP_ROOT = _resolve_app_root()
DATA_DIR = APP_ROOT / "data"
INPUT_DIR = DATA_DIR / "input"
OUTPUT_DIR = DATA_DIR / "output" / "documents"
INDEX_DIR = DATA_DIR / "output"
APP_STATE_DIR = DATA_DIR / "app_state"
TEMP_DIR = DATA_DIR / "temp"
ASSETS_DIR = APP_ROOT / "assets"


SUPPORTED_EXTENSIONS = {".pdf"}


def ensure_runtime_dirs() -> dict[str, Path]:
    dirs = {
        "app_root": APP_ROOT,
        "data": DATA_DIR,
        "input": INPUT_DIR,
        "output": OUTPUT_DIR,
        "index": INDEX_DIR,
        "app_state": APP_STATE_DIR,
        "temp": TEMP_DIR,
        "assets": ASSETS_DIR,
    }
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    return dirs


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def slugify_filename(name: str) -> str:
    base = Path(name).stem.lower()
    base = re.sub(r"[^a-z0-9áéíóúñü_-]+", "_", base, flags=re.IGNORECASE)
    base = re.sub(r"_+", "_", base).strip("_")
    return base or "documento"


def file_sha256(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    hasher = hashlib.sha256()
    with Path(path).open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def build_doc_id(source_name: str, file_hash: str) -> str:
    safe = slugify_filename(source_name)
    return f"doc_{safe}_{file_hash[:12]}"


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def document_output_dir(document_id: str, base_dir: Path | None = None) -> Path:
    root = base_dir or OUTPUT_DIR
    normalized = document_id if document_id.startswith("doc_") else slugify_filename(document_id)
    return ensure_dir(root / normalized)


def document_subdirs(document_id: str, base_dir: Path | None = None) -> dict[str, Path]:
    base = document_output_dir(document_id, base_dir)
    subdirs = {
        "base": base,
        "source": ensure_dir(base / "source"),
        "extracted": ensure_dir(base / "extracted"),
        "index": ensure_dir(base / "index"),
        "logs": ensure_dir(base / "logs"),
        "temp": ensure_dir(base / "temp"),
    }
    return subdirs


def write_json(path: Path, data: Any) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def open_folder(path: Path) -> None:
    if os.name == "nt":
        os.startfile(str(path))  # type: ignore[attr-defined]
        return

    if os.name == "posix":
        if "darwin" in os.uname().sysname.lower():
            os.system(f'open "{path}"')
        else:
            os.system(f'xdg-open "{path}"')
