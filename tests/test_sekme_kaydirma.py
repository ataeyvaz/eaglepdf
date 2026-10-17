import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from eaglepdf.ui import theme
from eaglepdf.ui.goruntuleyici import MOD_SUREKLI, MOD_TEK
from eaglepdf.ui.oturum import BelgeOturumu
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


def iki_sekme(p, tmp_path, sayfa=12):
    for ad in ("a", "b"):
        p.ac(str(pdf_yap(tmp_path / f"{ad}.pdf", sayfa)))
    p.sekmeler.setCurrentIndex(0)
    QApplication.processEvents()


def kaydirma(p) -> int:
    return p.goruntuleyici.verticalScrollBar().value()


def test_duzen_anahtari_olcek_mod_sutunla_degisir(pencere, tmp_path):
    iki_sekme(pencere, tmp_path, 3)
    g = pencere.goruntuleyici
    a = g.duzen_anahtari
    assert a == g.duzen_anahtari and len(a) == 3
    g.olcek_ata(g.olcek * 0.5)
    assert g.duzen_anahtari != a
    g.olcek_ata(g.olcek * 2)
    assert g.duzen_anahtari == a                   # aynı ölçeğe dönünce aynı anahtar
    g.mod_ata(MOD_TEK, 1)
    assert g.duzen_anahtari != a
    g.mod_ata(MOD_SUREKLI, 2)
    assert g.duzen_anahtari != a


def test_sekme_donunce_sayfa_ici_kaydirma_geri_gelir(pencere, tmp_path):
    iki_sekme(pencere, tmp_path)
    sb = pencere.goruntuleyici.verticalScrollBar()
    hedef = sb.maximum() // 2 + 137                 # bir sayfanın tam başlangıcı olmayan konum
    sb.setValue(hedef)
    assert kaydirma(pencere) == hedef
    sayfa = pencere.goruntuleyici.gecerli_sayfa
    pencere.sekmeler.setCurrentIndex(1)
    assert pencere._etkin == 1 and kaydirma(pencere) != hedef
    pencere.sekmeler.setCurrentIndex(0)
    assert kaydirma(pencere) == hedef               # sayfa başına değil, kaldığı yere
    assert pencere.goruntuleyici.gecerli_sayfa == sayfa


def test_iki_sekmenin_kaydirmasi_birbirinden_bagimsiz(pencere, tmp_path):
    iki_sekme(pencere, tmp_path)
    sb = pencere.goruntuleyici.verticalScrollBar()
    a_deger = sb.maximum() // 3
    sb.setValue(a_deger)
    pencere.sekmeler.setCurrentIndex(1)
    b_deger = pencere.goruntuleyici.verticalScrollBar().maximum() * 2 // 3
    pencere.goruntuleyici.verticalScrollBar().setValue(b_deger)
    pencere.sekmeler.setCurrentIndex(0)
    assert kaydirma(pencere) == a_deger
    pencere.sekmeler.setCurrentIndex(1)
    assert kaydirma(pencere) == b_deger


def test_baska_sekmede_olcek_degisse_de_kendi_olcegi_ve_kaydirmasi_doner(pencere, tmp_path):
    iki_sekme(pencere, tmp_path)
    sb = pencere.goruntuleyici.verticalScrollBar()
    sb.setValue(sb.maximum() // 2 + 137)
    sayfa = pencere.goruntuleyici.gecerli_sayfa
    pencere.sekmeler.setCurrentIndex(1)
    pencere.goruntuleyici.olcek_ata(pencere.goruntuleyici.olcek * 0.6)   # başka sekmede genel ölçek değişti
    eski_deger = pencere._oturumlar[0].kaydirma
    pencere.sekmeler.setCurrentIndex(0)
    assert abs(pencere.goruntuleyici.olcek - pencere._oturumlar[0].olcek) < 1e-3   # sekmenin kendi ölçeği döndü
    # sekmenin kendi ölçeği geri yüklendiği için düzen anahtarı yine eşleşir ve kaydırma da döner
    assert kaydirma(pencere) == eski_deger
    assert pencere.goruntuleyici.gecerli_sayfa == sayfa


def test_sayfa_modu_degistiyse_eski_kaydirma_uygulanmaz(pencere, tmp_path):
    iki_sekme(pencere, tmp_path)
    sb = pencere.goruntuleyici.verticalScrollBar()
    sb.setValue(sb.maximum() // 2 + 137)
    sayfa = pencere.goruntuleyici.gecerli_sayfa
    pencere.sekmeler.setCurrentIndex(1)
    pencere.e_tek.trigger()                         # genel sayfa modu değişti (setChecked eylemi tetiklemez) → düzen anahtarı farklı
    assert pencere.goruntuleyici.duzen_anahtari[1] == MOD_TEK
    pencere.sekmeler.setCurrentIndex(0)
    o = pencere._oturumlar[0]
    assert o.duzen != pencere.goruntuleyici.duzen_anahtari          # düzen farklı: eski kaydırma anlamsız
    assert pencere.goruntuleyici.gecerli_sayfa == sayfa             # ama sayfa korunur
    assert kaydirma(pencere) < o.kaydirma                           # tek sayfa düzeninde sayfa başı; sürekli düzenin değeri uygulanmadı


def test_yeni_sekme_kaydirma_geri_yuklemez(pencere, tmp_path):
    pencere.ac(str(pdf_yap(tmp_path / "a.pdf", 12)))
    pencere.goruntuleyici.verticalScrollBar().setValue(pencere.goruntuleyici.verticalScrollBar().maximum() // 2)
    pencere.ac(str(pdf_yap(tmp_path / "b.pdf", 12)))
    assert pencere._oturumlar[1].duzen == () and kaydirma(pencere) == 0     # yeni belge en baştan açılır


def test_oturum_varsayilanlari_kaydirma(tmp_path):
    from eaglepdf.core.belge import Belge
    b = Belge.yeni(1)
    o = BelgeOturumu(b)
    assert o.kaydirma == 0 and o.duzen == ()
    b.kapat()


def test_komsuya_gecerken_komsunun_kaydirmasi_gelir(pencere, tmp_path):
    for ad in "abc":
        pencere.ac(str(pdf_yap(tmp_path / f"{ad}.pdf", 12)))
    pencere.sekmeler.setCurrentIndex(2)
    sb = pencere.goruntuleyici.verticalScrollBar()
    c_deger = sb.maximum() // 2 + 55
    sb.setValue(c_deger)
    pencere.sekmeler.setCurrentIndex(1)             # b
    pencere.kapat()                                 # b kapanır → sağdaki komşu c gelir
    assert pencere.belge.yol.name == "c.pdf" and kaydirma(pencere) == c_deger
