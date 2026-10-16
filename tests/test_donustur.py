import io
import random
from pathlib import Path

import pymupdf
import pytest

from eaglepdf.core import donustur
from eaglepdf.core.belge import Belge, BelgeHatasi, ParolaGerekli
from test_belge import ARIAL, pdf_yap

pytestmark = pytest.mark.skipif(not ARIAL.exists(), reason="Arial yazı tipi yok")
ARIALB = Path("C:/Windows/Fonts/arialbd.ttf")


def ornek_pdf(yol: Path, sayfa: int = 2) -> Path:
    """Başlık, Türkçe paragraf ve çizgili tablo içeren örnek PDF."""
    d = pymupdf.open()
    for n in range(sayfa):
        p = d.new_page()
        p.insert_text((72, 90), f"Aylık Satış Raporu — İstanbul {n + 1}", fontname="arialb", fontfile=str(ARIALB), fontsize=20)
        p.insert_textbox(pymupdf.Rect(72, 110, 520, 200), "Işık Şirketi'nin ğüşiöç karakterleri içeren bu paragraf, "
                         "dönüştürme sonrasında doğru çıkmalıdır.", fontname="arial", fontfile=str(ARIAL), fontsize=12)
        x0, y0, w, h = 72, 230, 110, 28
        for r, satir in enumerate([("Ürün", "Adet", "Tutar"), ("Çay", "12", "1.240,50"), ("Şeker", "7", "88,00"), ("Kod", "007", "x")]):
            for c, hucre in enumerate(satir):
                rect = pymupdf.Rect(x0 + c * w, y0 + r * h, x0 + (c + 1) * w, y0 + (r + 1) * h)
                p.draw_rect(rect, color=(0, 0, 0), width=0.8)
                p.insert_text((rect.x0 + 6, rect.y0 + 18), hucre, fontname="arial", fontfile=str(ARIAL), fontsize=11)
    d.save(yol)
    return yol


def taranmis_pdf(yol: Path) -> Path:
    """Yalnızca resimden oluşan (metin katmanı olmayan) PDF."""
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 200, 100), False)
    pix.set_rect(pix.irect, (200, 200, 200))
    d = pymupdf.open()
    d.new_page().insert_image(pymupdf.Rect(50, 50, 400, 250), pixmap=pix)
    d.save(yol)
    return yol


@pytest.fixture
def pdf(tmp_path):
    return ornek_pdf(tmp_path / "ornek.pdf")


# --- PDF → resim ---
def test_pdf_resim_bicimler_ve_boyut(pdf, tmp_path):
    cikti = tmp_path / "r"
    dosyalar = donustur.pdf_resim(pdf, cikti, "png", dpi=72)
    assert [d.name for d in dosyalar] == ["ornek_sayfa_001.png", "ornek_sayfa_002.png"]
    from PIL import Image
    with Image.open(dosyalar[0]) as im:
        assert im.size == (595, 842) and im.mode == "RGB"
    jpg = donustur.pdf_resim(pdf, cikti, "jpg", dpi=144, sayfalar=[1])
    with Image.open(jpg[0]) as im:
        assert jpg[0].name == "ornek_sayfa_002.jpg" and im.size == (1190, 1684) and im.format == "JPEG"
    for bicim in ("bmp", "tiff"):
        assert donustur.pdf_resim(pdf, cikti, bicim, dpi=36, sayfalar=[0])[0].suffix == f".{bicim}"
    # aynı adlar ezilmez
    yeniden = donustur.pdf_resim(pdf, cikti, "png", dpi=72)
    assert yeniden[0].name == "ornek_sayfa_001 (2).png" and dosyalar[0].exists()
    assert not list(cikti.glob("*.tmp"))


def test_pdf_resim_renk_modlari_ve_tek_resim(pdf, tmp_path):
    from PIL import Image
    gri = donustur.pdf_resim(pdf, tmp_path / "g", "png", 72, renk="gri", sayfalar=[0])[0]
    with Image.open(gri) as im:
        assert im.mode == "L"
    sb = donustur.pdf_resim(pdf, tmp_path / "s", "png", 72, renk="siyahbeyaz", sayfalar=[0])[0]
    with Image.open(sb) as im:
        assert set(im.tobytes()) <= {0, 255} and 0 in set(im.tobytes())
    tek = donustur.pdf_resim(pdf, tmp_path / "t", "png", 72, tek_resim=True)
    assert len(tek) == 1
    with Image.open(tek[0]) as im:
        assert im.size == (595, 842 * 2)


def test_pdf_resim_hatalar_ve_iptal(pdf, tmp_path):
    for kotu in (dict(bicim="gif"), dict(renk="mor"), dict(dpi=10), dict(dpi=9999), dict(sayfalar=[5])):
        with pytest.raises(BelgeHatasi):
            donustur.pdf_resim(pdf, tmp_path / "x", **{"bicim": "png", **kotu})
    cagrilar = []
    with pytest.raises(donustur.Iptal):
        donustur.pdf_resim(pdf, tmp_path / "x", "png", 72, ilerleme=lambda n, t: cagrilar.append((n, t)) or n >= 1)
    assert cagrilar[0] == (0, 2)
    d = pymupdf.open()
    d.new_page(width=14000, height=14000)
    d.save(tmp_path / "dev.pdf")
    with pytest.raises(BelgeHatasi):
        donustur.pdf_resim(tmp_path / "dev.pdf", tmp_path / "x", "png", 600)


def test_parolali_pdf(tmp_path):
    y = pdf_yap(tmp_path / "p.pdf", 1, "Gizli metin", parola="abc")
    with pytest.raises(ParolaGerekli):
        donustur.pdf_metin(y, tmp_path / "o")
    assert "Gizli" in donustur.pdf_metin(y, tmp_path / "o", parola="abc").read_text(encoding="utf-8-sig")


# --- PDF → metin / HTML ---
def test_pdf_metin_ve_html(pdf, tmp_path):
    t = donustur.pdf_metin(pdf, tmp_path / "m")
    icerik = t.read_text(encoding="utf-8-sig")
    assert "— Sayfa 1 —" in icerik and "— Sayfa 2 —" in icerik and "Işık Şirketi'nin ğüşiöç" in icerik
    assert "İstanbul 2" in icerik
    tek = donustur.pdf_metin(pdf, tmp_path / "m2", sayfalar=[1], sayfa_ayraci=False).read_text(encoding="utf-8-sig")
    assert "Sayfa 1" not in tek and "İstanbul 2" in tek and "İstanbul 1" not in tek
    h = donustur.pdf_html(pdf, tmp_path / "h", sayfalar=[0])
    veri = h.read_text(encoding="utf-8")
    assert 'charset="utf-8"' in veri and 'id="sayfa-1"' in veri and "Işık" in veri and "sayfa-2" not in veri
    tar = taranmis_pdf(tmp_path / "tara.pdf")
    for fn in (donustur.pdf_metin, donustur.pdf_html, donustur.pdf_word, donustur.pdf_excel):
        with pytest.raises(BelgeHatasi, match="OCR"):
            fn(tar, tmp_path / "x")


# --- PDF → Word ---
def test_pdf_word(pdf, tmp_path):
    import docx
    dosya = donustur.pdf_word(pdf, tmp_path / "w")
    assert dosya.suffix == ".docx" and not list((tmp_path / "w").glob("*.tmp"))
    d = docx.Document(str(dosya))
    metin = "\n".join(p.text for p in d.paragraphs)
    assert "Aylık Satış Raporu — İstanbul 1" in metin and "ğüşiöç" in metin and "İstanbul 2" in metin
    assert len(d.tables) >= 2
    hucreler = [c.text for r in d.tables[0].rows for c in r.cells]
    assert "Ürün" in hucreler and "1.240,50" in hucreler
    tek = donustur.pdf_word(pdf, tmp_path / "w2", sayfalar=[1])
    assert "İstanbul 1" not in "\n".join(p.text for p in docx.Document(str(tek)).paragraphs)


# --- PDF → Excel ---
def test_pdf_excel_tablolar_ve_sayilar(pdf, tmp_path):
    import openpyxl
    dosya, adet = donustur.pdf_excel(pdf, tmp_path / "x")
    assert adet == 2
    wb = openpyxl.load_workbook(str(dosya))
    assert wb.sheetnames == ["S1-T1", "S2-T1"]
    ws = wb["S1-T1"]
    assert [c.value for c in ws[1]] == ["Ürün", "Adet", "Tutar"]
    assert ws["B2"].value == 12 and ws["C2"].value == 1240.5 and ws["C3"].value == 88 and ws["B4"].value == "007"
    ham, _ = donustur.pdf_excel(pdf, tmp_path / "x2", sayi_algila=False)
    assert openpyxl.load_workbook(str(ham))["S1-T1"]["C2"].value == "1.240,50"


def test_pdf_excel_tablosuz_metin(tmp_path):
    import openpyxl
    y = pdf_yap(tmp_path / "t.pdf", 2, "Satır metni")
    dosya, adet = donustur.pdf_excel(y, tmp_path / "x")
    assert adet == 0
    ws = openpyxl.load_workbook(str(dosya))["Metin"]
    assert [r[0].value for r in ws.iter_rows()] == ["Satır metni 1", "Satır metni 2"]


def test_sayi_cozumle():
    cz = donustur.sayi_cozumle
    assert cz("1.234,50") == 1234.5 and cz("240,50") == 240.5 and cz("12") == 12 and cz("-7") == -7
    assert cz("0") == 0 and cz("007") == "007" and cz("00,5") == "00,5" and cz("12/05") == "12/05"
    assert cz("  ") is None and cz("Çay") == "Çay" and cz("1.5") == "1.5" and cz("99999999999999999999") == "99999999999999999999"


# --- PDF → PowerPoint ---
@pytest.mark.parametrize("mod", ("duzenlenebilir", "resim"))
def test_pdf_pptx(pdf, tmp_path, mod):
    from pptx import Presentation
    from pptx.util import Emu
    dosya = donustur.pdf_pptx(pdf, tmp_path / "p", mod=mod, dpi=72)
    prs = Presentation(str(dosya))
    assert len(prs.slides) == 2 and prs.slide_width == Emu(595 * 12700) and prs.slide_height == Emu(842 * 12700)
    s = prs.slides[0]
    turler = [sh.shape_type for sh in s.shapes]
    kutular = [sh for sh in s.shapes if sh.has_text_frame and sh.text_frame.text.strip()]
    resimler = [sh for sh in s.shapes if sh.shape_type == 13]
    assert len(resimler) == 1
    if mod == "duzenlenebilir":
        metin = "\n".join(k.text_frame.text for k in kutular)
        assert "Aylık Satış Raporu — İstanbul 1" in metin and "ğüşiöç" in metin
        baslik = [k for k in kutular if "Aylık" in k.text_frame.text][0]
        assert abs(baslik.left / 12700 - 72) < 3 and baslik.text_frame.paragraphs[0].runs[0].font.bold
        assert abs(baslik.text_frame.paragraphs[0].runs[0].font.size.pt - 20) < 0.6
    else:
        assert not kutular
    assert "Işık Şirketi" in s.notes_slide.notes_text_frame.text


def test_pdf_pptx_arka_plan_metinsiz(pdf, tmp_path):
    """Düzenlenebilir modda arka plan görüntüsünde metin kalmamalı (çift görünmesin), tablo çizgileri kalmalı."""
    from pptx import Presentation
    dosya = donustur.pdf_pptx(pdf, tmp_path / "p", mod="duzenlenebilir", dpi=72, sayfalar=[0])
    resim = [sh for sh in Presentation(str(dosya)).slides[0].shapes if sh.shape_type == 13][0]
    px = pymupdf.Pixmap(resim.image.blob)
    # başlığın bulunduğu bölge (72..300, 72..95) tamamen beyaz, tablo çizgisi (72,230) civarı koyu piksel içerir
    assert all(px.pixel(x, y) == (255, 255, 255) for x in range(72, 300, 3) for y in range(72, 95, 3))
    assert any(px.pixel(x, 230) != (255, 255, 255) for x in range(72, 400))


# --- → PDF ---
def resim_olustur(yol: Path, boyut=(300, 200), renk=(200, 30, 30), bicim="PNG", mod="RGB"):
    from PIL import Image
    im = Image.new(mod, boyut, renk if mod != "RGBA" else renk + (255,))
    im.save(yol, bicim)
    return yol


def test_resimlerden_pdf(tmp_path):
    a = resim_olustur(tmp_path / "a.png", (300, 200))
    b = resim_olustur(tmp_path / "b.jpg", (200, 400), bicim="JPEG")
    c = resim_olustur(tmp_path / "c.png", (100, 100), mod="RGBA")
    [pdf] = donustur.resimlerden_pdf([a, b, c], tmp_path / "o", ad="Albüm")
    assert pdf.name == "Albüm.pdf"
    d = pymupdf.open(pdf)
    assert d.page_count == 3
    assert (d[0].rect.width, d[0].rect.height) == (842, 595)      # yatay resim → A4 yatay
    assert (d[1].rect.width, d[1].rect.height) == (595, 842)      # dikey resim → A4 dikey
    assert d[1].get_images() and d[0].get_pixmap().pixel(421, 297) == (200, 30, 30)
    # JPEG kayıpsız gömülür (yeniden kodlanmaz)
    assert d.extract_image(d[1].get_images()[0][0])["ext"] == "jpeg"
    # kenar boşluğu + zorla dikey + sayfa boyutu = resim
    [k] = donustur.resimlerden_pdf([a], tmp_path / "k", sayfa_boyutu="A5", yon="dikey", kenar=20)
    dk = pymupdf.open(k)
    assert (dk[0].rect.width, dk[0].rect.height) == (420, 595) and dk[0].get_pixmap().pixel(5, 5) == (255, 255, 255)
    [r] = donustur.resimlerden_pdf([a], tmp_path / "r", sayfa_boyutu="resim")
    assert pymupdf.open(r)[0].rect.width == 225
    ayri = donustur.resimlerden_pdf([a, b], tmp_path / "ay", ayri_dosyalar=True)
    assert [p.name for p in ayri] == ["a.pdf", "b.pdf"] and all(pymupdf.open(p).page_count == 1 for p in ayri)
    for kotu in (dict(yollar=[]), dict(yollar=[a], sayfa_boyutu="A9"), dict(yollar=[a], yon="eğik"),
                 dict(yollar=[a], kenar=1000), dict(yollar=[tmp_path / "yok.png"])):
        with pytest.raises(BelgeHatasi):
            donustur.resimlerden_pdf(klasor=tmp_path / "z", **kotu)
    bozuk = tmp_path / "bozuk.png"
    bozuk.write_bytes(b"png degil")
    with pytest.raises(BelgeHatasi):
        donustur.resimlerden_pdf([bozuk], tmp_path / "z")


def test_exif_yonu_uygulanir(tmp_path):
    from PIL import Image
    im = Image.new("RGB", (300, 100), (10, 10, 200))
    exif = im.getexif()
    exif[274] = 6  # 90° saat yönü döndür
    yol = tmp_path / "e.jpg"
    im.save(yol, "JPEG", exif=exif)
    [pdf] = donustur.resimlerden_pdf([yol], tmp_path / "o")
    assert pymupdf.open(pdf)[0].rect.width < pymupdf.open(pdf)[0].rect.height  # dikey (döndürülmüş) → dikey sayfa


def test_metinden_pdf(tmp_path):
    t = tmp_path / "not.txt"
    t.write_bytes("Merhaba dünya, Işık ğüşiöç İĞÜŞÖÇ.\n\n  Girintili satır\n".encode("cp1254"))  # Windows-1254 kodlu
    [pdf] = [donustur.metinden_pdf(t, tmp_path / "o")]
    metin = pymupdf.open(pdf)[0].get_text()
    assert "Merhaba dünya, Işık ğüşiöç İĞÜŞÖÇ." in metin and "Girintili" in metin
    t2 = tmp_path / "u.txt"
    t2.write_text("Şekerli çay", encoding="utf-8-sig")
    assert "Şekerli çay" in pymupdf.open(donustur.metinden_pdf(t2, tmp_path / "o"))[0].get_text()
    uzun = tmp_path / "uzun.txt"
    uzun.write_text("\n".join(f"Satır {i} içeriği" for i in range(300)), encoding="utf-8")
    assert pymupdf.open(donustur.metinden_pdf(uzun, tmp_path / "o")).page_count >= 3
    bos = tmp_path / "bos.txt"
    bos.write_text("  \n")
    with pytest.raises(BelgeHatasi):
        donustur.metinden_pdf(bos, tmp_path / "o")


def test_word_den_pdf(tmp_path):
    import docx
    r = resim_olustur(tmp_path / "gomulu.png", (200, 100), (0, 120, 0))
    d = docx.Document()
    d.add_heading("Rapor Başlığı İşçi", 1)
    d.add_paragraph("Bu paragrafta Işık, Şeker ve ğüşiöç var.")
    t = d.add_table(rows=2, cols=2)
    t.cell(0, 0).text, t.cell(0, 1).text, t.cell(1, 0).text, t.cell(1, 1).text = "Ürün", "Fiyat", "Çay", "12,50"
    d.add_picture(str(r), width=docx.shared.Inches(2))
    d.save(tmp_path / "a.docx")
    pdf = donustur.word_den_pdf(tmp_path / "a.docx", tmp_path / "o")
    doc = pymupdf.open(pdf)
    metin = doc[0].get_text()
    assert "Rapor Başlığı İşçi" in metin and "Işık, Şeker ve ğüşiöç" in metin and "12,50" in metin
    assert doc[0].get_images()
    with pytest.raises(BelgeHatasi):
        donustur.word_den_pdf(tmp_path / "ornek.pdf", tmp_path / "o")  # docx değil / yok
    docx.Document().save(tmp_path / "bos.docx")
    with pytest.raises(BelgeHatasi):
        donustur.word_den_pdf(tmp_path / "bos.docx", tmp_path / "o")


def test_excel_den_pdf(tmp_path):
    import datetime
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Satışlar"
    ws.append(["Ürün", "Adet", "Tutar", "Tarih"])
    ws.append(["Çay", 12, 1234.5, datetime.date(2026, 10, 16)])
    ws.append(["Şeker", 7, 88, None])
    ws2 = wb.create_sheet("Özet")
    ws2.append(["Toplam", 19])
    wb.save(tmp_path / "a.xlsx")
    pdf = donustur.excel_den_pdf(tmp_path / "a.xlsx", tmp_path / "o")
    metin = pymupdf.open(pdf)[0].get_text()
    assert "Satışlar" in metin and "Çay" in metin and "1.234,5" in metin and "16.10.2026" in metin and "Özet" in metin
    # geniş çalışma sayfası yatay basılır
    gen = openpyxl.Workbook()
    gen.active.append([f"S{i}" for i in range(10)])
    gen.save(tmp_path / "g.xlsx")
    sayfa = pymupdf.open(donustur.excel_den_pdf(tmp_path / "g.xlsx", tmp_path / "o"))[0]
    assert sayfa.rect.width > sayfa.rect.height
    openpyxl.Workbook().save(tmp_path / "bos.xlsx")
    with pytest.raises(BelgeHatasi):
        donustur.excel_den_pdf(tmp_path / "bos.xlsx", tmp_path / "o")
    (tmp_path / "bozuk.xlsx").write_bytes(b"degil")
    with pytest.raises(BelgeHatasi):
        donustur.excel_den_pdf(tmp_path / "bozuk.xlsx", tmp_path / "o")


def test_html_den_pdf(tmp_path):
    r = resim_olustur(tmp_path / "res.png", (200, 100), (0, 0, 200))
    (tmp_path / "s.html").write_text('<html><body><h1>Başlık Işık</h1><p>Paragraf ğüşiöç</p><img src="res.png"></body></html>',
                                     encoding="utf-8")
    pdf = donustur.html_dosyasindan_pdf(tmp_path / "s.html", tmp_path / "o")
    doc = pymupdf.open(pdf)
    assert "Başlık Işık" in doc[0].get_text() and "Paragraf ğüşiöç" in doc[0].get_text() and doc[0].get_images()


def test_pdf_den_pdf_gidis_donus(pdf, tmp_path):
    """PDF → metin → PDF ve PDF → Word içeriği Türkçe karakterleri kaybetmez."""
    txt = donustur.pdf_metin(pdf, tmp_path / "m", sayfa_ayraci=False)
    geri = donustur.metinden_pdf(txt, tmp_path / "g")
    assert "Işık Şirketi'nin ğüşiöç" in pymupdf.open(geri)[0].get_text().replace("\n", " ")


# --- sıkıştırma ---
def buyuk_resimli_pdf(yol: Path) -> Path:
    from PIL import Image
    rnd = random.Random(1)
    im = Image.new("RGB", (1600, 1200))
    im.putdata([(rnd.randrange(256), rnd.randrange(256), rnd.randrange(256)) for _ in range(1600 * 1200)])
    tampon = io.BytesIO()
    im.save(tampon, "JPEG", quality=95)
    d = pymupdf.open()
    p = d.new_page()
    p.insert_text((72, 60), "Fotoğraflı belge", fontname="arial", fontfile=str(ARIAL), fontsize=16)
    p.insert_image(pymupdf.Rect(36, 100, 536, 475), stream=tampon.getvalue())  # ~230 dpi
    d.save(yol)
    return yol


def test_sikistir_seviyeleri(tmp_path):
    kaynak = buyuk_resimli_pdf(tmp_path / "foto.pdf")
    boyut = kaynak.stat().st_size
    sonuclar = {}
    for seviye in donustur.SIKISTIRMA_SEVIYELERI:
        hedef, s = donustur.sikistir(kaynak, tmp_path / "o", seviye)
        sonuclar[seviye] = s.yeni_boyut
        assert hedef.name.startswith("foto_sikistirilmis") and s.eski_boyut == boyut
        d = pymupdf.open(hedef)
        assert d.page_count == 1 and "Fotoğraflı belge" in d[0].get_text().replace("\xa0", " ") and d[0].get_images()
    assert sonuclar["yuksek"] < sonuclar["orta"] < boyut * 0.8
    assert sonuclar["yuksek"] < boyut * 0.25 and sonuclar["dusuk"] <= boyut
    _, s = donustur.sikistir(kaynak, tmp_path / "o", "yuksek")
    assert s.kucultuldu and 0.5 < s.kazanc_orani < 1
    with pytest.raises(BelgeHatasi):
        donustur.sikistir(kaynak, tmp_path / "o", "ekstrem")
    # çıktı gerçekten çizilebilir
    hedef, _ = donustur.sikistir(kaynak, tmp_path / "o2", "yuksek")
    px = pymupdf.open(hedef)[0].get_pixmap()
    assert any(px.pixel(x, 250) != (255, 255, 255) for x in range(100, 400, 10))


def test_sikistir_zaten_kucuk_olani_buyutmez(tmp_path):
    kaynak = pdf_yap(tmp_path / "k.pdf", 1)
    hedef, s = donustur.sikistir(kaynak, tmp_path / "o", "orta")
    assert hedef.stat().st_size <= kaynak.stat().st_size
    if not s.kucultuldu:
        assert hedef.read_bytes() == kaynak.read_bytes()


# --- karşılaştırma ---
def test_karsilastir(tmp_path):
    a = pdf_yap(tmp_path / "a.pdf", 3, "Merhaba dunya")
    b = pdf_yap(tmp_path / "b.pdf", 3, "Merhaba dunya")
    ayni = donustur.karsilastir(a, b)
    assert len(ayni) == 3 and not any(f.farkli for f in ayni) and all(f.fark_png is None for f in ayni)
    c = pdf_yap(tmp_path / "c.pdf", 3, "Merhaba dunya")
    d = pymupdf.open(c)
    d[1].insert_text((72, 200), "Eklenen cümle burada", fontname="helv", fontsize=14)
    d.saveIncr()
    d.close()
    sonuc = donustur.karsilastir(a, c)
    assert [f.farkli for f in sonuc] == [False, True, False]
    f = sonuc[1]
    assert "Eklenen cümle burada" in " ".join(f.eklenen) and f.silinen == [] and f.piksel_orani > 0
    assert f.fark_png and pymupdf.Pixmap(f.fark_png).width == 595
    ters = donustur.karsilastir(c, a)
    assert "Eklenen cümle burada" in " ".join(ters[1].silinen) and ters[1].eklenen == []
    # sayfa sayısı farkı
    kisa = pdf_yap(tmp_path / "k.pdf", 2, "Merhaba dunya")
    fark = donustur.karsilastir(a, kisa)
    assert len(fark) == 3 and fark[2].yalniz == "a" and fark[2].farkli
    assert donustur.karsilastir(kisa, a)[2].yalniz == "b"
    # değişen kelime: hem silinen hem eklenen
    e = pdf_yap(tmp_path / "e.pdf", 1, "Merhaba evren")
    f2 = donustur.karsilastir(pdf_yap(tmp_path / "f.pdf", 1, "Merhaba dunya"), e)[0]
    assert "dunya" in " ".join(f2.silinen) and "evren" in " ".join(f2.eklenen)
    cagrilar = []
    donustur.karsilastir(a, b, ilerleme=lambda n, t: cagrilar.append((n, t)))
    assert cagrilar[0] == (0, 3) and cagrilar[-1] == (3, 3)


def test_karsilastir_farkli_sayfa_boyutu(tmp_path):
    a = pdf_yap(tmp_path / "a.pdf", 1, "Boyut")
    d = pymupdf.open()
    p = d.new_page(width=420, height=595)
    p.insert_text((72, 100), "Boyut 1", fontname="helv", fontsize=11)
    d.save(tmp_path / "b.pdf")
    f = donustur.karsilastir(a, tmp_path / "b.pdf")[0]
    assert f.piksel_orani > 0 and f.fark_png  # hata vermeden çalışır, fark bulur
