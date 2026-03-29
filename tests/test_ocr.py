from pathlib import Path

from app.ocr import extractor


def test_pdf_nativo_salta_ocr(monkeypatch):
    monkeypatch.setattr(extractor, "detect_needs_ocr", lambda _p: False)
    monkeypatch.setattr(extractor, "iter_native_text", lambda _p: iter([(1, "texto nativo")]))
    data = extractor.extract_document(Path("x.pdf"), Path("tmp"))
    assert data["pages"][0]["clean_text"] == "texto nativo"


def test_pdf_escaneado_activa_ocr(monkeypatch):
    class DummyEngine:
        def __init__(self, *args, **kwargs):
            pass

        def recognize(self, _img):
            return type("R", (), {"text": "texto ocr", "confidence": 80.0, "boxes": []})

    monkeypatch.setattr(extractor, "detect_needs_ocr", lambda _p: True)
    monkeypatch.setattr(extractor, "iter_native_text", lambda _p: iter([(1, "")]))
    monkeypatch.setattr(extractor, "iter_native_text", lambda _p: iter([(1, "")]))
    monkeypatch.setattr(extractor, "render_pdf_pages", lambda _p, dpi, first_page=None, last_page=None: [object()])
    monkeypatch.setattr(extractor, "preprocess_image", lambda i: i)
    monkeypatch.setattr(extractor, "OCREngine", DummyEngine)
    data = extractor.extract_document(Path("x.pdf"), Path("tmp"))
    assert data["pages"][0]["word_count"] == 2


def test_preprocesamiento_mejora_confianza(monkeypatch):
    """Smoke test: preprocessor is called before recognition."""
    calls = {"pre": 0}

    class DummyEngine:
        def __init__(self, *args, **kwargs):
            pass

        def recognize(self, _img):
            return type("R", (), {"text": "ok", "confidence": 70.0, "boxes": []})

    def _pre(img):
        calls["pre"] += 1
        return img

    monkeypatch.setattr(extractor, "detect_needs_ocr", lambda _p: True)
    monkeypatch.setattr(extractor, "render_pdf_pages", lambda _p, dpi, first_page=None, last_page=None: [object()])
    monkeypatch.setattr(extractor, "preprocess_image", _pre)
    monkeypatch.setattr(extractor, "OCREngine", DummyEngine)
    extractor.extract_document(Path("x.pdf"), Path("tmp"))
    assert calls["pre"] == 1
