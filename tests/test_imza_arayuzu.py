import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog, QMessageBox

from eaglepdf.core import dijital_imza as di
from eaglepdf.core.belge import Belge
from eaglepdf.ui import theme
from eaglepdf.ui.imza_arayuzu import BosAlanPenceresi, ImzalaPenceresi, SertifikaOlusturPenceresi
from eaglepdf.ui.pencere import AnaPencere
from test_belge import pdf_yap

PAROLA = "sifre123"


@pytest.fixture(scope="module")
def app():
    a = QApplication.instance() or QApplication([])
    theme.apply(a)
    return a


@pytest.fixture(scope="module")
def pfx(tmp_path_factory):
    yol = tmp_path_factory.mktemp("sert") / "ata.pfx"
    di.sertifika_olustur(yol, "Ata Test", PAROLA)
    return yol


@pytest.fixture
def pencere(app, tmp_path):
    p = AnaPencere(str(tmp_path / "ayar.ini"))
    p.show()
    yield p
    if p.belge:
        p.belge.degisti = False
    p.close()


def test_menu(pencere):
    assert not pencere.e_imzala.isEnabled() and pencere.e_sertifika.isEnabled()
    metinler = [a.text() for a in pencere.m_koruma.actions()]
    assert "Dijital İmzala…" in metinler and "Sertifika Oluştur…" in metinler


def test_imzala_dialog_dogrulama(app, pfx):
    d = ImzalaPenceresi(3, str(pfx))
    d._onayla()
    assert d.hata.text()  # parola yok → hata
    d.parola.setText("yanlis")
    d._onayla()
    assert "parola" in d.hata.text()
    d.parola.setText(PAROLA)
    d.sayfa.setText("9")
    d._onayla()
    assert "arasında" in d.hata.text()
    d.sayfa.setText("2")
    d._onayla()
    assert d.result() == QDialog.DialogCode.Accepted
    v = d.degerler()
    assert v["sayfa"] == 1 and v["konum"] == "sag_alt" and v["alan_adi"] is None


def test_sertifika_ve_alan_dialoglari(app):
    d = SertifikaOlusturPenceresi()
    d._onayla()
    assert "Adınızı" in d.hata.text()
    d.ad.setText("A")
    d.parola.setText("p")
    d.parola2.setText("q")
    d._onayla()
    assert "aynı değil" in d.hata.text()
    b = BosAlanPenceresi(2)
    b.sayfa.setText("5")
    b._onayla()
    assert b.hata.text()
    b.sayfa.setText("2")
    b._onayla()
    assert b.degerler()["sayfa"] == 1


def test_imzala_akisi(pencere, pfx, tmp_path, monkeypatch):
    pencere.ac(str(pdf_yap(tmp_path / "k.pdf", 2)))
    hedef = tmp_path / "k (imzali).pdf"

    def sahte(self):
        self.parola.setText(PAROLA)
        return True
    monkeypatch.setattr(ImzalaPenceresi, "exec", sahte)
    monkeypatch.setattr(ImzalaPenceresi, "__init__", (lambda orijinal: lambda self, n, yol="", bos=None, parent=None:
                                                      orijinal(self, n, str(pfx), bos, parent))(ImzalaPenceresi.__init__))
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(hedef), "")))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.No))
    pencere.dijital_imzala()
    assert hedef.is_file() and di.dogrula(hedef)[0].butunluk_tamam


def test_dogrula_imzasiz(pencere, tmp_path, monkeypatch):
    pencere.ac(str(pdf_yap(tmp_path / "k.pdf", 1)))
    iletiler = []
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: iletiler.append(a[2])))
    pencere.imzalari_dogrula()
    assert "imza yok" in iletiler[0]


def test_imzali_belge_kayit_uyarisi(pencere, pfx, tmp_path, monkeypatch):
    b = Belge.ac(pdf_yap(tmp_path / "k.pdf", 1))
    imzali = tmp_path / "i.pdf"
    di.imzala(b, imzali, pfx, PAROLA, konum=None)
    b.kapat()
    pencere.ac(str(imzali))
    assert pencere._imzali_kayit_onayi() is True  # değişmemiş: uyarı yok
    pencere.belge.degisti = True
    sorular = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: sorular.append(a[2]) or QMessageBox.Cancel))
    assert pencere._imzali_kayit_onayi() is False and "GEÇERSİZ" in sorular[0]
    # değiştirilmiş imzalı belgeye yeni imza eklenemez
    bilgi = []
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: bilgi.append(a[2])))
    assert pencere._imza_icin_uygun_mu() is False and bilgi
