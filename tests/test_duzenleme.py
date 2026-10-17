import math
from pathlib import Path

import pymupdf
import pytest

from eaglepdf.core.belge import Belge, BelgeHatasi
from eaglepdf.core.duzenleme import bilgi_metni, sayfa_numarasi_metni
from test_belge import ARIAL, pdf_yap
from test_ekaciklama import koyu_piksel

DONUSLER = (0, 90, 180, 270)


def asimetrik_belge(tmp_path: Path, donus: int = 0, sayfa: int = 1, ad: str = "") -> Belge:
    """600×800 sayfa: sol üstte siyah dikdörtgen (40,60)-(120,120), (200,300)'de metin."""
    d = pymupdf.open()
    for _ in range(sayfa):
        p = d.new_page(width=600, height=800)
        p.draw_rect(pymupdf.Rect(40, 60, 120, 120), color=None, fill=(0, 0, 0))
        p.insert_text((200, 300), "MERKEZ METIN", fontname="helv", fontsize=20)
        p.set_rotation(donus)
    yol = tmp_path / f"asim{donus}{ad}.pdf"
    d.save(yol)
    return Belge.ac(yol)


def piksel_matrisi(b: Belge, sayfa: int, adim: int = 8):
    px = b.render(sayfa, 1.0)
    return px.width, px.height, {(x, y): px.pixel(x, y) for x in range(0, px.width, adim) for y in range(0, px.height, adim)}


def yon_acisi(p: pymupdf.Page, parca: str) -> float:
    """Aranan metnin GÖRÜNEN uzaydaki okuma yönü (derece, ters saat yönü = pozitif)."""
    for blok in p.get_text("dict")["blocks"]:
        for satir in blok.get("lines", []):
            if parca in "".join(s["text"] for s in satir["spans"]):
                dx, dy = satir["dir"]
                rm = p.rotation_matrix
                vx, vy = dx * rm.a + dy * rm.c, dx * rm.b + dy * rm.d
                return math.degrees(math.atan2(-vy, vx))
    raise AssertionError(f"Metin bulunamadı: {parca}")


def gorunen_merkez(p: pymupdf.Page, parca: str):
    for blok in p.get_text("dict")["blocks"]:
        for satir in blok.get("lines", []):
            if parca in "".join(s["text"] for s in satir["spans"]):
                r = pymupdf.Rect(satir["bbox"]) * p.rotation_matrix
                return (r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2
    raise AssertionError(f"Metin bulunamadı: {parca}")


@pytest.mark.parametrize("donus", DONUSLER)
def test_kirp_gorunen_alani_dogru_keser(tmp_path, donus):
    b = asimetrik_belge(tmp_path, donus)
    g0, y0, once = piksel_matrisi(b, 0)
    sol, ust, sag, alt = 48, 32, 16, 8
    b.kirp([0], sol, ust, sag, alt)
    g1, y1, sonra = piksel_matrisi(b, 0, adim=8)
    assert (g1, y1) == (g0 - sol - sag, y0 - ust - alt)
    # kırpılmış görüntü, orijinalin ilgili parçasıyla birebir aynı olmalı
    px0, px1 = b.render(0, 1.0), None
    b.geri_al()
    orijinal = b.render(0, 1.0)
    b.yinele()
    kirpik = b.render(0, 1.0)
    for x in range(0, kirpik.width, 10):
        for y in range(0, kirpik.height, 10):
            assert kirpik.pixel(x, y) == orijinal.pixel(x + sol, y + ust), (donus, x, y)


def test_kirp_ikinci_kez_ve_kaldir(tmp_path):
    b = asimetrik_belge(tmp_path, 90)
    b.kirp([0], 40, 40, 40, 40)
    b.kirp([0], 10, 20, 30, 0)
    assert b._doc[0].rect.width == 800 - 80 - 40 and b._doc[0].rect.height == 600 - 80 - 20
    b.kirpmayi_kaldir([0])
    assert (b._doc[0].rect.width, b._doc[0].rect.height) == (800, 600)
    with pytest.raises(BelgeHatasi):
        b.kirp([0], 400, 0, 400, 0)
    with pytest.raises(BelgeHatasi):
        b.kirp([0], -1, 0, 0, 0)
    with pytest.raises(BelgeHatasi):
        b.kirp([], 1, 1, 1, 1)


def test_otomatik_kirp(tmp_path):
    b = asimetrik_belge(tmp_path)
    s = b.icerik_sinirlari(0)
    assert s and s[0] <= 41 and s[1] <= 61 and s[2] > 300
    b.otomatik_kirp([0], pay=10)
    r = b._doc[0].rect
    assert r.width < 600 and r.height < 800 and r.width > 250
    bos = Belge.yeni(1)
    assert bos.icerik_sinirlari(0) is None
    bos.otomatik_kirp([0])  # boş sayfa atlanır, hata vermez
    assert bos._doc[0].rect.width == 595


@pytest.mark.parametrize("donus", (0, 90))
def test_sayfa_boyutu_degistir(tmp_path, donus):
    b = asimetrik_belge(tmp_path, donus)
    b.ek_sekil(0, "dikdortgen", (300, 400), (400, 460))
    gen0, yuk0 = b.sayfa_boyutu(0)
    b.sayfa_boyutu_degistir([0], 300, 300)
    assert b.sayfa_boyutu(0) == (300, 300)
    assert b.ek_listele() == []  # ek açıklama sayfaya işlendi
    olcek = min(300 / gen0, 300 / yuk0)
    # siyah dikdörtgenin (görünen uzayda) ölçeklenmiş merkezi hâlâ siyah
    if donus == 0:
        mx, my = 80 * olcek + (300 - gen0 * olcek) / 2, 90 * olcek + (300 - yuk0 * olcek) / 2
        assert b.render(0, 1.0).pixel(int(mx), int(my)) == (0, 0, 0)
    assert b.ara("MERKEZ") and b.geri_al() and b.sayfa_boyutu(0) == (gen0, yuk0)
    with pytest.raises(BelgeHatasi):
        b.sayfa_boyutu_degistir([0], 5, 300)


@pytest.mark.parametrize("donus", DONUSLER)
def test_filigran_metin_egimi_ve_merkezi(tmp_path, donus):
    b = asimetrik_belge(tmp_path, donus)
    p = b._doc[0]
    b.filigran_metin([0], "TASLAK ŞĞİ", boyut=60, aci=45, opaklik=0.3)
    p = b._doc[0]
    assert abs(yon_acisi(p, "TASLAK") - 45) < 1.5, donus
    cx, cy = gorunen_merkez(p, "TASLAK")
    r = p.rect
    assert abs(cx - r.width / 2) < 4 and abs(cy - r.height / 2) < 4
    with pytest.raises(BelgeHatasi):
        b.filigran_metin([0], "  ")
    with pytest.raises(BelgeHatasi):
        b.filigran_metin([0], "x", opaklik=0)


def test_filigran_saydam_ve_resim(tmp_path):
    b = Belge.yeni(1)
    b.filigran_metin([0], "GİZLİ", boyut=80, renk="#ff0000", aci=0, opaklik=0.25)
    px = b.render(0, 1.0)
    en_koyu = min(px.pixel(x, y) for x in range(100, 500, 3) for y in range(380, 450, 3))
    assert en_koyu[0] == 255 and 120 < en_koyu[1] < 230  # saydam kırmızı: pembe
    png = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 50, 20), False)
    png.set_rect(png.irect, (0, 0, 255))
    for donus in DONUSLER:
        c = Belge.yeni(1)
        c._doc[0].set_rotation(donus)
        c.filigran_resim([0], png.tobytes("png"), 0.5)
        r = c._doc[0].rect
        assert c.render(0, 1.0).pixel(int(r.width / 2), int(r.height / 2)) == (0, 0, 255), donus
    with pytest.raises(BelgeHatasi):
        c.filigran_resim([0], png.tobytes("png"), 0)


@pytest.mark.parametrize("donus", DONUSLER)
def test_arka_plan(tmp_path, donus):
    b = asimetrik_belge(tmp_path, donus)
    b.arka_plan([0], renk="#ffeb3b")
    px = b.render(0, 1.0)
    assert px.pixel(2, 2) == (255, 235, 59) and px.pixel(px.width - 3, px.height - 3) == (255, 235, 59)
    # içerik arka planın üstünde kalır
    assert b.ara("MERKEZ")
    # resim: sol yarı kırmızı, sağ yarı mavi → görünen uzayda da sol kırmızı
    img = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 40, 20), False)
    img.set_rect(pymupdf.IRect(0, 0, 20, 20), (255, 0, 0))
    img.set_rect(pymupdf.IRect(20, 0, 40, 20), (0, 0, 255))
    c = asimetrik_belge(tmp_path, donus, ad="b")
    c.arka_plan([0], png=img.tobytes("png"))
    px = c.render(0, 1.0)
    assert px.pixel(px.width - 5, 5) == (0, 0, 255) and px.pixel(px.width - 5, px.height - 5) == (0, 0, 255)
    assert px.pixel(5, px.height - 5) == (255, 0, 0) and px.pixel(5, 5) != (0, 0, 255)
    with pytest.raises(BelgeHatasi):
        c.arka_plan([0])


def test_yer_tutucular():
    assert sayfa_numarasi_metni("Sayfa {n} / {toplam}", 3, 9) == "Sayfa 3 / 9"
    import datetime
    assert bilgi_metni("{dosya} — {sayfa}/{toplam} — {tarih}", 2, 5, "a.pdf", datetime.date(2026, 10, 16)) == \
        "a.pdf — 2/5 — 16.10.2026"


@pytest.mark.parametrize("donus", DONUSLER)
def test_ustalt_bilgi_dik_okunur(tmp_path, donus):
    b = asimetrik_belge(tmp_path, donus, sayfa=3)
    b.ustalt_bilgi([0, 1, 2], ust=("Rapor", "", "{sayfa}/{toplam}"), alt=("", "{tarih}", ""), boyut=12, kenar=40)
    p = b._doc[1]
    assert abs(yon_acisi(p, "Rapor")) < 1.0, donus
    assert "2/3" in p.get_text() and "Rapor" in p.get_text()
    cx, cy = gorunen_merkez(p, "Rapor")
    r = p.rect
    assert cx < r.width / 3 and cy < 60           # sol üst
    cx2, cy2 = gorunen_merkez(p, "2/3")
    assert cx2 > r.width * 2 / 3 and cy2 < 60     # sağ üst
    import datetime
    cx3, cy3 = gorunen_merkez(p, datetime.date.today().strftime("%d.%m.%Y"))
    assert abs(cx3 - r.width / 2) < 5 and cy3 > r.height - 60  # alt orta
    with pytest.raises(BelgeHatasi):
        b.ustalt_bilgi([0])


@pytest.mark.parametrize("donus", DONUSLER)
def test_sayfa_numarasi(tmp_path, donus):
    b = asimetrik_belge(tmp_path, donus, sayfa=3)
    b.sayfa_numarasi_ekle([0, 1, 2], "alt-sag", "Sayfa {n} / {toplam}", baslangic=5)
    p = b._doc[2]
    assert "Sayfa 7 / 7" in p.get_text() and "Sayfa 5 / 7" in b._doc[0].get_text()
    assert abs(yon_acisi(p, "Sayfa 7")) < 1.0
    cx, cy = gorunen_merkez(p, "Sayfa 7")
    r = p.rect
    assert cx > r.width / 2 and cy > r.height - 60
    for kotu in (("orta-orta", "{n}"), ("alt-orta", "sabit")):
        with pytest.raises(BelgeHatasi):
            b.sayfa_numarasi_ekle([0], kotu[0], kotu[1])


def test_kalici_sil(tmp_path):
    b = Belge.ac(pdf_yap(tmp_path / "s.pdf", 3, "GIZLI TC 12345"))
    assert b.ara("12345")
    r = b.ara("12345")[0][1]
    b.kalici_sil(0, [r])
    assert "12345" not in b._doc[0].get_text() and "12345" in b._doc[1].get_text()
    assert b.render(0, 1.0).pixel(int((r[0] + r[2]) / 2), int((r[1] + r[3]) / 2)) == (0, 0, 0)  # dolgu
    hedef = tmp_path / "temiz.pdf"
    b.kaydet(hedef)
    ham = hedef.read_bytes()
    assert "12345" not in Belge.ac(hedef)._doc[0].get_text()
    n = b.kalici_sil_metin("GIZLI", dolgu=None)
    assert n == 3 and b.ara("GIZLI") == []
    with pytest.raises(BelgeHatasi):
        b.kalici_sil_metin("yokyokyok")
    with pytest.raises(BelgeHatasi):
        b.kalici_sil(0, [])
    assert b.geri_al() and b.ara("GIZLI")


def test_kalici_sil_resim_pikselleri(tmp_path):
    d = pymupdf.open()
    p = d.new_page()
    img = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 100, 100), False)
    img.set_rect(img.irect, (0, 200, 0))
    p.insert_image(pymupdf.Rect(100, 100, 300, 300), pixmap=img)
    d.save(tmp_path / "r.pdf")
    b = Belge.ac(tmp_path / "r.pdf")
    assert b.render(0, 1.0).pixel(150, 150) == (0, 200, 0)
    b.kalici_sil(0, [(120, 120, 180, 180)], dolgu="#000000")
    px = b.render(0, 1.0)
    assert px.pixel(150, 150) == (0, 0, 0) and px.pixel(250, 250) == (0, 200, 0)


def test_duzlestir(tmp_path):
    from test_ekaciklama import form_pdf
    b = Belge.ac(form_pdf(tmp_path / "f.pdf"))
    ad = [a for a in b.form_alanlari() if a.ad == "ad"][0]
    b.form_degeri_yaz(0, ad.xref, "Ata")
    b.ek_sekil(0, "dikdortgen", (300, 300), (400, 360))
    b.duzlestir(ek_aciklamalar=True, form_alanlari=False)
    assert b.ek_listele() == [] and len(b.form_alanlari()) == 3
    b.duzlestir(ek_aciklamalar=False, form_alanlari=True)
    assert b.form_alanlari() == [] and not b.form_var_mi() or b.form_alanlari() == []
    assert koyu_piksel(b, 0, (300, 300, 400, 360)) > 100  # çizim sayfaya işlendi
    with pytest.raises(BelgeHatasi):
        b.duzlestir(False, False)


def saydam_png() -> bytes:
    """100×40 kırmızı resim; yalnızca ortadaki 20×20 kare opak, gerisi tamamen saydam."""
    rgb = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 100, 40), False)
    rgb.set_rect(rgb.irect, (220, 0, 0))
    alfa = bytearray(100 * 40)
    for y in range(10, 30):
        for x in range(40, 60):
            alfa[y * 100 + x] = 255
    pix = pymupdf.Pixmap(rgb, 1)
    pix.set_alpha(bytes(alfa), premultiply=0)
    return pix.tobytes("png")


def test_muhur_resim_tasi_boyutlandir(tmp_path):
    b = Belge.ac(pdf_yap(tmp_path / "m.pdf", 1))
    xref = b.muhur_ekle(0, (100, 100, 300, 180), saydam_png(), "Ata", "ONAY")
    e = b.ek_listele()[0]
    assert e.etiket == "Mühür / Resim" and e.xref == xref and e.metin == "ONAY"
    px = b.render(0, 1.0)
    assert px.pixel(200, 140) == (220, 0, 0)          # opak kare
    assert px.pixel(110, 110) == (255, 255, 255)      # saydam bölge: sayfa görünür
    once = b.ek_listele()[0].rect
    b.ek_tasi(0, xref, 50, 40)
    yeni = b.ek_listele()[0].rect
    assert abs(yeni[0] - once[0] - 50) < 2 and abs(yeni[1] - once[1] - 40) < 2
    b.ek_boyutlandir(0, xref, (100, 100, 400, 280))
    assert abs(b.ek_listele()[0].rect[2] - 400) < 2
    with pytest.raises(BelgeHatasi):
        b.ek_boyutlandir(0, xref, (10, 10, 12, 12))
    with pytest.raises(BelgeHatasi):
        b.muhur_ekle(0, (10, 10, 12, 12), saydam_png())
    with pytest.raises(BelgeHatasi):
        b.muhur_ekle(0, (10, 10, 100, 100), b"png degil")
    nota = b.ek_cizim(0, [[(1, 1), (30, 30)]])
    with pytest.raises(BelgeHatasi):
        b.ek_boyutlandir(0, nota, (1, 1, 50, 50))
    b.kaydet(tmp_path / "m2.pdf")
    assert Belge.ac(tmp_path / "m2.pdf").ek_listele()[0].etiket == "Mühür / Resim"


def test_metin_blogu_ve_degistir(tmp_path):
    if not ARIAL.exists():
        pytest.skip("Arial yok")
    b = Belge.ac(pdf_yap(tmp_path / "t.pdf", 1, "Merhaba dunya"))
    blok = b.metin_blogu(0, (80, 95))
    assert blok and blok["metin"] == "Merhaba dunya 1" and 10 < blok["boyut"] < 14 and not blok["kalin"]
    assert b.metin_blogu(0, (400, 700)) is None
    b.metin_degistir(0, blok["rect"], "Güncel ışık metni", blok["boyut"], blok["renk"])
    metin = b._doc[0].get_text()
    assert "Merhaba" not in metin and "Güncel ışık metni" in metin
    b.metin_degistir(0, blok["rect"], "çok uzun bir metin " * 8, 12)  # sığmazsa küçülür/uzar
    assert "çok uzun" in b._doc[0].get_text()
    with pytest.raises(BelgeHatasi):
        b.metin_degistir(0, blok["rect"], "  ", 12)
    b.sayfa_dondur([0], 90)
    with pytest.raises(BelgeHatasi):
        b.metin_degistir(0, blok["rect"], "x", 12)
    b.geri_al()
    b.geri_al()
    b.geri_al()
    assert "Merhaba" in b._doc[0].get_text()


def test_islemler_kaydet_ac_gidis_donus(tmp_path):
    b = asimetrik_belge(tmp_path, 0, sayfa=2)
    b.kirp([0], 20, 20, 20, 20)
    b.filigran_metin([0, 1], "TASLAK", aci=30)
    b.sayfa_numarasi_ekle([0, 1], "alt-orta", "{n}")
    b.arka_plan([1], renk="#e3f2fd")
    hedef = tmp_path / "son.pdf"
    b.kaydet(hedef)
    c = Belge.ac(hedef)
    assert c.sayfa_boyutu(0) == (560, 760) and c.sayfa_boyutu(1) == (600, 800)
    assert "TASLAK" in c._doc[0].get_text() and c.render(1, 1.0).pixel(3, 3) == (227, 242, 253)


def sayfa_goruntusu(b: Belge, i: int):
    px = b.render(i, 1.0)
    return px.width, px.height, [px.pixel(x, y) for x in range(0, px.width, 7) for y in range(0, px.height, 7)]


@pytest.mark.parametrize("donus", DONUSLER)
def test_filigran_kaldir_eski_gorunume_doner(tmp_path, donus):
    b = asimetrik_belge(tmp_path, donus, sayfa=3)
    once = sayfa_goruntusu(b, 1)
    assert b.filigran_sayfalari() == []
    b.filigran_metin([0, 1, 2], "TASLAK", 70, "#c62828", 45, 0.3)
    png = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 60, 30), False)
    png.set_rect(png.irect, (0, 0, 255))
    b.filigran_resim([1], png.tobytes("png"), 0.4)
    assert b.filigran_sayfalari() == [0, 1, 2] and "TASLAK" in b._doc[1].get_text()
    assert sayfa_goruntusu(b, 1) != once
    n = b.filigranlari_kaldir([1])
    assert n == 2 and b.filigran_sayfalari() == [0, 2]
    assert "TASLAK" not in b._doc[1].get_text() and "MERKEZ METIN" in b._doc[1].get_text()
    assert sayfa_goruntusu(b, 1) == once          # piksel piksel eski görünüm
    assert "TASLAK" in b._doc[0].get_text()       # öteki sayfalara dokunulmadı
    with pytest.raises(BelgeHatasi):
        b.filigranlari_kaldir([1])                # artık yok
    assert b.filigranlari_kaldir([0, 1, 2]) == 2 and b.filigran_sayfalari() == []


def test_filigran_kaydet_ac_sonra_kaldir_ve_geri_al(tmp_path):
    b = asimetrik_belge(tmp_path, 0, sayfa=2)
    once = sayfa_goruntusu(b, 0)
    with pytest.raises(BelgeHatasi):
        b.filigranlari_kaldir([0])                # hiç filigran eklenmemiş belge
    b.filigran_metin([0, 1], "GİZLİ", 80, aci=30)
    b.filigran_metin([0], "KOPYA", 40, aci=0)     # aynı sayfada iki filigran
    hedef = tmp_path / "f.pdf"
    b.kaydet(hedef)
    c = Belge.ac(hedef)
    assert c.filigran_sayfalari() == [0, 1]
    assert c.filigranlari_kaldir([0, 1]) == 3
    assert sayfa_goruntusu(c, 0) == once
    assert c.geri_al() and c.filigran_sayfalari() == [0, 1]
    c.kaydet(tmp_path / "g.pdf")
    assert Belge.ac(tmp_path / "g.pdf").filigran_sayfalari() == [0, 1]


@pytest.mark.parametrize("donus", DONUSLER)
def test_ustalt_ve_sayfa_numarasi_kaldir_eski_gorunume_doner(tmp_path, donus):
    b = asimetrik_belge(tmp_path, donus, sayfa=3)
    once = [sayfa_goruntusu(b, i) for i in range(3)]
    assert b.ustalt_sayfalari() == [] and b.sayfa_numarasi_sayfalari() == []
    b.ustalt_bilgi([0, 1, 2], ust=("Rapor", "", "{sayfa}/{toplam}"), alt=("", "{dosya}", ""))
    b.sayfa_numarasi_ekle([1, 2], "alt-sag", "Sayfa {n}")
    assert b.ustalt_sayfalari() == [0, 1, 2] and b.sayfa_numarasi_sayfalari() == [1, 2]
    # ikisi ayrı katmanda: biri kalkınca öteki yerinde kalır
    assert b.ustalt_kaldir([1]) == 3                       # sol-üst, sağ-üst, orta-alt
    assert b.ustalt_sayfalari() == [0, 2] and b.sayfa_numarasi_sayfalari() == [1, 2]
    assert "Rapor" not in b._doc[1].get_text() and "Sayfa 1" in b._doc[1].get_text()
    assert b.sayfa_numarasi_kaldir([1, 2]) == 2
    assert sayfa_goruntusu(b, 1) == once[1]                # piksel piksel eski görünüm
    assert "Rapor" in b._doc[0].get_text()                 # öteki sayfaya dokunulmadı
    with pytest.raises(BelgeHatasi):
        b.sayfa_numarasi_kaldir([1])                       # artık yok
    b.ustalt_kaldir([0, 2])
    assert sayfa_goruntusu(b, 0) == once[0] and b.ustalt_sayfalari() == []
    assert b.geri_al() and b.ustalt_sayfalari() == [0, 2]


def test_ustalt_kaldir_kayittan_sonra_ve_filigrana_dokunmaz(tmp_path):
    b = asimetrik_belge(tmp_path, 0, sayfa=2)
    b.filigran_metin([0, 1], "GİZLİ", 80, aci=30)
    b.ustalt_bilgi([0, 1], ust=("Başlık", "", ""))
    b.sayfa_numarasi_ekle([0, 1], "alt-orta", "{n}")
    b.kaydet(tmp_path / "u.pdf")
    c = Belge.ac(tmp_path / "u.pdf")
    assert c.ustalt_kaldir([0, 1]) == 2 and c.sayfa_numarasi_kaldir([0, 1]) == 2
    assert c.filigran_sayfalari() == [0, 1] and "GİZLİ" in c._doc[0].get_text()
    with pytest.raises(BelgeHatasi):
        asimetrik_belge(tmp_path, 0, ad="bos").ustalt_kaldir([0])    # hiç eklenmemiş belge


def _yazi_tipli_belge(tmp_path, ad: str, dosya: str, gom: bool, metin: str = "Merhaba dunya", stil=None):
    """Verilen Windows yazı tipiyle yazılmış tek sayfalık belge (gom=True: PDF'e gömülür)."""
    yol_font = Path(r"C:\Windows\Fonts") / dosya
    if not yol_font.exists():
        pytest.skip(f"{dosya} yok")
    d = pymupdf.open()
    p = d.new_page()
    p.insert_font(fontname="F1", fontfile=str(yol_font))
    p.insert_text((72, 100), metin, fontname="F1", fontsize=14)
    yol = tmp_path / f"{ad}.pdf"
    d.save(yol)
    d.close()
    return Belge.ac(yol)


def _sayfadaki_yazi_tipleri(b: Belge) -> list[str]:
    return [t[3].split("+", 1)[-1] for t in b._doc[0].get_fonts(full=True)]


def test_metin_degistir_belgedeki_yazi_tipini_korur(tmp_path):
    b = _yazi_tipli_belge(tmp_path, "cal", "calibri.ttf", True)
    blok = b.metin_blogu(0, (80, 95))
    assert blok and "calibri" in blok["yazi_tipi"].lower()
    kullanilan = b.metin_degistir(0, blok["rect"], "Merhaba", blok["boyut"], blok["renk"], blok["kalin"], blok["italik"], orijinal=blok)
    assert "Calibri" in kullanilan and "belgedeki" in kullanilan
    assert "Merhaba" in b._doc[0].get_text()
    # yeni yazılan metin de Calibri ile yazılmış (Noto kullanılmadı)
    assert not any("Noto" in f for f in _sayfadaki_yazi_tipleri(b))


def test_metin_degistir_gomulu_yazi_tipinde_olmayan_harf_icin_ayni_aile_sistem_dosyasi(tmp_path):
    """Belgede alt küme yok (tam gömülü) ya da harf eksik olsa da aynı ailenin Windows dosyası / yedek devreye girer; metin doğru çıkar."""
    b = _yazi_tipli_belge(tmp_path, "ar", "arial.ttf", True)
    blok = b.metin_blogu(0, (80, 95))
    kullanilan = b.metin_degistir(0, blok["rect"], "Güncel ışık şğüöç", blok["boyut"], blok["renk"], orijinal=blok)
    assert "Arial" in kullanilan
    assert "Güncel ışık şğüöç" in b._doc[0].get_text().replace(" ", " ")


def test_metin_degistir_bilinmeyen_yazi_tipi_ve_stil_degisince_yedek_noto(tmp_path):
    b = _yazi_tipli_belge(tmp_path, "cal2", "calibri.ttf", True)
    blok = b.metin_blogu(0, (80, 95))
    # orijinal verilmedi (eski davranış)
    assert b.metin_degistir(0, blok["rect"], "Yeni metin", blok["boyut"], blok["renk"]).startswith("Noto Sans")
    # yazı tipi adı tanınmayan aile: yedek
    sahte = {**blok, "yazi_tipi": "XYZ+BilinmeyenYaziTipi"}
    assert b.metin_degistir(0, blok["rect"], "Bir daha", blok["boyut"], blok["renk"], orijinal=sahte).startswith("Noto Sans")
    # kullanıcı kalın yaptı: belgedeki normal yazı tipi yerine ailenin kalın Windows dosyası
    kullanilan = b.metin_degistir(0, blok["rect"], "Kalın", blok["boyut"], blok["renk"], kalin=True, orijinal=blok)
    assert "Calibri" in kullanilan and "Windows" in kullanilan


def test_yazi_tipi_anahtari():
    from eaglepdf.core.duzenleme import DuzenlemeIslemleri as D
    assert D._yazi_tipi_anahtari("ABCDEF+Calibri-BoldItalic") == "calibri"
    assert D._yazi_tipi_anahtari("TimesNewRomanPS-BoldMT") == "timesnewroman"
    assert D._yazi_tipi_anahtari("Arial-ItalicMT") == "arial"
    assert D._yazi_tipi_anahtari("Helvetica-Bold") == "arial"
    assert D._yazi_tipi_anahtari("CourierNewPSMT") == "couriernew"
