from pathlib import Path

from app.indexer.search_index import index_chunks, search_chunks


def test_busqueda_exacta_retorna_resultado(tmp_path: Path):
    idx = tmp_path / "index"
    index_chunks(idx, "a.pdf", [{"chunk_id": "c1", "text": "medida cautelar urgente", "page_start": 2}])
    rows = search_chunks(idx, '"medida cautelar"', top=5)
    assert rows


def test_busqueda_fuzzy_tolera_typo(tmp_path: Path):
    idx = tmp_path / "index"
    index_chunks(idx, "a.pdf", [{"chunk_id": "c1", "text": "jurisprudencia", "page_start": 1}])
    rows = search_chunks(idx, "jurisprudenxia", fuzzy=True, top=5)
    assert rows


def test_busqueda_booleana_and(tmp_path: Path):
    idx = tmp_path / "index"
    index_chunks(idx, "a.pdf", [{"chunk_id": "c1", "text": "demanda civil", "page_start": 1}])
    rows = search_chunks(idx, "demanda AND civil", top=5)
    assert rows
