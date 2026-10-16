import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pymupdf
import pytest
from PySide6.QtWidgets import QApplication, QFileDialog, QInputDialog, QMessageBox

from eaglepdf.core import koruma
from eaglepdf.core.belge import Belge
from eaglepdf.ui import koruma_arayuzu, theme
from eaglepdf.ui.koruma_arayuzu import ParolaEkleDialog
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
    if p.belge:
        p.belge.degisti = False
    p.close()


def test_menu_belge_yokken_kapali(pencere):
    assert not pencere.e_parola_ekle.isEnabled()
    assert "Koruma" in [a.text().replace("&", "") for a in pencere.menuBar().actions()]


def test_dialog_dogrulama(app):
    d = ParolaEkleDialog()
    d._onayla()
    assert "En az bir parola" in d.hata.text()
    d.acma.setText("a")
    d.acma2.setText("b")
    d._onayla()
    assert "aynı değil" in d.hata.text()
    d.acma2.setText("a")
    d.izin_kutulari["kopyala"].setChecked(False)
    assert d.degerler()["izinler"]["kopyala"] is False
    assert d.degerler()["acma_parolasi"] == "a"


def test_parola_ekle_akisi(pencere, tmp_path, monkeypatch):
    kaynak = pdf_yap(tmp_path / "k.pdf", 2)
    pencere.ac(str(kaynak))
    hedef = tmp_path / "k (korumali).pdf"

    def sahte_exec(self):
        self.acma.setText("pw")
        self.acma2.setText("pw")
        return True

    monkeypatch.setattr(ParolaEkleDialog, "exec", sahte_exec)
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(hedef), "")))
    pencere.parola_ekle()
    assert hedef.is_file()
    doc = pymupdf.open(hedef)
    assert doc.needs_pass
    doc.close()


def test_parola_kaldir_akisi(pencere, tmp_path, monkeypatch):
    kaynak = pdf_yap(tmp_path / "k.pdf", 1)
    b = Belge.ac(kaynak)
    korumali = tmp_path / "kor.pdf"
    koruma.parola_ekle(b, korumali, acma_parolasi="pw")
    b.kapat()
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("pw", True)))
    pencere.ac(str(korumali))
    assert pencere.belge is not None
    temiz = tmp_path / "temiz.pdf"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(temiz), "")))
    pencere.parola_kaldir()
    doc = pymupdf.open(temiz)
    assert not doc.needs_pass
    doc.close()


def test_sifresiz_belgede_bilgi(pencere, tmp_path, monkeypatch):
    pencere.ac(str(pdf_yap(tmp_path / "k.pdf", 1)))
    iletiler = []
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: iletiler.append(a[2])))
    pencere.parola_kaldir()
    pencere.izinleri_goster()
    assert len(iletiler) == 2 and all("parolasız" in i or "korumalı değil" in i for i in iletiler)


def test_kaydet_parolayi_korur_arayuz(pencere, tmp_path, monkeypatch):
    b = Belge.ac(pdf_yap(tmp_path / "k.pdf", 1))
    hedef = tmp_path / "kor.pdf"
    koruma.parola_ekle(b, hedef, acma_parolasi="pw")
    b.kapat()
    from PySide6.QtWidgets import QInputDialog
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("pw", True)))
    pencere.ac(str(hedef))
    pencere.belge._doc[0].insert_text((72, 300), "x")
    pencere.belge.degisti = True
    assert pencere._yaz(hedef, True)
    assert "parola korundu" in pencere.statusBar().currentMessage()
    doc = pymupdf.open(hedef)
    assert doc.needs_pass
    doc.close()


def test_sahip_kisitli_belgede_kayit_onayi(pencere, tmp_path, monkeypatch):
    b = Belge.ac(pdf_yap(tmp_path / "k.pdf", 1))
    hedef = tmp_path / "izinli.pdf"
    koruma.parola_ekle(b, hedef, sahip_parolasi="s", izinler={"duzenle": False})
    b.kapat()
    pencere.ac(str(hedef))
    assert pencere.belge.koruma_dusecek
    sorular = []
    monkeypatch.setattr(QMessageBox, "question",
                        staticmethod(lambda *a, **k: sorular.append(a[2]) or QMessageBox.Cancel))
    assert pencere._yaz(tmp_path / "cikti.pdf", False) is False and "kısıtlar kalkacak" in sorular[0]
    assert not (tmp_path / "cikti.pdf").exists()
