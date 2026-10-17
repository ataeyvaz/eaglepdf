"""Filigran: yalnızca vektör çizimden oluşan filigranın otomatik tespiti ve 1-bit (siyah-beyaz) taramalarda ortak piksel deseni."""
import io

import numpy as np
import pymupdf as fitz
import pytest
from PIL import Image

from eaglepdf.core.filigran import cleaner, detector

PAGES = 6


def vektor_belge(yol, filigran_sayfalari=range(PAGES), n=PAGES):
    """Her sayfada: kendine özgü yazı + tekrar eden üst çizgi (opak, ince) + sarı başlık bandı; filigran: yarı saydam gri yıldız."""
    doc = fitz.open()
    for i in range(n):
        p = doc.new_page()
        p.draw_rect(fitz.Rect(0, 0, 595, 40), color=None, fill=(1, 0.85, 0))            # başlık bandı (sayfa tasarımı)
        p.draw_line((40, 60), (555, 60), color=(0, 0, 0), width=0.8)                      # üst çizgi (sayfa düzeni)
        p.insert_text((60, 110), f"Soru {i + 1}: ucgenin ic acilari toplami nedir?", fontsize=12)
        if i in filigran_sayfalari:
            merkez = fitz.Point(300, 450)
            noktalar = []
            for k in range(10):                                                           # 5 köşeli yıldız
                yaricap = 150 if k % 2 == 0 else 60
                aci = np.pi / 2 + k * np.pi / 5
                noktalar.append(fitz.Point(merkez.x + yaricap * np.cos(aci), merkez.y - yaricap * np.sin(aci)))
            p.draw_polyline(noktalar + [noktalar[0]], color=None, fill=(0.5, 0.5, 0.5), fill_opacity=0.25, closePath=True)
    doc.save(yol)
    doc.close()
    return str(yol)


def test_tekrar_eden_vektor_filigrani_bulunur_sayfa_duzeni_secilmez(tmp_path):
    yol = vektor_belge(tmp_path / "v.pdf")
    sonuc = detector.scan(yol, ocr=False)
    vek = [f for f in sonuc.findings if f.kind == "vector"]
    assert len(vek) >= 2
    secili = [f for f in vek if f.selected]
    assert len(secili) == 1 and set(secili[0].pages) == set(range(PAGES))
    assert "yarı saydam" in " ".join(secili[0].reasons)
    # sarı bant ve ince çizgi bulundu ama seçilmedi
    secilmeyen = " ".join(" ".join(f.reasons) for f in vek if not f.selected)
    assert "bant" in secilmeyen and "ince çizgi" in secilmeyen


def test_vektor_filigran_silinince_yalniz_filigran_gider(tmp_path):
    yol = vektor_belge(tmp_path / "v.pdf")
    sonuc = detector.scan(yol, ocr=False)
    cikti = str(tmp_path / "temiz.pdf")
    st = cleaner.clean_file(yol, [f for f in sonuc.findings if f.selected], cikti, verify=True)
    assert not [f for f in st.remaining if f.kind == "vector" and f.selected]

    def piksel(yol_, sayfa, x, y):
        d = fitz.open(yol_)
        px = d[sayfa].get_pixmap(dpi=72, alpha=False)
        return px.pixel(x, y)
    for sayfa in range(PAGES):
        assert piksel(yol, sayfa, 300, 450) != (255, 255, 255)        # önce: yıldızın ortasında gri
        assert piksel(cikti, sayfa, 300, 450) == (255, 255, 255)      # sonra: temiz
        assert abs(piksel(cikti, sayfa, 300, 20)[1] - 217) <= 2 and piksel(cikti, sayfa, 300, 20)[2] == 0   # sarı bant yerinde
    metin = "".join(p.get_text() for p in fitz.open(cikti))
    assert "Soru 1" in metin and "Soru 6" in metin


def test_tek_sayfada_olan_cizim_filigran_sayilmaz(tmp_path):
    yol = vektor_belge(tmp_path / "t.pdf", filigran_sayfalari=[2])
    vek = [f for f in detector.scan(yol, ocr=False).findings if f.kind == "vector" and f.selected]
    assert not vek


def test_vektor_tek_sayfalik_belgede_aranmaz(tmp_path):
    yol = vektor_belge(tmp_path / "bir.pdf", n=1)
    assert not [f for f in detector.scan(yol, ocr=False).findings if f.kind == "vector"]


# --- 1-bit taramalar ---
def _bayer(h, w):
    m = np.array([[0, 32, 8, 40, 2, 34, 10, 42], [48, 16, 56, 24, 50, 18, 58, 26], [12, 44, 4, 36, 14, 46, 6, 38],
                  [60, 28, 52, 20, 62, 30, 54, 22], [3, 35, 11, 43, 1, 33, 9, 41], [51, 19, 59, 27, 49, 17, 57, 25],
                  [15, 47, 7, 39, 13, 45, 5, 37], [63, 31, 55, 23, 61, 29, 53, 21]], np.float32) / 64.0
    return np.tile(m, (h // 8 + 1, w // 8 + 1))[:h, :w]


def bitlik_belge(yol, filigranli=True, n=PAGES, dpi=150):
    """Vektör sayfayı gri tonda çizip sıralı (Bayer) titreşimle 1-bit yapar: filigran her sayfada AYNI piksel desenini verir."""
    kaynak = fitz.open()
    rng = np.random.default_rng(7)
    kelimeler = ["ucgen", "aci", "kenar", "toplam", "orani", "yarim", "cember", "alan", "hacim", "dogru", "nokta", "cevap", "soru", "isik"]
    for i in range(n):
        p = kaynak.new_page()
        p.insert_text((60, 40), "Matematik Ders Notlari", fontsize=10)               # her sayfada tekrar eden üstbilgi (filigran değil)
        for k in range(18):                                                          # gövde metni sayfadan sayfaya değişir
            p.insert_text((60, 90 + k * 38), " ".join(rng.choice(kelimeler, 7)), fontsize=13)
        if filigranli:
            p.insert_text((90, 650), "ORNEK YAYINEVI", fontsize=70, color=(0, 0, 0), fill_opacity=0.3,
                          morph=(fitz.Point(90, 650), fitz.Matrix(50)))
    hedef = fitz.open()
    for pg in kaynak:
        pix = pg.get_pixmap(dpi=dpi, alpha=False, colorspace=fitz.csGRAY)
        gri = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w).astype(np.float32) / 255.0
        bit = gri > _bayer(pix.h, pix.w)                                              # True = beyaz
        im = Image.fromarray((bit * 255).astype(np.uint8)).convert("1", dither=Image.Dither.NONE)
        b = io.BytesIO()
        im.save(b, "PNG")
        hedef.new_page(width=pg.rect.width, height=pg.rect.height).insert_image(pg.rect, stream=b.getvalue())
    hedef.save(yol)
    hedef.close()
    return str(yol)


def test_bit_sayfalarda_ortak_desen_bulunur_ama_otomatik_secilmez(tmp_path):
    yol = bitlik_belge(tmp_path / "b.pdf")
    sonuc = detector.scan(yol, ocr=False)
    assert len(sonuc.bilevel_pages) == PAGES and not sonuc.scanned_pages
    bf = [f for f in sonuc.findings if f.kind == "raster" and f.signature.get("bilevel")]
    assert len(bf) == 1 and not bf[0].selected and set(bf[0].pages) == set(range(PAGES))
    assert "deneysel" in " ".join(bf[0].reasons)


def test_bit_filigran_silinir_yazi_korunur(tmp_path):
    yol = bitlik_belge(tmp_path / "b.pdf")
    temiz = bitlik_belge(tmp_path / "gercek.pdf", filigranli=False)      # filigransız gerçek hâl (karşılaştırma)
    sonuc = detector.scan(yol, ocr=False)
    bf = next(f for f in sonuc.findings if f.kind == "raster" and f.signature.get("bilevel"))
    cikti = str(tmp_path / "bt.pdf")
    st = cleaner.clean_file(yol, [bf], cikti)
    assert st.cleaned_images == PAGES

    def gri(yol_, i):
        pix = fitz.open(yol_)[i].get_pixmap(dpi=150, alpha=False, colorspace=fitz.csGRAY)
        return np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w).astype(int)
    for i in range(PAGES):
        once, sonra, gercek = gri(yol, i), gri(cikti, i), gri(temiz, i)
        bolge = np.abs(once - gercek) > 100                                           # filigranın ve yazının farklı olduğu pikseller
        hata_once = bolge.sum()
        hata_sonra = (np.abs(sonra - gercek) > 100).sum()
        assert hata_sonra < 0.15 * hata_once, (i, hata_once, hata_sonra)              # filigran piksellerinin ≥ %85'i temizlendi
        # filigran dışı yazı (üst kısım) piksel piksel aynı
        assert np.abs(sonra[:300] - gercek[:300]).max() == 0
    cikis = fitz.open(cikti)
    assert cikis[0].get_images(full=True)[0][4] == 1                                 # hâlâ 1-bit


def test_bit_sayfa_azsa_aranmaz(tmp_path):
    yol = bitlik_belge(tmp_path / "iki.pdf", n=2)
    sonuc = detector.scan(yol, ocr=False)
    assert not [f for f in sonuc.findings if f.signature.get("bilevel")]
