import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from eaglepdf.core import ocr
from eaglepdf.ui import ocr_arayuzu, theme
from eaglepdf.ui.ocr_arayuzu import AranabilirPenceresi, OcrMetinPenceresi
from eaglepdf.ui.pencere import AnaPencere
from test_ocr import taranmis

pytestmark = pytest.mark.skipif(not ocr.hazir_mi(), reason="OCR dil verisi kurulu değil")


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


def test_menu_ve_arac(pencere):
    assert "OCR" in [a.text().replace("&", "") for a in pencere.menuBar().actions()]
    assert not pencere.e_aranabilir.isEnabled()
    assert "ocr_bolge" in pencere._arac_eylemleri
    assert "ocr_bolge" in pencere._ek_ipuclari and "redaction" in pencere._ek_ipuclari  # eski ipuçları ezilmedi


def test_dialog_dogrulama(app):
    d = AranabilirPenceresi(3, 2)
    d.sayfalar.setText("9")
    d._onayla()
    assert d.hata.text()
    d.sayfalar.setText("1-2")
    assert d.secili_sayfalar() == [0, 1]
    d.sayfalar.setText("")
    assert d.secili_sayfalar() is None
    assert d.secili_dil() == "tur+eng"


def test_aranabilir_yap_akisi(pencere, tmp_path, monkeypatch):
    pencere.belge = None
    b = taranmis(tmp_path / "t.pdf")
    b.kapat()
    pencere.ac(str(tmp_path / "t.pdf"))
    monkeypatch.setattr(AranabilirPenceresi, "exec", lambda self: True)
    pencere.aranabilir_yap_ac()
    assert pencere.belge.ara("istanbul")
    assert pencere.belge.degisti
    assert "işlendi" in pencere.statusBar().currentMessage()


def test_bolge_eylemi(pencere, tmp_path, monkeypatch):
    taranmis(tmp_path / "t.pdf").kapat()
    pencere.ac(str(tmp_path / "t.pdf"))
    gosterilen = []
    monkeypatch.setattr(OcrMetinPenceresi, "exec", lambda self: gosterilen.append(self.kutu.toPlainText()))
    assert pencere._ocr_eylemi("ocr_bolge", 0, ((50, 90), (545, 140))) is True
    assert gosterilen and "stanbul" in gosterilen[0]
    assert pencere._ocr_eylemi("baska", 0, None) is False


def test_dil_verisi_yoksa_yonlendirir(pencere, tmp_path, monkeypatch):
    taranmis(tmp_path / "t.pdf").kapat()
    pencere.ac(str(tmp_path / "t.pdf"))
    monkeypatch.setattr(ocr_arayuzu, "dil_secenekleri", lambda: [])
    iletiler = []
    # Davranış güncellendi (2026-10-17): eskiden yalnızca uyarıydı; şimdi Dil Verisi penceresini açmayı önerir
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: iletiler.append(a[2]) or QMessageBox.No))
    pencere.aranabilir_yap_ac()
    assert iletiler and "traineddata" in iletiler[0] and "Dil Verisi penceresini" in iletiler[0]
