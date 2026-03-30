from __future__ import annotations

import json
import os
import sys
import re
from datetime import datetime
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
INPUT_DIR = APP_ROOT / "input"
OUTPUT_DIR = APP_ROOT / "output"
INDEX_DIR = APP_ROOT / "index"
TEMP_DIR = APP_ROOT / "temp"
ASSETS_DIR = APP_ROOT / "assets"


def ensure_runtime_dirs() -> dict[str, Path]:
    dirs = {
        "app_root": APP_ROOT,
        "input": INPUT_DIR,
        "output": OUTPUT_DIR,
        "index": INDEX_DIR,
        "temp": TEMP_DIR,
        "assets": ASSETS_DIR,
    }
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    return dirs


def utc_now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def slugify_filename(name: str) -> str:
    base = Path(name).stem.lower()
    base = re.sub(r"[^a-z0-9áéíóúñü_-]+", "_", base, flags=re.IGNORECASE)
    base = re.sub(r"_+", "_", base).strip("_")
    return base or "documento"


def build_doc_id(source_name: str) -> str:
    safe = slugify_filename(source_name)
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    return f"doc_{safe}_{timestamp}"


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def document_output_dir(source_name: str, base_dir: Path | None = None) -> Path:
    root = base_dir or OUTPUT_DIR
    return ensure_dir(root / slugify_filename(source_name))


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
