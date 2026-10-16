import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from eaglepdf.ui import pencere as pencere_modulu
from eaglepdf.ui import theme
from eaglepdf.ui.pencere import AnaPencere
from test_belge import pdf_yap


@pytest.fixture(scope="module")
def app():
    a = QApplication.instance() or QApplication([])
    theme.apply(a)
    return a


@pytest.fixture
def pencere(app, tmp_path):
    p = AnaPencere(str(tmp_path / "ayar.ini"))
    p.show()
    yield p
    for o in p._oturumlar:
        o.belge.degisti = False
    p.close()


def iki_sekme(p, tmp_path, sayfa=4):
    for ad in ("a", "b"):
        p.ac(str(pdf_yap(tmp_path / f"{ad}.pdf", sayfa)))
    p.sekmeler.setCurrentIndex(0)   # a etkin


def ara(p, metin):
    p.ara_ac()
    p.bul_kutu.setText(metin)   # textChanged → arama


def test_arama_durumu_sekmeye_ozel(pencere, tmp_path):
    iki_sekme(pencere, tmp_path)
    ara(pencere, "Sayfa 2")
    assert len(pencere._sonuclar) == 1 and pencere.bul_cubugu.isVisible()
    sonuclar_a = list(pencere._sonuclar)
    pencere.sekmeler.setCurrentIndex(1)   # b: temiz
    assert pencere.bul_kutu.text() == "" and pencere._sonuclar == [] and not pencere.bul_cubugu.isVisible()
    assert pencere.goruntuleyici._vurgu_sayfalari == {} and pencere.bul_bilgi.text() == ""
    ara(pencere, "Sayfa 3")
    sonuclar_b = list(pencere._sonuclar)
    pencere.sekmeler.setCurrentIndex(0)   # a geri: aynı metin, sonuçlar, vurgu, bilgi
    assert pencere.bul_kutu.text() == "Sayfa 2" and pencere._sonuclar == sonuclar_a
    assert pencere.bul_cubugu.isVisible() and pencere.bul_bilgi.text() == "1 / 1"
    assert list(pencere.goruntuleyici._vurgu_sayfalari) == [sonuclar_a[0][0]]
    pencere.sekmeler.setCurrentIndex(1)
    assert pencere.bul_kutu.text() == "Sayfa 3" and pencere._sonuclar == sonuclar_b


def test_sekme_donusu_yeni_arama_baslatmaz(pencere, tmp_path, monkeypatch):
    iki_sekme(pencere, tmp_path)
    ara(pencere, "Sayfa 2")
    pencere.sekmeler.setCurrentIndex(1)
    cagrilar = []
    gercek = pencere.belge.__class__.ara
    monkeypatch.setattr(pencere.belge.__class__, "ara", lambda self, m: cagrilar.append(m) or gercek(self, m))
    pencere.sekmeler.setCurrentIndex(0)
    pencere.sekmeler.setCurrentIndex(1)
    assert cagrilar == []   # metni geri yazmak aramayı yeniden tetiklemez


def test_yeni_sekme_aramayi_temizler(pencere, tmp_path):
    iki_sekme(pencere, tmp_path)
    ara(pencere, "Sayfa 2")
    pencere.ac(str(pdf_yap(tmp_path / "c.pdf", 2)))
    assert pencere.bul_kutu.text() == "" and pencere._sonuclar == [] and pencere.goruntuleyici._vurgu_sayfalari == {}
    assert not pencere.bul_cubugu.isVisible()


def test_belge_degisince_eski_vurgular_kalmaz(pencere, tmp_path):
    iki_sekme(pencere, tmp_path)
    ara(pencere, "Sayfa 2")
    assert pencere.goruntuleyici._vurgu_sayfalari
    pencere._belge_goster(0)   # sayfa işlemi sonrası görünüm tazeleme
    assert pencere.goruntuleyici._vurgu_sayfalari == {} and pencere._sonuclar == []


def test_panel_sekmesi_sekmeye_ozel(pencere, tmp_path):
    iki_sekme(pencere, tmp_path)
    pencere.paneller.setCurrentIndex(1)   # a: yer imleri
    pencere.sekmeler.setCurrentIndex(1)
    assert pencere.paneller.currentIndex() == 0   # b hiç seçilmedi: varsayılan (küçük resimler)
    pencere.paneller.setCurrentIndex(2)   # b: açıklamalar
    pencere.sekmeler.setCurrentIndex(0)
    assert pencere.paneller.currentIndex() == 1
    pencere.sekmeler.setCurrentIndex(1)
    assert pencere.paneller.currentIndex() == 2


def test_bekleyen_yerlestirme_sekme_degisince_iptal(pencere, tmp_path):
    iki_sekme(pencere, tmp_path)
    pencere._yerlestirmeyi_hazirla(b"png", "damga", 100.0, "muhur")
    assert pencere._etkin_arac() == "muhur" and pencere._bekleyen_png == b"png"
    pencere.sekmeler.setCurrentIndex(1)
    assert pencere._bekleyen_png is None and pencere._etkin_arac() == "el" and pencere.e_el.isChecked()


def test_cizim_araci_sekme_degisince_korunur(pencere, tmp_path):
    iki_sekme(pencere, tmp_path)
    pencere._arac_eylemleri["dikdortgen"].setChecked(True)
    pencere._arac_uygula()
    pencere.sekmeler.setCurrentIndex(1)
    assert pencere._etkin_arac() == "dikdortgen"   # belgeye bağlı olmayan araç değişmez


def test_mesgulken_sekme_degismez(pencere, tmp_path):
    iki_sekme(pencere, tmp_path)
    with pencere._mesgul_blok():
        pencere.sekmeler.setCurrentIndex(1)
        assert pencere._etkin == 0 and pencere.belge.yol.name == "a.pdf"
        assert pencere.sekmeler.currentIndex() == 0   # çubuk eski sekmeye döndü
        assert "işlem sürüyor" in pencere.statusBar().currentMessage()
    assert pencere._mesgul == 0
    pencere.sekmeler.setCurrentIndex(1)
    assert pencere._etkin == 1


def test_mesgul_sayaci_istisnada_sifirlanir(pencere):
    with pytest.raises(RuntimeError):
        with pencere._mesgul_blok():
            assert pencere._mesgul == 1
            raise RuntimeError("x")
    assert pencere._mesgul == 0


def test_toplu_yazdirma_sirasinda_mesgul(pencere, tmp_path, monkeypatch):
    iki_sekme(pencere, tmp_path)
    gorulen = []
    from eaglepdf.ui.toplu_yazdir import DosyaSonucu
    monkeypatch.setattr(pencere_modulu, "toplu_yazdir",
                        lambda *a, **k: gorulen.append(pencere._mesgul) or [DosyaSonucu(str(tmp_path / "a.pdf"), 1)])
    pencere.toplu_yazdir_calistir([str(tmp_path / "a.pdf")], object())
    assert gorulen == [1] and pencere._mesgul == 0


def test_gecis_sirasinda_tekrar_giris_yok_sayilir(pencere, tmp_path):
    iki_sekme(pencere, tmp_path)
    pencere._geciste = True
    pencere._sekme_secildi(1)
    assert pencere._etkin == 0
    pencere._geciste = False
    assert not pencere._geciste


def test_kapatinca_komsunun_durumu_gelir(pencere, tmp_path):
    for ad in "abc":
        pencere.ac(str(pdf_yap(tmp_path / f"{ad}.pdf", 4)))
    pencere.sekmeler.setCurrentIndex(2)       # c
    ara(pencere, "Sayfa 4")
    pencere.sekmeler.setCurrentIndex(1)       # b: sayfa 3'e git
    pencere.goruntuleyici.git(2)
    pencere.sekmeler.setCurrentIndex(0)       # a
    pencere.sekmeler.setCurrentIndex(1)       # b etkin, kapat → sağdaki komşu c gelir
    pencere.kapat()
    assert pencere.belge.yol.name == "c.pdf" and pencere.bul_kutu.text() == "Sayfa 4"
    assert len(pencere._sonuclar) == 1 and pencere.bul_cubugu.isVisible()
