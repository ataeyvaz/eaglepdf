import gc

import pytest

from eaglepdf.core import gecmis
from eaglepdf.core.belge import Belge
from test_belge import pdf_yap

KB = 1024


@pytest.fixture(autouse=True)
def temiz(monkeypatch):
    """Her test kendi bütçesi ve temiz kayıt defteriyle çalışır."""
    monkeypatch.setattr(gecmis, "GENEL_BUTCE", 10_000)
    monkeypatch.setattr(gecmis, "EN_COK_BAYT", 10_000_000)
    gecmis.etkin_ata(None)
    for g in list(gecmis._kayitli):
        g.temizle()
    yield
    gecmis.etkin_ata(None)


def yukle(g: gecmis.Gecmis, adet: int, boyut: int = 100):
    for i in range(adet):
        g.geri.append((bytes([i % 256]) * boyut, False))


def test_bayt_ve_toplam():
    a, b = gecmis.Gecmis(), gecmis.Gecmis()
    yukle(a, 3)
    yukle(b, 2)
    b.ileri.append((b"x" * 50, False))
    assert a.bayt() == 300 and b.bayt() == 250 and gecmis.toplam_bayt() == 550


def test_butce_icindeyse_dokunulmaz():
    a, b = gecmis.Gecmis(), gecmis.Gecmis()
    gecmis.etkin_ata(a)
    yukle(a, 30, 100)   # 3000
    yukle(b, 30, 100)   # 3000
    gecmis.butceyi_uygula()
    assert len(a.geri) == 30 and len(b.geri) == 30


def test_once_etkin_olmayan_budanir_etkin_korunur():
    etkin, diger = gecmis.Gecmis(), gecmis.Gecmis()
    gecmis.etkin_ata(etkin)
    yukle(etkin, 50, 100)   # 5000
    yukle(diger, 70, 100)   # 7000 → toplam 12000 > 10000
    gecmis.butceyi_uygula()
    assert len(etkin.geri) == 50                      # etkin dokunulmadı
    assert gecmis.toplam_bayt() <= 10_000 and len(diger.geri) == 50
    assert diger.geri[0][0][0] == 20                  # en eski 20 görüntü silindi (en eskiler önce)


def test_en_cok_bayt_tutan_diger_belge_once_budanir():
    etkin, kucuk, buyuk = gecmis.Gecmis(), gecmis.Gecmis(), gecmis.Gecmis()
    gecmis.etkin_ata(etkin)
    yukle(etkin, 10, 100)    # 1000
    yukle(kucuk, 20, 100)    # 2000
    yukle(buyuk, 90, 100)    # 9000 → 12000
    gecmis.butceyi_uygula()
    assert len(kucuk.geri) == 20 and len(etkin.geri) == 10 and len(buyuk.geri) == 70


def test_digerleri_bosalinca_etkinin_en_eskisi_gider_son_adim_kalir():
    etkin, diger = gecmis.Gecmis(), gecmis.Gecmis()
    gecmis.etkin_ata(etkin)
    yukle(etkin, 150, 100)   # 15000 > 10000 ve başka belge yok
    gecmis.butceyi_uygula()
    assert gecmis.toplam_bayt() <= 10_000 and len(etkin.geri) == 100
    assert etkin.geri[-1][0][0] == 149               # en yeni adım duruyor
    tek = gecmis.Gecmis()
    gecmis.etkin_ata(tek)
    tek.geri.append((b"y" * 50_000, False))          # tek görüntü tek başına bütçeyi aşıyor
    gecmis.butceyi_uygula()
    assert len(tek.geri) == 1                        # son adım yine de korunur


def test_geri_bitince_ileri_budanir():
    etkin, diger = gecmis.Gecmis(), gecmis.Gecmis()
    gecmis.etkin_ata(etkin)
    diger.ileri.extend((bytes([i]) * 100, False) for i in range(120))   # 12000, geri yok
    gecmis.butceyi_uygula()
    assert gecmis.toplam_bayt() <= 10_000 and diger.ileri[0][0][0] == 20


def test_ekle_genel_butceyi_uygular_ve_ileriyi_temizler():
    etkin, diger = gecmis.Gecmis(), gecmis.Gecmis()
    gecmis.etkin_ata(etkin)
    yukle(diger, 90, 100)    # 9000
    etkin.ileri.append((b"z" * 10, False))
    etkin.ekle(b"a" * 2000, False)                   # toplam 11000 → diğerinden 10 adım gider
    assert etkin.ileri == [] and len(etkin.geri) == 1
    assert gecmis.toplam_bayt() <= 10_000 and len(diger.geri) == 80


def test_belge_basina_adim_siniri_hala_gecerli():
    g = gecmis.Gecmis()
    for i in range(gecmis.EN_COK_ADIM + 5):
        g.ekle(bytes([i % 256]), False)
    assert len(g.geri) == gecmis.EN_COK_ADIM


def test_belge_basina_bayt_siniri_hala_gecerli(monkeypatch):
    monkeypatch.setattr(gecmis, "EN_COK_BAYT", 450)
    monkeypatch.setattr(gecmis, "GENEL_BUTCE", 10**9)
    g = gecmis.Gecmis()
    for i in range(10):
        g.ekle(bytes([i]) * 100, False)
    assert len(g.geri) == 4 and g.geri[-1][0][0] == 9


def test_temizle_bellegi_birakir_ve_etkinligi_kaldirir():
    a = gecmis.Gecmis()
    gecmis.etkin_ata(a)
    yukle(a, 5)
    a.ileri.append((b"q", False))
    a.temizle()
    assert a.bayt() == 0 and gecmis.etkin() is None and gecmis.toplam_bayt() == 0


def test_cop_toplanan_gecmis_kayit_defterinden_duser():
    g = gecmis.Gecmis()
    yukle(g, 5)
    assert gecmis.toplam_bayt() == 500
    del g
    gc.collect()
    assert gecmis.toplam_bayt() == 0


def test_etkin_zayif_referans_kapanan_belgeyi_tutmaz():
    g = gecmis.Gecmis()
    gecmis.etkin_ata(g)
    del g
    gc.collect()
    assert gecmis.etkin() is None


# --- Belge ile bütünleşik ---
def test_belge_kapatinca_gecmis_birakilir(tmp_path, monkeypatch):
    b = Belge.ac(pdf_yap(tmp_path / "a.pdf", 1))
    gecmis.etkin_ata(b._gecmis)
    monkeypatch.setattr(gecmis, "GENEL_BUTCE", 10**9)
    b.ozellikleri_ata(baslik="x")
    assert b.geri_al_bayti > 0
    b.kapat()
    assert b.geri_al_bayti == 0 and not b.geri_alinabilir_mi


def test_belgeler_arasi_butce_etkin_belge_geri_alinabilir_kalir(tmp_path, monkeypatch):
    a = Belge.ac(pdf_yap(tmp_path / "a.pdf", 1))
    b = Belge.ac(pdf_yap(tmp_path / "b.pdf", 1))
    for i in range(3):
        b.ozellikleri_ata(baslik=f"b{i}")
    gecmis.etkin_ata(a._gecmis)
    monkeypatch.setattr(gecmis, "GENEL_BUTCE", 1)   # bütçe fiilen sıfır
    a.ozellikleri_ata(baslik="a0")
    assert not b.geri_alinabilir_mi                 # etkin olmayan belgenin geçmişi budandı
    assert a.geri_alinabilir_mi and len(a._gecmis.geri) == 1   # etkinin son adımı korundu
    assert a.geri_al() and a.ozellikler()["Başlık"] == ""
    a.kapat()
    b.kapat()


def test_geri_al_ve_yinele_butceyi_denetler(tmp_path, monkeypatch):
    a = Belge.ac(pdf_yap(tmp_path / "a.pdf", 1))
    gecmis.etkin_ata(a._gecmis)
    a.ozellikleri_ata(baslik="1")
    a.ozellikleri_ata(baslik="2")
    cagrilar = []
    gercek = gecmis.Gecmis.denetle
    monkeypatch.setattr(gecmis.Gecmis, "denetle", lambda self: cagrilar.append(1) or gercek(self))
    assert a.geri_al() and a.yinele()
    assert len(cagrilar) == 2
    a.kapat()
