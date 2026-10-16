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


def _korumali(belge, tmp_path, ad="k.pdf", **kw):
    hedef = tmp_path / ad
    koruma.parola_ekle(belge, hedef, **kw)
    return hedef


def test_kaydet_parolayi_korur_ayni_yola(belge, tmp_path):
    hedef = _korumali(belge, tmp_path, acma_parolasi="pw")
    b = Belge.ac(hedef, "pw")
    assert b.parola_korunur
    b._doc[0].insert_text((72, 200), "eklendi")
    b.degisti = True
    b.kaydet(hedef, uzerine_yaz=True)  # üzerine yazma: belge yeniden açılır
    assert not b.degisti and b._doc.page_count == 2 and "eklendi" in b._doc[0].get_text()
    b.kapat()
    with pytest.raises(ParolaGerekli):
        Belge.ac(hedef)
    k = Belge.ac(hedef, "pw")
    assert "eklendi" in k._doc[0].get_text()
    k.kapat()


def test_farkli_kaydet_korur_ve_parolasiz_secenegi(belge, tmp_path):
    hedef = _korumali(belge, tmp_path, acma_parolasi="pw")
    b = Belge.ac(hedef, "pw")
    b.kaydet(tmp_path / "kopya.pdf")
    with pytest.raises(ParolaGerekli):
        Belge.ac(tmp_path / "kopya.pdf")
    b.kaydet(tmp_path / "acik.pdf", parolayi_koru=False)
    b.kapat()
    Belge.ac(tmp_path / "acik.pdf").kapat()  # parolasız açılır


def test_izinler_kayitta_korunur(belge, tmp_path):
    hedef = _korumali(belge, tmp_path, acma_parolasi="a", sahip_parolasi="s", izinler={"kopyala": False})
    b = Belge.ac(hedef, "a")  # yalnızca açma parolasıyla: kısıtlı
    b.kaydet(tmp_path / "k2.pdf")
    b.kapat()
    k = Belge.ac(tmp_path / "k2.pdf", "a")
    assert koruma.mevcut_izinler(k)["kopyala"] is False
    k.kapat()
    assert b.izinler_kilitli and not b.sahip_yetkisi_var
    # kısıtlar aşılamaz: ne açma parolası ne eski sahip parolası sahip yetkisi verir
    assert koruma.sahip_parolasi_dogru_mu(tmp_path / "k2.pdf", "a") is False
    assert koruma.sahip_parolasi_dogru_mu(tmp_path / "k2.pdf", "s") is False


def test_kisitsiz_belgede_sahip_parolasi_acma_parolasi_olarak_surer(belge, tmp_path):
    hedef = _korumali(belge, tmp_path, acma_parolasi="a")
    b = Belge.ac(hedef, "a")
    assert not b.izinler_kilitli
    b.kaydet(tmp_path / "k4.pdf")
    b.kapat()
    assert koruma.sahip_parolasi_dogru_mu(tmp_path / "k4.pdf", "a")


def test_sahip_parolasiyla_acilan_belge(belge, tmp_path):
    hedef = _korumali(belge, tmp_path, acma_parolasi="a", sahip_parolasi="s", izinler={"kopyala": False})
    b = Belge.ac(hedef, "s")
    assert b._yetki in (4, 6)
    b.kaydet(tmp_path / "k3.pdf")
    b.kapat()
    assert koruma.sahip_parolasi_dogru_mu(tmp_path / "k3.pdf", "s")


def test_sifresiz_belge_parola_korumaz_ve_koruma_dusecek(belge, tmp_path):
    assert not belge.parola_korunur and not belge.koruma_dusecek
    hedef = _korumali(belge, tmp_path, sahip_parolasi="s", izinler={"duzenle": False})  # açma parolası yok
    b = Belge.ac(hedef)
    assert not b.parola_korunur and b.koruma_dusecek
    b.kapat()
