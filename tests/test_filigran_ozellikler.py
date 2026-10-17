"""Filigran: elle işaretleme, OCR, şifreli PDF, sayfa aralığı, belge bilgileri testleri (pdfedit'ten taşındı)."""
import collections

import pymupdf as fitz
import pytest

from eaglepdf.core import yazitipi  # noqa: E402
from eaglepdf.core.filigran import cleaner, detector, manual, ocr, pdfops, rules  # noqa: E402

from test_filigran_motor import _scan_like, _vector_pages  # noqa: E402

PAGES = 5
STAR = [(300, 300), (320, 360), (380, 360), (330, 395), (350, 455), (300, 420), (250, 455), (270, 395),
        (220, 360), (280, 360)]


def _words(doc):
    return [collections.Counter(w[4] for w in p.get_text("words")) for p in doc]


@pytest.fixture()
def vector_pdf(tmp_path):
    """Her sayfada aynı vektör yıldız (filigran, otomatik tespit edilemez) + metin filigranı
    (soluk olmayan, döndürülmemiş: otomatik seçilmez) + sayfaya özgü gerçek içerik."""
    path = str(tmp_path / "vektor.pdf")
    doc = fitz.open()
    for i in range(PAGES):
        p = doc.new_page()
        p.insert_text((50, 80), f"Gercek icerik sayfa {i + 1}", fontsize=12)
        p.insert_text((260, 340), f"Soru{i}", fontsize=11)            # yıldızın üstünde gerçek metin
        p.draw_rect(fitz.Rect(50, 600, 150 + 20 * i, 650), color=(0, 0, 1))   # sayfaya özgü çizim
        p.draw_polyline(STAR + [STAR[0]], color=(0.6, 0.6, 0.6), fill=(0.9, 0.9, 0.9), fill_opacity=0.5)
        p.insert_text((230, 480), "KOPYA YAYINEVI", fontsize=14)
    doc.set_metadata({"author": "Kopya Yayinevi", "title": "Deneme", "subject": "www.kopyayayin.com"})
    doc.save(path)
    return path


def _drawings(doc, pno):
    return [(tuple(round(v) for v in d["rect"])) for d in doc[pno].get_drawings()]


def test_manual_vector_and_text(vector_pdf, tmp_path):
    res = detector.scan(vector_pdf, ocr=False)
    box = (215, 290, 390, 490)                       # yıldız + "KOPYA YAYINEVI" + gerçek "Soru0"
    found = manual.search(vector_pdf, res, 0, box)
    kinds = {f.kind: f for f in found}
    assert set(kinds) == {"vector", "text"} and len(found) == 2
    assert kinds["vector"].pages == list(range(PAGES))
    # yarı saydam yıldız filigran benzeri: seçili; düz siyah metin: listede ama seçilmemiş
    assert kinds["vector"].selected and not kinds["text"].selected
    t = kinds["text"]
    assert t.text == "KOPYA YAYINEVI" and t.pages == list(range(PAGES))   # "Soru0" tek sayfada: alınmaz
    out = str(tmp_path / "temiz.pdf")
    st = cleaner.clean_file(vector_pdf, found, out)
    a, b = fitz.open(vector_pdf), fitz.open(out)
    for i in range(PAGES):
        lost = _words(a)[i] - _words(b)[i]
        assert lost == collections.Counter({"KOPYA": 1, "YAYINEVI": 1}), lost
        before, after = _drawings(a, i), _drawings(b, i)
        assert len(after) == len(before) - 1           # yalnızca yıldız gitti
        assert (50, 600, 150 + 20 * i, 650) in after
    assert not st.warnings


def test_manual_image_separate_copies(tmp_path):
    """Logo her sayfaya ayrı nesne olarak gömülmüş: içerik özetiyle tek bulgu olmalı."""
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 40, 40), False)
    pix.set_rect(pix.irect, (10, 120, 200))
    png = pix.tobytes("png")
    path = str(tmp_path / "logo.pdf")
    doc = fitz.open()
    for i in range(4):
        p = doc.new_page()
        p.insert_text((50, 80), f"Metin {i}", fontsize=12)
        p.insert_image(fitz.Rect(500, 20, 560, 80), stream=png)
    doc.save(path, garbage=0)
    d2 = fitz.open(path)
    xrefs = {d2[i].get_images()[0][0] for i in range(4)}
    res = detector.scan(path, ocr=False)
    imgs = [f for f in res.findings if f.kind == "image"]
    if len(xrefs) > 1:
        assert len(imgs) == 1 and len(imgs[0].pages) == 4
    found = manual.search(path, res, 1, (490, 10, 570, 90))
    assert len(found) == 1 and found[0].kind == "image" and len(found[0].pages) == 4
    out = str(tmp_path / "logo_temiz.pdf")
    cleaner.clean_file(path, found, out)
    assert all(not p.get_images() for p in fitz.open(out))


def test_page_range_and_metadata(vector_pdf, tmp_path):
    res = detector.scan(vector_pdf, ocr=False)
    meta = [f for f in res.findings if f.kind == "meta"]
    assert meta and meta[0].selected and "www.kopyayayin.com" in meta[0].urls
    found = manual.search(vector_pdf, res, 0, (215, 460, 390, 490))         # yalnızca metin
    assert [f.kind for f in found] == ["text"]
    pages = pdfops.page_selection("2-4", "3", PAGES)                         # {1, 3}
    assert pages == {1, 3}
    out = str(tmp_path / "aralik.pdf")
    st = cleaner.clean_file(vector_pdf, found + meta, out, pages=pages, verify=True)
    b = fitz.open(out)
    for i in range(PAGES):
        has = "KOPYA" in {w[4] for w in b[i].get_text("words")}
        assert has == (i not in pages), i
    assert st.removed_meta >= 3
    assert not b.metadata.get("author") and not b.metadata.get("subject")
    assert not st.remaining


def test_password_pdf(vector_pdf, tmp_path):
    enc = str(tmp_path / "sifreli.pdf")
    fitz.open(vector_pdf).save(enc, encryption=fitz.PDF_ENCRYPT_AES_256, user_pw="1234", owner_pw="sahip")
    with pytest.raises(pdfops.PasswordRequired):
        detector.scan(enc, ocr=False)
    assert not pdfops.try_password(enc, "yanlis")
    assert pdfops.try_password(enc, "1234")
    pdfops.set_password(enc, "1234")
    try:
        res = detector.scan(enc, ocr=False)
        found = manual.search(enc, res, 0, (215, 460, 390, 490))
        out = str(tmp_path / "sifreli_temiz.pdf")
        st = cleaner.clean_file(enc, found, out, verify=True)
        assert st.encrypted and not st.remaining
        d = fitz.open(out)
        assert d.needs_pass and d.authenticate("1234")
        assert "KOPYA" not in d[0].get_text()
        out2 = str(tmp_path / "sifresiz_temiz.pdf")
        cleaner.clean_file(enc, found, out2, keep_encryption=False)
        assert not fitz.open(out2).needs_pass
    finally:
        pdfops.set_password(enc, None)


def test_parse_pages():
    assert pdfops.parse_pages("1-3, 8 10-", 12) == {0, 1, 2, 7, 9, 10, 11}
    assert pdfops.parse_pages("-2", 5) == {0, 1}
    assert pdfops.page_selection("", "", 5) is None
    assert pdfops.page_selection("", "1", 3) == {1, 2}
    with pytest.raises(ValueError):
        pdfops.parse_pages("3-1", 5)
    with pytest.raises(ValueError):
        pdfops.parse_pages("abc", 5)


@pytest.mark.skipif(not ocr.available(), reason="OCR motoru yok")
def test_ocr_scanned_watermark(tmp_path):
    vec = str(tmp_path / "v.pdf")
    _vector_pages(vec, {1, 2, 3, 4, 5, 6, 7})
    scan = str(tmp_path / "s.pdf")
    _scan_like(vec, scan)
    res = detector.scan(scan)
    rf = [f for f in res.findings if f.kind == "raster"][0]
    assert "YAYINEVI" in rf.text.replace(" ", "").upper() or "YAYINEV" in rf.text.upper(), rf.text


@pytest.mark.skipif(not ocr.available(), reason="OCR motoru yok")
def test_ocr_image_url(tmp_path):
    """Logo resmindeki adres okunmalı."""
    src = fitz.open()
    pg = src.new_page(width=300, height=60)
    pg.insert_text((10, 40), "www.ornekyayin.com", fontsize=24)
    png = pg.get_pixmap(dpi=150).tobytes("png")
    path = str(tmp_path / "logo_url.pdf")
    doc = fitz.open()
    for i in range(4):
        p = doc.new_page()
        p.insert_text((50, 80), f"Metin {i}", fontsize=12)
        p.insert_image(fitz.Rect(300, 780, 550, 830), stream=png)
    doc.save(path)
    res = detector.scan(path)
    img = [f for f in res.findings if f.kind == "image"][0]
    assert any("ornekyayin.com" in u for u in img.urls), (img.text, img.urls)


# ---------------------------------------------------------------- Tesseract tabanlı OCR (EaglePDF'e özgü)
def _yazi_resmi(metin, boyut=70, aci=0, gurultu=False):
    """Beyaz zemin üstünde siyah tek satır yazı (gri numpy). aci=180 → ters yön."""
    import cv2
    import numpy as np
    d = fitz.open()
    p = d.new_page(width=900, height=140)
    p.insert_font(fontname="noto", fontbuffer=yazitipi.tampon())   # Helvetica ş/ğ/ı/İ çizmez: gömülü Noto Sans
    p.insert_text((20, 95), metin, fontsize=boyut, fontname="noto")
    pix = p.get_pixmap(dpi=72, alpha=False, colorspace=fitz.csGRAY)
    im = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w).copy()
    if aci == 180:
        im = cv2.rotate(im, cv2.ROTATE_180)
    if gurultu:
        im = cv2.GaussianBlur(im, (0, 0), 1.6)
        im = np.clip(im.astype(int) + np.random.default_rng(1).normal(0, 12, im.shape), 0, 255).astype(np.uint8)
    return im


def _norm(t):
    return ocr._anahtar(t)


@pytest.mark.skipif(not ocr.available(), reason="OCR dil verisi kurulu değil")
@pytest.mark.parametrize("aci", [0, 180], ids=["duz", "ters"])
@pytest.mark.parametrize("gurultu", [False, True], ids=["temiz", "gurultulu"])
def test_ocr_yazi_yonleri(aci, gurultu):
    t = ocr.read_text_image(_yazi_resmi("ORNEK YAYINEVI", aci=aci, gurultu=gurultu))
    assert _norm(t) == "ornekyayinevi", t


@pytest.mark.skipif(not ocr.available(), reason="OCR dil verisi kurulu değil")
def test_ocr_turkce_harfler():
    t = ocr.read_text_image(_yazi_resmi("Işık İstanbul şğüöç", boyut=60))
    for kelime in ("Işık", "İstanbul", "şğüöç"):
        assert kelime in t, t   # RapidOCR'da İ/Ö/Ş → I/O/S çıkıyordu: Tesseract Türkçe ile doğru


def test_ocr_makullugu():
    assert ocr._plausible("Editor Yayinlari") and ocr._plausible("www.ornek.com")
    assert not ocr._plausible("") and not ocr._plausible("12 !!") and not ocr._plausible("ab") and not ocr._plausible("|||| ---- ====")
    assert ocr._anahtar("YAYINEVİ") == ocr._anahtar("yayinevi") == ocr._anahtar("Y a y i n e v i")


def test_ocr_dil_verisi_yoksa_okuma_yapmaz(monkeypatch):
    monkeypatch.setattr(ocr, "dil_sec", lambda: None)
    assert not ocr.available() and "Dil Verisi" in ocr.unavailable_reason()
    assert ocr.read_text_image(_yazi_resmi("ORNEK")) == "" and ocr.read_image(None, 1) == ""


def test_kurallar_eski_uygulamadan_devralinir(tmp_path, monkeypatch):
    """EaglePDF'in kendi kural dosyası yoksa eski (PDFFiligran) uygulamanın kuralları okunur; yazma kendi dosyamıza olur."""
    import json
    monkeypatch.setenv("APPDATA", str(tmp_path))
    eski = tmp_path / "PDFFiligran"
    eski.mkdir()
    (eski / "rules.json").write_text(json.dumps([{"name": "Eski kural", "matches": [{"kind": "text", "text": "X"}]}]), encoding="utf-8")
    assert [r["name"] for r in rules.load_rules()] == ["Eski kural"]
    rules.add_rule("Yeni", [type("F", (), {"signature": {"kind": "image"}})()])
    assert [r["name"] for r in rules.load_rules()] == ["Eski kural", "Yeni"]   # eskiler devralındı, yenisi eklendi
    assert (tmp_path / "EaglePDF" / "filigran_kurallari.json").is_file()
    assert json.loads((eski / "rules.json").read_text(encoding="utf-8"))[0]["name"] == "Eski kural"   # eskisine dokunulmadı
