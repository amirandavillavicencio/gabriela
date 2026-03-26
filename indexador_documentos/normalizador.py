from __future__ import annotations

from collections import Counter
import re
from typing import Any


_WHITESPACE_RE = re.compile(r"[\t\f\v ]+")
_MULTILINE_RE = re.compile(r"\n{3,}")
_CONFIDENCIAL_RE = re.compile(r"^confidencial\s+\d+$", re.IGNORECASE)

# Umbrales conservadores para no degradar contenido útil.
REPEATED_LINE_THRESHOLD = 50
SHORT_LINE_MAX_CHARS = 30
SHORT_LINE_REPEAT_THRESHOLD = 12
HEADER_FOOTER_REPEAT_THRESHOLD = 6


def _normalize_line(line: str) -> str:
    return _WHITESPACE_RE.sub(" ", line).strip()


def limpiar_texto(texto: str) -> str:
    if not texto:
        return ""

    text = texto.replace("\x00", " ").replace("\r", "\n")
    lines = [_normalize_line(line) for line in text.splitlines()]
    non_empty = [line for line in lines if line]
    normalized = "\n".join(non_empty)
    normalized = _MULTILINE_RE.sub("\n\n", normalized)
    return normalized.strip()


def limpiar_paginas_con_ruido(pages: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not pages:
        return pages, {"lines_removed": 0, "patterns_detected": []}

    page_lines: list[list[str]] = []
    all_lines: list[str] = []
    first_lines: list[str] = []
    last_lines: list[str] = []

    for page in pages:
        raw_text = page.get("raw_text") or ""
        cleaned_lines = [_normalize_line(line) for line in raw_text.replace("\x00", " ").replace("\r", "\n").splitlines()]
        cleaned_lines = [line for line in cleaned_lines if line]
        page_lines.append(cleaned_lines)
        all_lines.extend(cleaned_lines)

        if cleaned_lines:
            first_lines.append(cleaned_lines[0])
            last_lines.append(cleaned_lines[-1])

    line_counts = Counter(all_lines)
    first_counts = Counter(first_lines)
    last_counts = Counter(last_lines)

    repeated_global = {
        line
        for line, count in line_counts.items()
        if count > REPEATED_LINE_THRESHOLD
    }
    short_repeated = {
        line
        for line, count in line_counts.items()
        if len(line) <= SHORT_LINE_MAX_CHARS and count >= SHORT_LINE_REPEAT_THRESHOLD
    }
    repetitive_header_footer = {
        line for line, count in first_counts.items() if count >= HEADER_FOOTER_REPEAT_THRESHOLD
    } | {
        line for line, count in last_counts.items() if count >= HEADER_FOOTER_REPEAT_THRESHOLD
    }

    patterns_detected: list[str] = []
    if repeated_global:
        patterns_detected.append("lineas_repetidas_mas_de_50")
    if short_repeated:
        patterns_detected.append("lineas_cortas_repetidas")
    if repetitive_header_footer:
        patterns_detected.append("encabezados_pies_repetitivos")

    lines_removed = 0
    regex_confidencial_matches = 0
    cleaned_pages: list[dict[str, Any]] = []

    for page, lines in zip(pages, page_lines):
        filtered_lines: list[str] = []
        for line in lines:
            if _CONFIDENCIAL_RE.match(line):
                lines_removed += 1
                regex_confidencial_matches += 1
                continue
            if line in repeated_global:
                lines_removed += 1
                continue
            if line in short_repeated:
                lines_removed += 1
                continue
            if line in repetitive_header_footer:
                lines_removed += 1
                continue
            filtered_lines.append(line)

        clean_text = "\n".join(filtered_lines).strip()
        updated_page = dict(page)
        updated_page["clean_text"] = clean_text
        updated_page["has_text"] = bool(clean_text)
        updated_page["text_source"] = "embedded_text" if clean_text else "none"
        cleaned_pages.append(updated_page)

    if regex_confidencial_matches:
        patterns_detected.append("regex_confidencial_numero")

    patterns_detected = list(dict.fromkeys(patterns_detected))

    stats = {
        "lines_removed": lines_removed,
        "patterns_detected": patterns_detected,
    }
    return cleaned_pages, stats


def split_paragraphs(texto: str) -> list[str]:
    if not texto:
        return []
    blocks = re.split(r"\n\s*\n", texto)
    return [b.strip() for b in blocks if b.strip()]


def split_sentences(texto: str) -> list[str]:
    if not texto:
        return []
    chunks = re.split(r"(?<=[\.!?;:])\s+", texto.strip())
    return [c.strip() for c in chunks if c.strip()]
