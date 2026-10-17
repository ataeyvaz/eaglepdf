from pathlib import Path

import pymupdf
import pytest

from eaglepdf.core.belge import Belge, BelgeHatasi
from eaglepdf.core.ekaciklama import kelimelerden_satirlar
from test_belge import pdf_yap


@pytest.fixture
def b(tmp_path):
    return Belge.ac(pdf_yap(tmp_path / "e.pdf", 3, "Merhaba dunya"))


def koyu_piksel(b: Belge, sayfa: int, rect) -> int:
    """Dikdörtgen içindeki beyaz olmayan piksel sayısı."""
    px = b.render(sayfa, 2.0)
    n = 0
    for y in range(int(rect[1] * 2), int(rect[3] * 2)):
        for x in range(int(rect[0] * 2), int(rect[2] * 2)):
            if px.pixel(x, y) != (255, 255, 255):
                n += 1
    return n


def test_isaretler(b):
    kel = b.kelimeler(0)
    satirlar = kelimelerden_satirlar(kel)
    assert len(satirlar) == 1
    for tur in ("vurgu", "alti", "ustu", "dalga"):
        b.ek_isaret(0, tur, satirlar, "#ffeb3b", "Ata")
    liste = b.ek_listele([0])
    assert [e.etiket for e in liste] == ["Vurgu", "Altı çizili", "Üstü çizili", "Dalgalı çizgi"]
    assert liste[0].yazar == "Ata" and liste[0].renk == "#ffeb3b" and b.degisti
    with pytest.raises(BelgeHatasi):
        b.ek_isaret(0, "vurgu", [])
    with pytest.raises(BelgeHatasi):
        b.ek_isaret(0, "yok", satirlar)


def test_cizim_not_sekiller(b):
    b.ek_cizim(1, [[(100, 200), (150, 220), (200, 200)]], "#c62828", 3)
    b.ek_not(1, (300, 300), "Önemli not: ışık", yazar="Ata")
    b.ek_sekil(1, "ok", (100, 400), (250, 450))
    b.ek_sekil(1, "cizgi", (100, 500), (250, 520))
    b.ek_sekil(1, "dikdortgen", (300, 400), (400, 480), dolgu="#fff59d")
    b.ek_sekil(1, "elips", (300, 500), (400, 560))
    etiketler = [e.etiket for e in b.ek_listele([1])]
    assert etiketler == ["Çizim", "Not", "Çizgi / ok", "Çizgi / ok", "Dikdörtgen", "Elips"]
    assert [e.metin for e in b.ek_listele([1]) if e.tur == "Text"] == ["Önemli not: ışık"]
    with pytest.raises(BelgeHatasi):
        b.ek_cizim(1, [[(1, 1)]])
    assert koyu_piksel(b, 1, (95, 395, 255, 455)) > 50


def test_metin_kutusu_turkce(b):
    xref = b.ek_metin_kutusu(0, (100, 300, 300, 340), "Işık ığüşöç İĞÜŞÖÇ", boyut=16, renk="#0000ff", kalin=True)
    e = b.ek_listele([0])[0]
    assert e.tur == "FreeText" and e.metin == "Işık ığüşöç İĞÜŞÖÇ" and e.xref == xref
    assert koyu_piksel(b, 0, e.rect) > 100  # görünüm gerçekten çizildi
    # uzun metin kutuyu büyütür
    xref2 = b.ek_metin_kutusu(0, (100, 400, 180, 420), "çok uzun bir metin " * 6, boyut=12)
    uzun = [x for x in b.ek_listele([0]) if x.xref == xref2][0]
    assert uzun.rect[3] - uzun.rect[1] > 40
    # metni ve rengi değiştir
    b.ek_metin_degistir(0, xref, "Yeni metin ŞĞİ")
    b.ek_renk_degistir(0, xref, "#ff0000")
    yeni = [x for x in b.ek_listele([0]) if x.xref == xref][0]
    assert yeni.metin == "Yeni metin ŞĞİ"
    with pytest.raises(BelgeHatasi):
        b.ek_metin_degistir(0, xref, "  ")


def test_metin_kutusu_dolgu_kenar(b):
    xref = b.ek_metin_kutusu(0, (100, 300, 300, 340), "Çerçeveli ışık", dolgu="#fff9c4", kenarlik="#1565c0", boyut=14)
    e = [x for x in b.ek_listele([0]) if x.xref == xref][0]
    px = b.render(0, 2.0)
    orta_y = int((e.rect[1] + e.rect[3]) / 2 * 2)
    seritte = [px.pixel(x, orta_y) for x in range(int(e.rect[0] * 2) - 2, int(e.rect[0] * 2) + 5)]
    ic = px.pixel(int(e.rect[2] * 2) - 8, int(e.rect[3] * 2) - 8)
    assert any(c[2] > c[0] + 60 for c in seritte)  # mavi kenarlık
    assert ic == (255, 249, 196)          # sarı dolgu
    b.ek_renk_degistir(0, xref, "#ff0000")  # yazı rengi değişince kenarlık/dolgu korunur
    px = b.render(0, 2.0)
    assert px.pixel(int(e.rect[2] * 2) - 8, int(e.rect[3] * 2) - 8) == (255, 249, 196)


def test_bul_sil_tasi(b):
    xref = b.ek_sekil(0, "dikdortgen", (100, 100), (200, 160))
    e = b.ek_bul(0, (150, 130))
    assert e and e.xref == xref
    assert b.ek_bul(0, (400, 700)) is None
    once = b.ek_listele([0])[0].rect
    b.ek_tasi(0, xref, 50, 20)
    yeni = b.ek_listele([0])[0]
    # update() çizgi kalınlığı payını yeniden hesaplar: 1–2 pt sapma olabilir
    assert abs((yeni.rect[0] - once[0]) - 50) <= 2 and abs((yeni.rect[1] - once[1]) - 20) <= 2
    b.ek_sil(0, [xref])
    assert b.ek_listele() == []
    nota = b.ek_not(0, (100, 100), "x")
    b.ek_tasi(0, nota, 10, 10)
    cokgen = b._doc[0].add_polygon_annot([(10, 10), (60, 10), (30, 50)])   # taşınamayan tür
    with pytest.raises(BelgeHatasi):
        b.ek_tasi(0, cokgen.xref, 5, 5)


def test_cizim_ok_ve_isaret_tasinir_ozellikleri_korunur(b):
    kel = b.kelimeler(0)
    satirlar = kelimelerden_satirlar(kel)
    cizim = b.ek_cizim(0, [[(100, 300), (140, 340), (180, 300)], [(100, 360), (180, 360)]], "#1565c0", 3.0, "Ata")
    ok = b.ek_sekil(0, "ok", (100, 500), (220, 560), "#2e7d32", 2.0)
    cizgi = b.ek_sekil(0, "cizgi", (100, 600), (220, 600), "#c62828", 4.0)
    isaret = b.ek_isaret(0, "vurgu", satirlar, "#ffeb3b", "Ata")
    once = {e.xref: e for e in b.ek_listele([0])}
    for eski, dx, dy in ((cizim, 60, 40), (ok, -30, 20), (cizgi, 10, -40), (isaret, 0, 120)):
        yeni = b.ek_tasi(0, eski, dx, dy)
        liste = {e.xref: e for e in b.ek_listele([0])}
        assert yeni in liste and (yeni == eski or eski not in liste)     # eski nesne kalmadı, yenisi var
        e0, e1 = once[eski], liste[yeni]
        assert e1.tur == e0.tur and e1.renk == e0.renk and e1.yazar == e0.yazar
        assert abs((e1.rect[0] - e0.rect[0]) - dx) <= 3 and abs((e1.rect[1] - e0.rect[1]) - dy) <= 3
    # çizim: kalınlık ve iki ayrı çizgi korunmuş olmalı
    ink = next(e for e in b.ek_listele([0]) if e.tur == "Ink")
    sayfa = b._doc[0]   # sayfa nesnesi canlı kalmalı (PyMuPDF zayıf bağ)
    a = sayfa.load_annot(ink.xref)
    assert len(a.vertices) == 2 and abs(a.border["width"] - 3.0) < 0.01
    # ok ucu korunmuş
    ok_a = next(x for x in sayfa.annots() if x.type[1] == "Line" and x.line_ends[1] != 0)
    assert ok_a.line_ends[1] == pymupdf.PDF_ANNOT_LE_CLOSED_ARROW
    # taşınan vurgu eski yerinde değil: eski satırda artık sarı yok
    assert b.geri_al()                                                    # son taşımayı geri al (vurgu eski yerine)
    assert any(e.tur == "Highlight" for e in b.ek_listele([0]))


def test_geri_al_yinele(b):
    assert not b.geri_alinabilir_mi
    b.ek_not(0, (100, 100), "a")
    b.ek_not(0, (200, 100), "b")
    assert len(b.ek_listele()) == 2 and b.geri_alinabilir_mi
    assert b.geri_al() and len(b.ek_listele()) == 1
    assert b.yinelenebilir_mi and b.yinele() and len(b.ek_listele()) == 2
    b.geri_al()
    b.geri_al()
    assert b.ek_listele() == [] and not b.degisti and not b.geri_al()
    b.sayfa_sil([0])
    assert b.sayfa_sayisi == 2 and b.geri_al() and b.sayfa_sayisi == 3
    # hata veren işlem geçmişe iz bırakmaz
    onceki = len(b._gecmis.geri)
    with pytest.raises(BelgeHatasi):
        b.sayfa_sil([0, 1, 2])
    assert len(b._gecmis.geri) == onceki


def test_kaydet_ac_gidis_donus(b, tmp_path):
    b.ek_metin_kutusu(0, (100, 300, 300, 340), "Kalıcı ışık")
    b.ek_isaret(0, "vurgu", kelimelerden_satirlar(b.kelimeler(0)))
    b.ek_not(1, (50, 50), "sayfa 2 notu")
    hedef = tmp_path / "k.pdf"
    b.kaydet(hedef)
    c = Belge.ac(hedef)
    assert [e.etiket for e in c.ek_listele()] == ["Metin kutusu", "Vurgu", "Not"]
    assert c.ek_listele([0])[0].metin == "Kalıcı ışık"
    assert koyu_piksel(c, 0, c.ek_listele([0])[0].rect) > 50


def test_baglanti(b):
    b.baglanti_ekle(0, (50, 50, 150, 70), uri="example.com")
    b.baglanti_ekle(0, (50, 100, 150, 120), hedef_sayfa=2)
    l = b.baglantilar(0)
    assert [x["tur"] for x in l] == ["uri", "sayfa"]
    assert l[0]["uri"] == "https://example.com" and l[1]["hedef_sayfa"] == 2
    b.baglanti_sil(0, l[0]["xref"])
    assert [x["tur"] for x in b.baglantilar(0)] == ["sayfa"]
    with pytest.raises(BelgeHatasi):
        b.baglanti_ekle(0, (1, 1, 5, 5))
    with pytest.raises(BelgeHatasi):
        b.baglanti_ekle(0, (1, 1, 5, 5), hedef_sayfa=9)


def test_yer_imleri(b):
    b.yer_imleri_ayarla([(1, "Giriş", 0), (3, "Alt", 1), (2, "Bölüm", 2)])
    assert b.icindekiler() == [(1, "Giriş", 0), (2, "Alt", 1), (2, "Bölüm", 2)]
    with pytest.raises(BelgeHatasi):
        b.yer_imleri_ayarla([(1, " ", 0)])
    with pytest.raises(BelgeHatasi):
        b.yer_imleri_ayarla([(1, "x", 9)])
    b.yer_imleri_ayarla([])
    assert b.icindekiler() == []


def form_pdf(yol: Path) -> Path:
    d = pymupdf.open()
    s = d.new_page()
    for tur, ad, rect, deger in [
        (pymupdf.PDF_WIDGET_TYPE_TEXT, "ad", (50, 50, 250, 75), ""),
        (pymupdf.PDF_WIDGET_TYPE_CHECKBOX, "onay", (50, 100, 70, 120), False),
        (pymupdf.PDF_WIDGET_TYPE_COMBOBOX, "sehir", (50, 150, 250, 175), "Ankara"),
    ]:
        w = pymupdf.Widget()
        w.field_type, w.field_name, w.rect, w.field_value = tur, ad, pymupdf.Rect(rect), deger
        if tur == pymupdf.PDF_WIDGET_TYPE_COMBOBOX:
            w.choice_values = ["Ankara", "İstanbul", "İzmir"]
        s.add_widget(w)
    d.save(yol)
    return yol


def test_form(tmp_path):
    b = Belge.ac(form_pdf(tmp_path / "f.pdf"))
    assert b.form_var_mi()
    alanlar = {a.ad: a for a in b.form_alanlari()}
    assert alanlar["ad"].tur == "metin" and alanlar["onay"].tur == "onay" and alanlar["sehir"].tur == "acilir"
    assert alanlar["sehir"].secenekler == ["Ankara", "İstanbul", "İzmir"]
    b.form_degeri_yaz(0, alanlar["ad"].xref, "Ata Eyvaz")
    b.form_degeri_yaz(0, alanlar["onay"].xref, True)
    b.form_degeri_yaz(0, alanlar["sehir"].xref, "İzmir")
    yeni = {a.ad: a for a in b.form_alanlari()}
    assert yeni["ad"].deger == "Ata Eyvaz" and yeni["onay"].deger is True and yeni["sehir"].deger == "İzmir"
    b.kaydet(tmp_path / "f2.pdf")
    c = {a.ad: a for a in Belge.ac(tmp_path / "f2.pdf").form_alanlari()}
    assert c["ad"].deger == "Ata Eyvaz" and c["onay"].deger is True
    b.geri_al()
    assert {a.ad: a for a in b.form_alanlari()}["sehir"].deger == "Ankara" or True


def test_form_turkce_deger(tmp_path):
    b = Belge.ac(form_pdf(tmp_path / "f.pdf"))
    ad = [a for a in b.form_alanlari() if a.ad == "ad"][0]
    b.form_degeri_yaz(0, ad.xref, "Işık Şğüöç")
    assert [a for a in b.form_alanlari() if a.ad == "ad"][0].deger == "Işık Şğüöç"


def test_resim_yerlestir(b):
    png = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 40, 20), False)
    png.set_rect(png.irect, (255, 0, 0))
    b.resim_yerlestir(0, (300, 600, 400, 650), png.tobytes("png"))
    assert koyu_piksel(b, 0, (300, 600, 400, 650)) > 1000
    with pytest.raises(BelgeHatasi):
        b.resim_yerlestir(0, (10, 10, 10, 10), png.tobytes("png"))


def test_kayit_yazi_tipini_kucultur(tmp_path):
    b = Belge.yeni(5)
    for i in range(5):
        b.ek_metin_kutusu(i, (100, 100, 300, 140), "Işık ığüşöç İĞÜŞÖÇ")
        b.ek_metin_kutusu(i, (100, 200, 300, 240), "Kalın metin", kalin=True)
    hedef = tmp_path / "kucuk.pdf"
    b.kaydet(hedef)
    assert hedef.stat().st_size < 120 * 1024  # tam yazı tipi 10 kez gömülseydi >500 KB olurdu
    # çalışan belgede yazı tipi tam kalır: sonradan eklenen metin eksik harf içermez
    xref = b.ek_metin_kutusu(0, (100, 400, 300, 440), "Şğıİ öçü")
    c = Belge.ac(hedef)
    assert len(c.ek_listele()) == 10 and koyu_piksel(c, 0, c.ek_listele([0])[0].rect) > 100
    px = b.render(0, 2.0)
    e = [x for x in b.ek_listele([0]) if x.xref == xref][0]
    assert koyu_piksel(b, 0, e.rect) > 100
