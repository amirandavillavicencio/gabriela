from app.chunker.semantic_chunker import build_chunks


def test_chunk_size_respeta_max_words():
    pages = [{"page_number": 1, "clean_text": "palabra " * 500}]
    chunks = build_chunks(pages, "doc", max_chunk_words=200, overlap_words=50, min_chunk_words=1)
    assert chunks
    assert max(c["word_count"] for c in chunks) <= 200


def test_overlap_genera_chunks_solapados():
    pages = [{"page_number": 1, "clean_text": " ".join(f"w{i}" for i in range(260))}]
    chunks = build_chunks(pages, "doc", max_chunk_words=100, overlap_words=20, min_chunk_words=1, strategy="sliding_only")
    assert len(chunks) >= 3
    first_tail = chunks[0]["text"].split()[-20:]
    second_head = chunks[1]["text"].split()[:20]
    assert first_tail == second_head


def test_parrafo_corto_no_se_divide():
    pages = [{"page_number": 1, "clean_text": "Este es un párrafo corto de prueba."}]
    chunks = build_chunks(pages, "doc", max_chunk_words=200, overlap_words=50, min_chunk_words=1)
    assert len(chunks) == 1
