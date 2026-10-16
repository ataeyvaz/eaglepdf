from pathlib import Path

import pymupdf
import pytest

from eaglepdf import metin_tr
from eaglepdf.core.belge import Belge, BelgeHatasi, ParolaGerekli, aralik_coz, birlestir, bol


ARIAL = Path("C:/Windows/Fonts/arial.ttf")  # ı, ş, İ gibi Türkçe harfler için (yerleşik Helvetica'da yok)


def pdf_yap(yol: Path, sayfalar=3, metin="Sayfa", parola=None):
    d = pymupdf.open()
    for i in range(sayfalar):
        s = d.new_page()
        if ARIAL.exists():
            s.insert_text((72, 100), f"{metin} {i + 1}", fontname="arial", fontfile=str(ARIAL))
        else:
            s.insert_text((72, 100), f"{metin} {i + 1}", fontname="helv")
    if parola:
        d.save(yol, encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw=parola, owner_pw=parola)
    else:
        d.save(yol)
    d.close()
    return yol


@pytest.fixture
def pdf(tmp_path):
    return pdf_yap(tmp_path / "a.pdf", 5)


def test_aralik():
    assert aralik_coz("1-3, 5", 5) == [0, 1, 2, 4]
    assert aralik_coz("4-", 5) == [3, 4]
    for kotu in ("0", "6", "3-1", "x", ""):
        with pytest.raises(BelgeHatasi):
            aralik_coz(kotu, 5)


def test_ac_ve_render(pdf):
    b = Belge.ac(pdf)
    assert b.sayfa_sayisi == 5
    px = b.render(0, 1.0)
    assert px.width == 595 and px.height == 842
    b.kapat()


def test_ac_hatalar(tmp_path):
    with pytest.raises(BelgeHatasi):
        Belge.ac(tmp_path / "yok.pdf")
    bozuk = tmp_path / "b.pdf"
    bozuk.write_bytes(b"degil")
    with pytest.raises(BelgeHatasi):
        Belge.ac(bozuk)


def test_parola(tmp_path):
    y = pdf_yap(tmp_path / "p.pdf", 1, parola="gizli")
    with pytest.raises(ParolaGerekli):
        Belge.ac(y)
    with pytest.raises(ParolaGerekli):
        Belge.ac(y, "yanlis")
    assert Belge.ac(y, "gizli").sayfa_sayisi == 1


def test_sayfa_islemleri(pdf):
    b = Belge.ac(pdf)
    b.sayfa_sil([0, 4])
    assert b.sayfa_sayisi == 3 and b.degisti
    b.sayfa_dondur([0], 90)
    assert b.sayfa_boyutu(0) == (842, 595)
    b.sayfa_dondur([0], -90)
    assert b.sayfa_boyutu(0) == (595, 842)
    b.bos_sayfa_ekle(-1)
    assert b.sayfa_sayisi == 4 and b.ara("Sayfa 2")[0][0] == 1
    b.sayfa_tasi(0, 3)
    assert b.ara("Sayfa 2")[0][0] == 0
    with pytest.raises(BelgeHatasi):
        b.sayfa_sil(list(range(4)))


def test_kayit_orijinali_korur(pdf):
    b = Belge.ac(pdf)
    boyut = pdf.stat().st_size
    b.sayfa_sil([0])
    with pytest.raises(BelgeHatasi):
        b.kaydet(pdf)
    assert pdf.stat().st_size == boyut
    yeni = pdf.with_name("b.pdf")
    b.kaydet(yeni)
    assert Belge.ac(yeni).sayfa_sayisi == 4 and Belge.ac(pdf).sayfa_sayisi == 5
    assert not list(pdf.parent.glob("*.tmp"))
    assert not b.degisti


def test_uzerine_yaz_onayla(pdf):
    b = Belge.ac(pdf)
    b.sayfa_sil([0])
    b.kaydet(pdf, uzerine_yaz=True)
    assert Belge.ac(pdf).sayfa_sayisi == 4 and b.sayfa_sayisi == 4
    assert not list(pdf.parent.glob("*.tmp"))


def test_birlestir_bol(tmp_path):
    a = pdf_yap(tmp_path / "a.pdf", 2, "A")
    c = pdf_yap(tmp_path / "c.pdf", 3, "C")
    out = tmp_path / "m.pdf"
    assert birlestir([a, c], out) == 5
    m = Belge.ac(out)
    assert m.ara("C 1")[0][0] == 2
    m.kapat()
    with pytest.raises(BelgeHatasi):
        birlestir([a], out)
    with pytest.raises(BelgeHatasi):
        birlestir([a, c], a)
    parcalar = bol(out, tmp_path / "bol", her_n=2)
    assert [Belge.ac(p).sayfa_sayisi for p in parcalar] == [2, 2, 1]
    ayri = bol(out, tmp_path / "bol2", parcalar=[[0, 4], [1]])
    assert [p.name for p in ayri] == ["m_1.pdf", "m_2.pdf"]


def test_sayfa_cikar(pdf, tmp_path):
    b = Belge.ac(pdf)
    b.sayfalari_kaydet([1, 3], tmp_path / "c.pdf")
    c = Belge.ac(tmp_path / "c.pdf")
    assert c.sayfa_sayisi == 2 and c.ara("Sayfa 4")


@pytest.mark.skipif(not ARIAL.exists(), reason="Arial yazı tipi yok")
def test_turkce_arama(tmp_path):
    y = pdf_yap(tmp_path / "t.pdf", 1, "ISPARTA Işık")
    b = Belge.ac(y)
    assert b.ara("isparta") == []  # i ≠ I (Türkçe: I → ı)
    assert len(b.ara("ISPARTA")) == 1
    assert len(b.ara("ışık")) == 1  # Işık → ışık
    assert b.ara("") == []


def test_metin_tr():
    assert metin_tr.kucuk("IİıiŞ") == "ıiıişi"[:4] + "ş"
    assert metin_tr.buyuk("iıçş") == "İIÇŞ"


def test_belge_ozellikleri_duzenle_geri_al_temizle(tmp_path):
    b = Belge.ac(pdf_yap(tmp_path / "o.pdf", 1))
    b.ozellikleri_ata(baslik="Rapor — İstanbul", yazar=" Ata ", konu="Işık", anahtar="a, b")
    o = b.ozellikler()
    assert o["Başlık"] == "Rapor — İstanbul" and o["Yazar"] == "Ata" and o["Konu"] == "Işık" and b.degisti
    b.ozellikleri_ata(yazar="")  # yalnızca verilen alan değişir, boş = sil
    assert b.ozellikler()["Yazar"] == "" and b.ozellikler()["Başlık"] == "Rapor — İstanbul"
    b.kaydet(tmp_path / "k.pdf")
    k = Belge.ac(tmp_path / "k.pdf")
    assert k.ozellikler()["Konu"] == "Işık" and k.ozellikler()["Anahtar sözcükler"] == "a, b"
    k.ozellikleri_temizle()
    assert not k.ozellikler()["Başlık"] and not k.ozellikler()["Konu"]
    assert k.geri_al() and k.ozellikler()["Konu"] == "Işık"
    b.kapat(); k.kapat()


def test_pdf_tarihi():
    assert Belge.pdf_tarihi("D:20261016233047+03'00'") == "16.10.2026 23:30"
    assert Belge.pdf_tarihi("D:2026") == "01.01.2026"
    assert Belge.pdf_tarihi("") == "" and Belge.pdf_tarihi("garip") == "garip"


XMP_ORNEK = """<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
<rdf:Description rdf:about="" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:pdf="http://ns.adobe.com/pdf/1.3/"
 xmlns:xmpRights="http://ns.adobe.com/xap/1.0/rights/" pdf:Keywords="eski, anahtar">
<dc:title><rdf:Alt><rdf:li xml:lang="x-default">Eski Başlık</rdf:li></rdf:Alt></dc:title>
<dc:creator><rdf:Seq><rdf:li>Eski Yazar</rdf:li><rdf:li>İkinci Yazar</rdf:li></rdf:Seq></dc:creator>
<xmpRights:Marked>True</xmpRights:Marked>
</rdf:Description></rdf:RDF></x:xmpmeta>
<?xpacket end="w"?>"""


def test_ozellikler_xmp_ile_tutarli(tmp_path):
    b = Belge.ac(pdf_yap(tmp_path / "x.pdf", 1))
    b._doc.set_xml_metadata(XMP_ORNEK)
    b.ozellikleri_ata(baslik="Yeni Işık", yazar="Ata", anahtar="yeni, anahtar")
    xmp = b._doc.get_xml_metadata()
    assert "Yeni Işık" in xmp and "Eski Başlık" not in xmp
    assert "Ata" in xmp and "Eski Yazar" not in xmp and "İkinci Yazar" not in xmp
    assert 'pdf:Keywords="yeni, anahtar"' in xmp and "eski, anahtar" not in xmp
    assert "xmpRights:Marked" in xmp and "xpacket" in xmp  # başka veri ve sarmal korunur
    b.ozellikleri_ata(baslik="")  # boş = XMP'den de silinir
    assert "dc:title" not in b._doc.get_xml_metadata()
    assert b.geri_al() and "Yeni Işık" in b._doc.get_xml_metadata()
    b.kapat()


def test_xmp_olmayan_belgeye_xmp_eklenmez_ve_bozuk_xmp_atlanir(tmp_path):
    b = Belge.ac(pdf_yap(tmp_path / "x.pdf", 1))
    b.ozellikleri_ata(baslik="A")
    assert not (b._doc.get_xml_metadata() or "").strip()
    b._doc.set_xml_metadata("<bozuk")
    b.ozellikleri_ata(baslik="B")  # hata vermez
    assert b.ozellikler()["Başlık"] == "B"
    b.kapat()
