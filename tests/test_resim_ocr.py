import io

import pymupdf
import pytest
from PIL import Image

from eaglepdf.core import donustur, ocr, resim_ocr, yazitipi
from eaglepdf.core.belge import Belge
from eaglepdf.core.hatalar import BelgeHatasi
from eaglepdf.core.resim_ocr import resimlerden_ocr

pytestmark = pytest.mark.skipif(not ocr.hazir_mi("eng"), reason="İngilizce OCR dil verisi kurulu değil")


def metin_resmi(metin: str, boyut: int = 30, genislik: int = 900, yukseklik: int = 160) -> Image.Image:
    """Beyaz zemin üzerine siyah metin (Noto Sans: Türkçe harfli) çizilmiş PIL resmi."""
    doc = pymupdf.open()
    s = doc.new_page(width=genislik, height=yukseklik)
    s.insert_font(fontname="noto", fontbuffer=yazitipi.tampon())
    s.insert_text((30, yukseklik / 2 + boyut / 3), metin, fontsize=boyut, fontname="noto")
    pix = s.get_pixmap(dpi=150, alpha=False)
    doc.close()
    return Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")


def kaydet(im: Image.Image, yol, **kw):
    im.save(yol, **kw)
    return yol


@pytest.mark.parametrize("uzanti", [".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp", ".gif"])
def test_tum_resim_bicimleri_okunur(tmp_path, uzanti):
    yol = kaydet(metin_resmi("Hello World report"), tmp_path / f"r{uzanti}")
    s = resimlerden_ocr([yol], dil="eng")
    assert len(s.sayfalar) == 1 and "Hello" in s.sayfalar[0].metin and "World" in s.sayfalar[0].metin, s.sayfalar[0].metin
    assert s.sayfalar[0].kaynak == f"r{uzanti}" and s.sayfalar[0].kare == 0 and not s.hatalar


def test_resim_mi():
    assert all(resim_ocr.resim_mi(f"a{u}") for u in (".PNG", ".Jpg", ".tiff", ".WEBP"))
    assert not resim_ocr.resim_mi("a.pdf") and not resim_ocr.resim_mi("resim") and not resim_ocr.resim_mi("a.txt")


def test_cok_kareli_tiff_her_kare_ayri_sayfa(tmp_path):
    kareler = [metin_resmi(m) for m in ("First frame alpha", "Second frame bravo", "Third frame charlie")]
    yol = tmp_path / "cok.tif"
    kareler[0].save(yol, save_all=True, append_images=kareler[1:])
    assert resim_ocr.kare_sayisi(yol) == 3
    s = resimlerden_ocr([yol], dil="eng")
    assert [p.kare for p in s.sayfalar] == [1, 2, 3]
    assert "alpha" in s.sayfalar[0].metin and "bravo" in s.sayfalar[1].metin and "charlie" in s.sayfalar[2].metin
    metin = s.toplu_metin()
    assert "— cok.tif (kare 1) —" in metin and metin.index("alpha") < metin.index("bravo") < metin.index("charlie")
    assert pymupdf.open("pdf", s.pdf).page_count == 3


def test_exif_dondurulmus_fotograf_duz_okunur(tmp_path):
    """Telefon fotoğrafı: piksel olarak yan yatık saklanır, EXIF yönü 6 (90° saat yönü) der. Metin düz okunmalı."""
    duz = metin_resmi("Upright sentence here")
    yan = duz.rotate(90, expand=True)   # saat yönünün tersi 90°: EXIF 6 bunu saat yönünde 90° döndürerek düzeltir
    exif = Image.Exif()
    exif[274] = 6
    yol = tmp_path / "foto.jpg"
    yan.save(yol, exif=exif)
    s = resimlerden_ocr([yol], dil="eng")
    assert "Upright" in s.sayfalar[0].metin and "sentence" in s.sayfalar[0].metin, s.sayfalar[0].metin


def test_saydam_png_beyaza_duzlestirilir(tmp_path):
    yol = tmp_path / "saydam.png"
    rgba = metin_resmi("Transparent background text").convert("RGBA")
    veri = [(r, g, b, 0 if (r, g, b) == (255, 255, 255) else 255) for r, g, b, a in rgba.getdata()]   # beyaz zemin saydam
    rgba.putdata(veri)
    rgba.save(yol)
    s = resimlerden_ocr([yol], dil="eng")
    assert "Transparent" in s.sayfalar[0].metin and "background" in s.sayfalar[0].metin


def test_yatay_resim_yatay_sayfa_dikey_resim_dikey_sayfa(tmp_path):
    yatay = kaydet(metin_resmi("Wide image", genislik=1000, yukseklik=200), tmp_path / "yatay.png")
    dikey = kaydet(metin_resmi("Tall", genislik=200, yukseklik=1000), tmp_path / "dikey.png")
    s = resimlerden_ocr([yatay, dikey], dil="eng")
    d = pymupdf.open("pdf", s.pdf)
    assert d[0].rect.width > d[0].rect.height and d[1].rect.width < d[1].rect.height
    d.close()


def test_pdf_ciktisi_aranabilir_ve_resim_gorunur(tmp_path):
    yol = kaydet(metin_resmi("Searchable output check"), tmp_path / "a.png")
    s = resimlerden_ocr([yol], dil="eng")
    (tmp_path / "o.pdf").write_bytes(s.pdf)
    b = Belge.ac(tmp_path / "o.pdf")
    try:
        assert b.sayfa_sayisi == 1 and b.ara("searchable")                    # görünmez metin katmanı aranabilir
        assert b._doc[0].get_images()                                         # resim yerinde duruyor
    finally:
        b.kapat()


def test_bozuk_dosya_digerlerini_durdurmaz(tmp_path):
    iyi = kaydet(metin_resmi("Good image ok"), tmp_path / "iyi.png")
    bozuk = tmp_path / "bozuk.png"
    bozuk.write_bytes(b"png degil")
    yok = tmp_path / "yok.jpg"
    s = resimlerden_ocr([bozuk, iyi, yok], dil="eng")
    assert len(s.sayfalar) == 1 and "Good" in s.sayfalar[0].metin
    assert len(s.hatalar) == 2 and any("bozuk.png" in h for h in s.hatalar) and any("yok.jpg" in h for h in s.hatalar)


def test_hicbiri_okunamazsa_hata(tmp_path):
    bozuk = tmp_path / "bozuk.png"
    bozuk.write_bytes(b"x")
    with pytest.raises(BelgeHatasi, match="Okunabilir resim bulunamadı"):
        resimlerden_ocr([bozuk], dil="eng")
    with pytest.raises(BelgeHatasi, match="Resim seçilmedi"):
        resimlerden_ocr([], dil="eng")


def test_iptal(tmp_path):
    yollar = [kaydet(metin_resmi(f"Page number {i}"), tmp_path / f"p{i}.png") for i in range(3)]
    with pytest.raises(ocr.OcrIptal):
        resimlerden_ocr(yollar, dil="eng", ilerleme=lambda n, t: n >= 1)


def test_ilerleme_sayfa_sayisina_gore(tmp_path):
    yollar = [kaydet(metin_resmi(f"Item {i}"), tmp_path / f"p{i}.png") for i in range(2)]
    gorulen = []
    resimlerden_ocr(yollar, dil="eng", ilerleme=lambda n, t: gorulen.append((n, t)) or False)
    assert gorulen[-1] == (2, 2) and all(t == 2 for _, t in gorulen)


def test_dil_verisi_yoksa_anlasilir_hata(tmp_path):
    yol = kaydet(metin_resmi("x"), tmp_path / "a.png")
    with pytest.raises(BelgeHatasi, match="dil verisi"):
        resimlerden_ocr([yol], dil="xyz")


def test_dpi_siniri(tmp_path):
    yol = kaydet(metin_resmi("x"), tmp_path / "a.png")
    for kotu in (50, 700):
        with pytest.raises(BelgeHatasi, match="DPI"):
            resimlerden_ocr([yol], dil="eng", dpi=kotu)


def test_asiri_buyuk_resim_reddedilir(tmp_path, monkeypatch):
    yol = kaydet(metin_resmi("x"), tmp_path / "a.png")
    monkeypatch.setattr(donustur, "EN_COK_PIKSEL", 1000)
    with pytest.raises(BelgeHatasi, match="Okunabilir resim bulunamadı") as h:
        resimlerden_ocr([yol], dil="eng")
    assert "çok büyük" in str(h.value)


def test_bos_resim_bos_metin_ama_hata_degil(tmp_path):
    beyaz = Image.new("RGB", (800, 400), "white")
    yol = kaydet(beyaz, tmp_path / "bos.png")
    s = resimlerden_ocr([yol], dil="eng")
    assert s.bos_mu and len(s.sayfalar) == 1 and s.pdf


@pytest.mark.skipif(not ocr.hazir_mi("tur"), reason="Türkçe dil verisi kurulu değil")
def test_turkce_karakterler(tmp_path):
    yol = kaydet(metin_resmi("Işık İstanbul şğüöç", boyut=40), tmp_path / "tr.png")
    s = resimlerden_ocr([yol], dil="tur+eng")
    m = s.sayfalar[0].metin
    for kelime in ("Işık", "İstanbul", "şğüöç"):
        assert kelime in m, m


def test_toplu_metin_tek_sayfada_baslik_yok(tmp_path):
    s = resim_ocr.ResimOcrSonucu(sayfalar=[resim_ocr.SayfaMetni("a.png", 0, "yalın metin")])
    assert s.toplu_metin() == "yalın metin"
    iki = resim_ocr.ResimOcrSonucu(sayfalar=[resim_ocr.SayfaMetni("a.png", 0, "bir"), resim_ocr.SayfaMetni("b.png", 0, "iki")])
    assert iki.toplu_metin() == "— a.png —\n\nbir\n\n— b.png —\n\niki"
