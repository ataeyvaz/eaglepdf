"""Filigran motoru testleri (sentetik PDF'lerle tespit + temizleme). pdfedit'ten taşındı; OCR Tesseract'a bağlandı."""
import collections

import pymupdf as fitz
import pytest

from eaglepdf.core.filigran import cleaner, detector, manual, ocr, pdfops, rules  # noqa: E402


PAGES = 6


def _words(doc):
    return [collections.Counter(w[4] for w in p.get_text("words")) for p in doc]


def _logo_png() -> bytes:
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 60, 30), True)
    pix.set_rect(pix.irect, (200, 30, 30, 120))
    return pix.tobytes("png")


@pytest.fixture(scope="module")
def sample(tmp_path_factory):
    path = str(tmp_path_factory.mktemp("pdf") / "ornek.pdf")
    doc = fitz.open()
    img_xref = 0
    for i in range(PAGES):
        page = doc.new_page()
        # gerçek içerik: üst bilgi (tekrar eder ama filigran değil) + sayfaya özgü metin
        page.insert_text((50, 40), "Matematik Ders Notlari", fontsize=10)
        page.insert_text((50, 100), f"Soru {i + 1}: Ucgenin ic acilari toplami kactir?", fontsize=12)
        page.insert_text((50, 130), f"Cevap secenekleri sayfa {i + 1}", fontsize=12)
        # metin filigranı: 45° döndürülmüş, yarı saydam, büyük
        page.insert_text((120, 600), "GIZLI www.ornekyayin.com", fontsize=40,
                         morph=(fitz.Point(120, 600), fitz.Matrix(45)), fill_opacity=0.25,
                         color=(0.5, 0.5, 0.5))
        # resim filigranı: aynı logo her sayfada aynı yerde
        r = fitz.Rect(450, 750, 550, 800)
        if img_xref:
            page.insert_image(r, xref=img_xref)
        else:
            img_xref = page.insert_image(r, stream=_logo_png())
        # gerçek resim: yalnızca bir sayfada
        if i == 2:
            page.insert_image(fitz.Rect(50, 200, 150, 250), stream=_logo_png())
        # annotation filigranı + tekrar eden bağlantı
        page.insert_link({"kind": fitz.LINK_URI, "from": fitz.Rect(50, 800, 200, 815),
                          "uri": "https://www.ornekyayin.com"})
    doc.save(path)
    doc.close()
    return path


def test_detects_text_image_link(sample):
    res = detector.scan(sample)
    kinds = {f.kind: f for f in sorted(res.findings, key=lambda f: f.score)}
    assert "text" in kinds and "image" in kinds and "link" in kinds
    t = kinds["text"]
    assert t.selected and "GIZLI" in t.text and len(t.pages) == PAGES
    assert "www.ornekyayin.com" in t.urls
    assert kinds["image"].selected and len(kinds["image"].pages) == PAGES
    # üst bilgi seçilmemeli
    for f in res.findings:
        if "Matematik" in f.text:
            assert not f.selected


def test_clean_removes_only_watermarks(sample, tmp_path):
    res = detector.scan(sample)
    sel = [f for f in res.findings if f.selected]
    out = str(tmp_path / "temiz.pdf")
    st = cleaner.clean_file(sample, sel, out, verify=True)
    assert not st.remaining, [f.title for f in st.remaining]
    a, b = fitz.open(sample), fitz.open(out)
    for wa, wb in zip(_words(a), _words(b)):
        lost, gained = wa - wb, wb - wa
        assert not gained
        assert set(lost) <= {"GIZLI", "www.ornekyayin.com"}, lost
        assert lost["GIZLI"] == 1
    # gerçek resim duruyor, filigran logosu gitti
    assert len(b[2].get_images()) == 1
    assert all(len(b[i].get_images()) == 0 for i in range(PAGES) if i != 2)
    assert all(not p.get_links() for p in b) == ("link" in {f.kind for f in sel})


def test_watermark_annotation(tmp_path):
    path = str(tmp_path / "annot.pdf")
    doc = fitz.open()
    for i in range(3):
        p = doc.new_page()
        p.insert_text((50, 100), f"Icerik {i}", fontsize=12)
        a = p.add_freetext_annot(fitz.Rect(100, 300, 400, 350), "TASLAK", fontsize=30)
        a.update()
        # Watermark alt tipine çevir
        doc.xref_set_key(a.xref, "Subtype", "/Watermark")
    doc.save(path)
    res = detector.scan(path)
    wm = [f for f in res.findings if f.kind == "annot"]
    assert wm and wm[0].selected and len(wm[0].pages) == 3
    out = str(tmp_path / "annot_temiz.pdf")
    cleaner.clean_file(path, wm, out)
    assert all(not list(p.annots()) for p in fitz.open(out))


def test_rules_roundtrip(sample, monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    res = detector.scan(sample)
    text = [f for f in res.findings if f.kind == "text" and f.selected]
    rules.add_rule("Gizli filigranı", text)
    rule = rules.load_rules()[0]
    res2 = detector.scan(sample)
    n = rules.apply_rule(rule, res2.findings)
    assert n == 1 and [f.kind for f in res2.findings if f.selected] == ["text"]


def test_preview_page(sample):
    res = detector.scan(sample)
    sel = [f for f in res.findings if f.selected]
    doc = cleaner.preview_page(sample, sel, 1)
    words = {w[4] for w in doc[1].get_text("words")}
    assert "GIZLI" not in words and "Soru" in words
    assert "GIZLI" in {w[4] for w in doc[0].get_text("words")}


# ---------------------------------------------------------------- taranmış sayfalar

def _scan_like(vector_pdf: str, out: str, dpi: int = 100):
    """Vektör PDF'i taranmış gibi (her sayfa tek JPEG) yeniden üretir; küçük kayma + gürültü ekler."""
    import cv2
    import numpy as np
    rng = np.random.default_rng(0)
    src, dst = fitz.open(vector_pdf), fitz.open()
    for pg in src:
        pix = pg.get_pixmap(dpi=dpi, alpha=False)
        img = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w, 3)
        dx, dy = rng.integers(-2, 3, 2)
        img = cv2.warpAffine(img, np.float32([[1, 0, dx], [0, 1, dy]]), (pix.w, pix.h),
                             borderValue=(255, 255, 255))
        img = np.clip(img + rng.normal(0, 2, img.shape), 0, 255).astype(np.uint8)
        ok, buf = cv2.imencode(".jpg", cv2.cvtColor(img, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 90])
        dst.new_page(width=pg.rect.width, height=pg.rect.height).insert_image(pg.rect, stream=buf.tobytes())
    dst.save(out)


def _vector_pages(path, watermark_pages, color=(0, 0, 0), opacity=0.25):
    doc = fitz.open()
    for i in range(8):
        p = doc.new_page()
        p.draw_rect(fitz.Rect(0, 0, 595, 40), color=None, fill=(1, 0.85, 0))      # sarı başlık bandı
        p.insert_text((50, 28), "Unite 3 - Geometri", fontsize=12)
        for k in range(18):
            p.insert_text((60, 90 + k * 38), f"Soru {i}-{k}: ucgenin ic acilari toplami nedir?", fontsize=13)
        if i in watermark_pages:
            p.insert_text((90, 650), "ORNEK YAYINEVI", fontsize=70, color=color, fill_opacity=opacity,
                          morph=(fitz.Point(90, 650), fitz.Matrix(50)))
    doc.save(path)


@pytest.mark.parametrize("color", [(0, 0, 0), (0.85, 0.1, 0.1)], ids=["gri", "kirmizi"])
def test_scanned_watermark(tmp_path, color):
    import numpy as np
    wm_pages = {2, 3, 4, 5, 6, 7}
    vec, vec_clean = str(tmp_path / "v.pdf"), str(tmp_path / "v0.pdf")
    _vector_pages(vec, wm_pages, color)
    _vector_pages(vec_clean, set(), color)            # filigransız gerçek hâli (karşılaştırma için)
    scan, scan_clean = str(tmp_path / "s.pdf"), str(tmp_path / "s0.pdf")
    _scan_like(vec, scan)
    _scan_like(vec_clean, scan_clean)

    res = detector.scan(scan)
    assert len(res.scanned_pages) == 8
    rf = [f for f in res.findings if f.kind == "raster"]
    assert rf and rf[0].selected
    assert set(rf[0].pages) == wm_pages               # filigransız sayfalar işaretlenmemeli

    out = str(tmp_path / "s_temiz.pdf")
    st = cleaner.clean_file(scan, rf, out)
    assert st.cleaned_images == len(wm_pages)

    def arr(path, i):
        pix = fitz.open(path)[i].get_pixmap(dpi=100, alpha=False)
        return np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w, 3).astype(int)

    for i in range(8):
        before, after, truth = arr(scan, i), arr(out, i), arr(scan_clean, i)
        if i not in wm_pages:
            assert np.abs(before - after).max() == 0  # dokunulmamış
            continue
        # filigranın olduğu yerlerde gerçeğe (filigransız taramaya) yaklaşmalı
        region = np.abs(before - truth).max(axis=2) > 25
        err_before = np.abs(before - truth)[region].mean()
        err_after = np.abs(after - truth)[region].mean()
        assert err_after < 0.35 * err_before, (i, err_before, err_after)
        # filigran dışı alan (yazılar, sarı bant) korunmalı
        assert np.abs(after - truth)[~region].mean() < 3
