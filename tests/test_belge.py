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
