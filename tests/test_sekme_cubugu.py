import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from eaglepdf.core import koruma
from eaglepdf.core.belge import Belge
from eaglepdf.ui import theme
from eaglepdf.ui.oturum import BelgeOturumu, sekme_basligi, sekme_ipucu
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


def test_baslik_ve_ipucu_yardimcilari(tmp_path):
    b = Belge.ac(pdf_yap(tmp_path / "Rapor.pdf", 1))
    o = BelgeOturumu(b)
    assert sekme_basligi(o) == "Rapor.pdf"
    assert str(tmp_path / "Rapor.pdf") in sekme_ipucu(o) and "Kaydedilmemiş" not in sekme_ipucu(o)
    b.degisti = True
    assert sekme_basligi(o) == "● Rapor.pdf" and "Kaydedilmemiş değişiklikler" in sekme_ipucu(o)
    b.degisti = False
    yeni = BelgeOturumu(Belge.yeni(1))
    assert sekme_basligi(yeni) == "● Adsız" and "yeni belge" in sekme_ipucu(yeni)
    b.kapat()
    yeni.belge.kapat()


def test_belge_yokken_gizli_acinca_gorunur(pencere, tmp_path):
    assert pencere.sekmeler.isHidden() and pencere.sekmeler.count() == 0
    pencere.ac(str(pdf_yap(tmp_path / "k.pdf", 1)))
    assert pencere.sekmeler.isVisible() and pencere.sekmeler.count() == 1
    assert pencere.sekmeler.tabText(0) == "k.pdf"
    assert str(tmp_path / "k.pdf") in pencere.sekmeler.tabToolTip(0)
    pencere.kapat()
    assert pencere.sekmeler.isHidden() and pencere.sekmeler.count() == 0


def test_degisti_isareti(pencere, tmp_path):
    pencere.ac(str(pdf_yap(tmp_path / "k.pdf", 1)))
    assert not pencere.sekmeler.tabText(0).startswith("●")
    pencere.belge.ozellikleri_ata(baslik="x")
    pencere._durumu_guncelle()
    assert pencere.sekmeler.tabText(0) == "● k.pdf"
    pencere.belge.geri_al()
    pencere.belge.degisti = False
    pencere._durumu_guncelle()
    assert pencere.sekmeler.tabText(0) == "k.pdf"


def test_parolali_belgede_kilit_simgesi(pencere, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QInputDialog
    b = Belge.ac(pdf_yap(tmp_path / "k.pdf", 1))
    koruma.parola_ekle(b, tmp_path / "p.pdf", acma_parolasi="pw")
    b.kapat()
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("pw", True)))
    pencere.ac(str(tmp_path / "p.pdf"))
    assert not pencere.sekmeler.tabIcon(0).isNull()
    assert "Parolayla" in pencere.sekmeler.tabToolTip(0)
    pencere.ac(str(pdf_yap(tmp_path / "d.pdf", 1)))  # ikinci sekme, parolasız: simge yok; ilk sekme kilitli kalır
    assert pencere.sekmeler.count() == 2
    assert not pencere.sekmeler.tabIcon(0).isNull() and pencere.sekmeler.tabIcon(1).isNull()


def test_cok_oturumda_tazele_ve_etkin(pencere, tmp_path):
    for ad in "abc":
        pencere._oturumlar.append(BelgeOturumu(Belge.ac(pdf_yap(tmp_path / f"{ad}.pdf", 1))))
    pencere._etkin = 1
    pencere._sekmeleri_tazele()
    assert [pencere.sekmeler.tabText(i) for i in range(3)] == ["a.pdf", "b.pdf", "c.pdf"]
    assert pencere.sekmeler.currentIndex() == 1
    pencere._oturumlar.pop()
    pencere._sekmeleri_tazele()
    assert pencere.sekmeler.count() == 2


def test_siralama_surukleyince_oturumlar_izlenir(pencere, tmp_path):
    for ad in "abc":
        pencere._oturumlar.append(BelgeOturumu(Belge.ac(pdf_yap(tmp_path / f"{ad}.pdf", 1))))
    pencere._etkin = 0   # a etkin
    pencere._sekmeleri_tazele()
    pencere.sekmeler.moveTab(0, 2)   # a → sona: b c a
    assert [o.belge.yol.name for o in pencere._oturumlar] == ["b.pdf", "c.pdf", "a.pdf"]
    assert pencere._etkin == 2 and pencere.belge.yol.name == "a.pdf"   # etkin belge değişmedi
    pencere.sekmeler.moveTab(2, 1)   # a → ortaya: b a c
    assert [o.belge.yol.name for o in pencere._oturumlar] == ["b.pdf", "a.pdf", "c.pdf"]
    assert pencere._etkin == 1 and pencere.belge.yol.name == "a.pdf"


def test_x_dugmesi_etkin_sekmeyi_kapatir(pencere, tmp_path, monkeypatch):
    pencere.ac(str(pdf_yap(tmp_path / "k.pdf", 1)))
    pencere.sekmeler.tabCloseRequested.emit(0)
    assert pencere.belge is None and pencere.sekmeler.isHidden()
    # değişmiş belgede mevcut kaydet sorusu çıkar; Vazgeç → sekme kalır
    pencere.ac(str(pdf_yap(tmp_path / "d.pdf", 1)))
    pencere.belge.degisti = True
    sorular = []

    def sahte_kutu(self_):  # _kapatmaya_izin QMessageBox.exec kullanır
        sorular.append(1)
        return 0
    monkeypatch.setattr(QMessageBox, "exec", sahte_kutu)
    monkeypatch.setattr(QMessageBox, "clickedButton", lambda self_: None)
    pencere.sekmeler.tabCloseRequested.emit(0)
    assert sorular and pencere.belge is not None and pencere.sekmeler.count() == 1


def test_ozel_kapat_dugmesi_tiklaninca_o_sekme_istenir(pencere, tmp_path):
    from PySide6.QtWidgets import QTabBar
    for ad in "ab":
        pencere._oturumlar.append(BelgeOturumu(Belge.ac(pdf_yap(tmp_path / f"{ad}.pdf", 1))))
    pencere._etkin = 0
    pencere._sekmeleri_tazele()
    istenen = []
    pencere.sekmeler.tabCloseRequested.disconnect()
    pencere.sekmeler.tabCloseRequested.connect(istenen.append)
    d1 = pencere.sekmeler.tabButton(1, QTabBar.RightSide)
    assert d1 is not None and pencere.sekmeler.tabButton(0, QTabBar.RightSide) is not d1
    d1.click()
    assert istenen == [1]
    pencere.sekmeler.tabButton(0, QTabBar.RightSide).click()
    assert istenen == [1, 0]
