from __future__ import annotations

import re


_WHITESPACE_RE = re.compile(r"[\t\f\v ]+")
_MULTILINE_RE = re.compile(r"\n{3,}")


def limpiar_texto(texto: str) -> str:
    if not texto:
        return ""

    text = texto.replace("\x00", " ").replace("\r", "\n")
    lines = [_WHITESPACE_RE.sub(" ", line).strip() for line in text.splitlines()]
    non_empty = [line for line in lines if line]
    normalized = "\n".join(non_empty)
    normalized = _MULTILINE_RE.sub("\n\n", normalized)
    return normalized.strip()


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
