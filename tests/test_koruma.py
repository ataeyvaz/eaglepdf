import pymupdf
import pytest

from eaglepdf.core import koruma
from eaglepdf.core.belge import Belge
from eaglepdf.core.hatalar import BelgeHatasi, ParolaGerekli


@pytest.fixture
def belge(tmp_path):
    b = Belge.yeni(2)
    b._doc[0].insert_text((72, 100), "Gizli belge")
    yol = tmp_path / "kaynak.pdf"
    b.kaydet(yol)
    return Belge.ac(yol)


def test_parola_ekle_acma_parolasi_ister(belge, tmp_path):
    hedef = tmp_path / "korumali.pdf"
    koruma.parola_ekle(belge, hedef, acma_parolasi="abc123")
    with pytest.raises(ParolaGerekli):
        Belge.ac(hedef)
    with pytest.raises(ParolaGerekli):
        Belge.ac(hedef, "yanlis")
    acik = Belge.ac(hedef, "abc123")
    assert acik.sayfa_sayisi == 2
    assert "Gizli belge" in acik._doc[0].get_text()
    acik.kapat()


def test_sadece_sahip_parolasi_herkes_acar_izinler_uygulanir(belge, tmp_path):
    hedef = tmp_path / "izinli.pdf"
    koruma.parola_ekle(belge, hedef, sahip_parolasi="sahip",
                       izinler={"kopyala": False, "duzenle": False})
    acik = Belge.ac(hedef)  # açma parolası yok
    izin = koruma.mevcut_izinler(acik)
    assert izin["yazdir"] is True
    assert izin["kopyala"] is False
    assert izin["duzenle"] is False
    acik.kapat()
    assert koruma.sahip_parolasi_dogru_mu(hedef, "sahip")
    assert not koruma.sahip_parolasi_dogru_mu(hedef, "baska")


def test_parola_girilmezse_hata(belge, tmp_path):
    with pytest.raises(BelgeHatasi):
        koruma.parola_ekle(belge, tmp_path / "x.pdf")


def test_bilinmeyen_izin_hata(belge, tmp_path):
    with pytest.raises(BelgeHatasi):
        koruma.parola_ekle(belge, tmp_path / "x.pdf", acma_parolasi="a", izinler={"uc": True})


def test_kaynagin_uzerine_yazilmaz(belge):
    with pytest.raises(BelgeHatasi):
        koruma.parola_ekle(belge, belge.yol, acma_parolasi="a")
    with pytest.raises(BelgeHatasi):
        koruma.parola_kaldir(belge, belge.yol)


def test_parola_kaldir(belge, tmp_path):
    korumali = tmp_path / "k.pdf"
    koruma.parola_ekle(belge, korumali, acma_parolasi="p")
    acik = Belge.ac(korumali, "p")
    assert koruma.sifreli_mi(acik)
    temiz = tmp_path / "temiz.pdf"
    koruma.parola_kaldir(acik, temiz)
    acik.kapat()
    doc = pymupdf.open(temiz)
    assert not doc.needs_pass and not doc.is_encrypted
    assert "Gizli belge" in doc[0].get_text()
    doc.close()


def test_sifresiz_belgede_izinler_acik(belge):
    assert not koruma.sifreli_mi(belge)
    assert all(koruma.mevcut_izinler(belge).values())
