import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication

from eaglepdf.core import gecmis
from eaglepdf.ui import pencere as pencere_modulu
from eaglepdf.ui import theme
from eaglepdf.ui.oturum import BelgeOturumu, sekme_ipucu
from eaglepdf.ui.pencere import AnaPencere
from test_belge import pdf_yap


@pytest.fixture(scope="module")
def app():
    a = QApplication.instance() or QApplication([])
    theme.apply(a)
    return a


@pytest.fixture
def pencere(app, tmp_path, monkeypatch):
    monkeypatch.setattr(gecmis, "GENEL_BUTCE", 10**9)   # testler kendi bütçesini ayarlar
    gecmis.etkin_ata(None)
    p = AnaPencere(str(tmp_path / "ayar.ini"))
    p.show()
    yield p
    for o in p._oturumlar:
        o.belge.degisti = False
    p.close()
    gecmis.etkin_ata(None)


def ac_n(p, tmp_path, n=2):
    for i in range(n):
        p.ac(str(pdf_yap(tmp_path / f"d{i}.pdf", 2)))


def test_etkin_gecmis_sekmeyle_degisir(pencere, tmp_path):
    ac_n(pencere, tmp_path, 3)
    assert gecmis.etkin() is pencere._oturumlar[2].belge._gecmis
    pencere.sekmeler.setCurrentIndex(0)
    assert gecmis.etkin() is pencere._oturumlar[0].belge._gecmis
    pencere._sekme_kapat(0)   # etkin sekme kapandı → komşu etkin
    assert gecmis.etkin() is pencere.belge._gecmis


def test_butce_asilinca_etkin_olmayan_sekmenin_geri_ali_budanir(pencere, tmp_path, monkeypatch):
    ac_n(pencere, tmp_path, 2)                         # d0, d1
    pencere.sekmeler.setCurrentIndex(1)
    for i in range(3):
        pencere.belge.ozellikleri_ata(baslik=f"b{i}")  # d1'de 3 geri al adımı
    pencere.sekmeler.setCurrentIndex(0)                # d0 etkin
    monkeypatch.setattr(gecmis, "GENEL_BUTCE", 1)
    pencere.belge.ozellikleri_ata(baslik="a")
    assert pencere._oturumlar[0].belge.geri_alinabilir_mi              # etkinin son adımı korundu
    assert not pencere._oturumlar[1].belge.geri_alinabilir_mi          # diğer sekmenin geçmişi atıldı
    pencere.sekmeler.setCurrentIndex(1)
    assert pencere.belge.ozellikler()["Başlık"] == "b2"                # belgenin kendisi bozulmadı
    assert not pencere.belge.geri_alinabilir_mi


def test_sekme_kapaninca_geri_al_bellegi_birakilir(pencere, tmp_path):
    ac_n(pencere, tmp_path, 2)
    pencere.belge.ozellikleri_ata(baslik="x")
    assert gecmis.toplam_bayt() > 0
    pencere.belge.degisti = False   # kaydetme sorusu çıkmasın (modal kutu testi bekletir)
    pencere.tum_sekmeleri_kapat()
    assert gecmis.toplam_bayt() == 0 and gecmis.etkin() is None


def test_sekme_ipucu_geri_al_bilgisi(pencere, tmp_path):
    ac_n(pencere, tmp_path, 1)
    assert "Geri al" not in sekme_ipucu(pencere._oturumlar[0])
    pencere.belge.ozellikleri_ata(baslik="x")
    pencere.belge.ozellikleri_ata(baslik="y")
    ipucu = sekme_ipucu(pencere._oturumlar[0])
    assert "Geri al: 2 adım" in ipucu and "MB" in ipucu
    pencere._durumu_guncelle()
    assert "Geri al: 2 adım" in pencere.sekmeler.tabToolTip(0)


def test_buyuk_belge_bilgisi(pencere, tmp_path, monkeypatch):
    monkeypatch.setattr(pencere_modulu, "BUYUK_BELGE_BAYT", 1)
    pencere.ac(str(pdf_yap(tmp_path / "buyuk.pdf", 1)))
    assert "Büyük belge" in pencere.statusBar().currentMessage()
    monkeypatch.setattr(pencere_modulu, "BUYUK_BELGE_BAYT", 10**12)
    pencere.ac(str(pdf_yap(tmp_path / "kucuk.pdf", 1)))
    assert "Büyük belge" not in pencere.statusBar().currentMessage()


def test_mesgulken_pencere_kapanmaz(pencere, tmp_path):
    ac_n(pencere, tmp_path, 2)
    belgeler = [o.belge for o in pencere._oturumlar]
    with pencere._mesgul_blok():
        olay = QCloseEvent()
        pencere.closeEvent(olay)
        assert not olay.isAccepted()
    assert len(pencere._oturumlar) == 2 and not any(b._doc.is_closed for b in belgeler)
    assert "işlem sürüyor" in pencere.statusBar().currentMessage()


def test_olu_uyumluluk_kodu_kalmadi(pencere):
    assert not hasattr(pencere, "_belgeyi_kapat_sessiz")
    import inspect
    assert "kontrol_edildi" not in inspect.signature(pencere.ac).parameters


def test_oturum_olusturmak_geri_al_belleginin_kopyasini_tutmaz(tmp_path):
    from eaglepdf.core.belge import Belge
    b = Belge.ac(pdf_yap(tmp_path / "x.pdf", 1))
    o = BelgeOturumu(b)
    assert o.belge.geri_al_bayti == 0
    b.kapat()
