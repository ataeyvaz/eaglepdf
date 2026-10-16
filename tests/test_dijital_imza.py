import pymupdf
import pytest

from eaglepdf.core import dijital_imza as di
from eaglepdf.core.belge import Belge
from eaglepdf.core.hatalar import BelgeHatasi
from test_belge import pdf_yap

PAROLA = "sifre123"


@pytest.fixture(scope="module")
def pfx(tmp_path_factory):
    yol = tmp_path_factory.mktemp("sert") / "ata.pfx"
    di.sertifika_olustur(yol, "Ata Şahin İğdır", PAROLA, "ata@example.com")
    return yol


@pytest.fixture
def belge(tmp_path):
    return Belge.ac(pdf_yap(tmp_path / "k.pdf", 2))


def test_sertifika_bilgisi(pfx):
    b = di.sertifika_bilgisi(pfx, PAROLA)
    assert b.ad == "Ata Şahin İğdır" and b.kendinden_imzali and not b.suresi_dolmus
    assert b.bitis > b.baslangic


def test_yanlis_parola_ve_bozuk_dosya(pfx, tmp_path):
    with pytest.raises(BelgeHatasi, match="parola yanlış"):
        di.sertifika_bilgisi(pfx, "yanlis")
    bozuk = tmp_path / "bozuk.pfx"
    bozuk.write_bytes(b"degil")
    with pytest.raises(BelgeHatasi):
        di.imzalayici_yukle(bozuk, PAROLA)
    with pytest.raises(BelgeHatasi, match="bulunamadı"):
        di.imzalayici_yukle(tmp_path / "yok.pfx", PAROLA)


def test_sertifika_olustur_dogrulama(tmp_path):
    with pytest.raises(BelgeHatasi):
        di.sertifika_olustur(tmp_path / "a.pfx", " ", "p")
    with pytest.raises(BelgeHatasi):
        di.sertifika_olustur(tmp_path / "a.pfx", "Ad", "")


def test_gorunur_imza_ve_dogrulama(belge, pfx, tmp_path):
    assert not di.imzali_mi(belge)
    hedef = tmp_path / "imzali.pdf"
    di.imzala(belge, hedef, pfx, PAROLA, sayfa=1, konum="sag_alt", neden="Onay", yer="İstanbul")
    assert hedef.is_file() and not list(tmp_path.glob("*.tmp"))
    imzali = Belge.ac(hedef)
    assert di.imzali_mi(imzali) and imzali.sayfa_sayisi == 2
    durumlar = di.dogrula(imzali)
    assert len(durumlar) == 1
    d = durumlar[0]
    assert d.butunluk_tamam and not d.belge_sonradan_degisti
    assert d.imzalayan == "Ata Şahin İğdır"
    assert not d.guvenilir and "kimlik doğrulanmadı" in d.ozet  # kendinden imzalı
    # görünür kutu 2. sayfada ve Türkçe imzalayan adını içeriyor
    metin = imzali._doc[1].get_text()
    assert "Ata Şahin İğdır" in metin
    imzali.kapat()


def test_gorunmez_imza(belge, pfx, tmp_path):
    hedef = tmp_path / "gorunmez.pdf"
    di.imzala(belge, hedef, pfx, PAROLA, konum=None)
    imzali = Belge.ac(hedef)
    assert di.dogrula(imzali)[0].butunluk_tamam
    imzali.kapat()


def test_guvenilen_sertifika_ile_guvenilir(belge, pfx, tmp_path):
    hedef = tmp_path / "g.pdf"
    di.imzala(belge, hedef, pfx, PAROLA, konum=None)
    sert = di.imzalayici_yukle(pfx, PAROLA).signing_cert
    d = di.dogrula(hedef, guvenilen_sertifikalar=[sert])[0]
    assert d.guvenilir and d.ozet == "Geçerli imza"


def test_degistirilmis_belge_yakalanir(belge, pfx, tmp_path):
    hedef = tmp_path / "i.pdf"
    di.imzala(belge, hedef, pfx, PAROLA, konum="sol_ust")
    ham = bytearray(hedef.read_bytes())
    i = ham.index(b"%PDF-1.") + 7  # imzalı bayt aralığındaki sürüm rakamı (ayrıştırmayı bozmaz)
    ham[i] = ord("6") if ham[i] != ord("6") else ord("5")
    bozuk = tmp_path / "bozuk.pdf"
    bozuk.write_bytes(bytes(ham))
    d = di.dogrula(bozuk)[0]
    assert not d.butunluk_tamam and d.ozet.startswith("GEÇERSİZ")


def test_pymupdf_ile_yeniden_kaydetmek_imzayi_bozar(belge, pfx, tmp_path):
    hedef = tmp_path / "i.pdf"
    di.imzala(belge, hedef, pfx, PAROLA, konum=None)
    imzali = Belge.ac(hedef)
    imzali._doc[0].insert_text((72, 300), "sonradan")
    imzali.degisti = True
    yeni = tmp_path / "duzenlenmis.pdf"
    imzali.kaydet(yeni)
    imzali.kapat()
    durumlar = di.dogrula(yeni)
    # ya imza tamamen düşer ya da geçersiz görünür — geçerli kalmamalı
    assert not durumlar or not (durumlar[0].butunluk_tamam and not durumlar[0].belge_sonradan_degisti)


def test_ertelenmis_alan_ekle_ve_sonra_imzala(belge, pfx, tmp_path):
    ara = tmp_path / "alanli.pdf"
    _, ad = di.bos_alan_ekle(belge, ara, sayfa=0, konum="sol_alt", alan_adi="Yonetici")
    assert ad == "Yonetici"
    alanli = Belge.ac(ara)
    assert di.bos_imza_alanlari(alanli) == ["Yonetici"] and not di.imzali_mi(alanli)
    hedef = tmp_path / "dolu.pdf"
    di.imzala(alanli, hedef, pfx, PAROLA, alan_adi="Yonetici")
    alanli.kapat()
    dolu = Belge.ac(hedef)
    assert di.bos_imza_alanlari(dolu) == []
    d = di.dogrula(dolu)
    assert len(d) == 1 and d[0].alan == "Yonetici" and d[0].butunluk_tamam
    dolu.kapat()


def test_iki_imza_ust_uste(belge, pfx, tmp_path):
    a, b = tmp_path / "1.pdf", tmp_path / "2.pdf"
    di.imzala(belge, a, pfx, PAROLA, konum=None)
    bir = Belge.ac(a)
    di.imzala(bir, b, pfx, PAROLA, konum=None)
    bir.kapat()
    d = di.dogrula(b)
    assert len(d) == 2 and all(x.butunluk_tamam for x in d)


def test_kaynagin_uzerine_yazilmaz(belge, pfx):
    with pytest.raises(BelgeHatasi):
        di.imzala(belge, belge.yol, pfx, PAROLA)
    with pytest.raises(BelgeHatasi):
        di.bos_alan_ekle(belge, belge.yol)


def test_gecersiz_sayfa_ve_konum(belge, pfx, tmp_path):
    with pytest.raises(BelgeHatasi):
        di.imzala(belge, tmp_path / "x.pdf", pfx, PAROLA, sayfa=9)
    with pytest.raises(BelgeHatasi):
        di.imzala(belge, tmp_path / "x.pdf", pfx, PAROLA, konum="orta")
    assert not (tmp_path / "x.pdf").exists()


def test_imzasiz_belgede_dogrulama_bos(belge):
    assert di.dogrula(belge) == []


def test_alan_adlari_benzersiz_ve_cakisma_hatasi(belge, pfx, tmp_path):
    a = tmp_path / "a.pdf"
    _, ad1 = di.bos_alan_ekle(belge, a, alan_adi="Yonetici")
    alanli = Belge.ac(a)
    with pytest.raises(BelgeHatasi, match="zaten var"):
        di.bos_alan_ekle(alanli, tmp_path / "b.pdf", alan_adi="Yonetici")
    _, ad2 = di.bos_alan_ekle(alanli, tmp_path / "c.pdf")
    assert ad2 == "Imza2"
    alanli.kapat()
