import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from eaglepdf.ui import theme
from eaglepdf.ui.ozellikler_penceresi import OzelliklerPenceresi
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
    p.ac(str(pdf_yap(tmp_path / "k.pdf", 1)))
    yield p
    if p.belge:
        p.belge.degisti = False
    p.close()


def test_degisenler_yalniz_degisen(app):
    d = OzelliklerPenceresi({"Başlık": "A", "Yazar": "B", "Sayfa sayısı": "3"})
    assert d.degisenler() == {}
    d.alanlar["konu"].setText("Işık")
    d.alanlar["baslik"].setText("A")  # değişmedi
    assert d.degisenler() == {"konu": "Işık"}


def test_duzenle_akisi(pencere, monkeypatch):
    def sahte(self):
        self.alanlar["baslik"].setText("Yeni Başlık")
        self.alanlar["yazar"].setText("Ata")
        return True
    monkeypatch.setattr(OzelliklerPenceresi, "exec", sahte)
    pencere.ozellikleri_goster()
    o = pencere.belge.ozellikler()
    assert o["Başlık"] == "Yeni Başlık" and o["Yazar"] == "Ata" and pencere.belge.degisti
    assert pencere.belge.geri_al() and pencere.belge.ozellikler()["Yazar"] == ""


def test_degisiklik_yoksa_belge_degismez(pencere, monkeypatch):
    monkeypatch.setattr(OzelliklerPenceresi, "exec", lambda self: True)
    pencere.ozellikleri_goster()
    assert not pencere.belge.degisti


def test_temizle(pencere, monkeypatch):
    pencere.belge.ozellikleri_ata(baslik="X", yazar="Y")
    pencere.belge.degisti = False

    def sahte(self):
        self.temizle_istendi = True
        return True
    monkeypatch.setattr(OzelliklerPenceresi, "exec", sahte)
    pencere.ozellikleri_goster()
    assert not pencere.belge.ozellikler()["Başlık"] and pencere.belge.degisti


def test_temizle_onayi(app, monkeypatch):
    d = OzelliklerPenceresi({"Başlık": "A"})
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.No))
    d._temizle_sor()
    assert not d.temizle_istendi and d.alanlar["baslik"].text() == "A"
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes))
    d._temizle_sor()
    assert d.temizle_istendi and d.alanlar["baslik"].text() == ""
