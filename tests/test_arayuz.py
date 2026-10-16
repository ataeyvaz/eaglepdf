import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from eaglepdf import APP_NAME
from eaglepdf.ui import theme
from eaglepdf.ui.pencere import AnaPencere
from eaglepdf.ui.yardim import konulari_yukle
from eaglepdf.ui.hakkinda import hakkinda_metni
from test_belge import pdf_yap


@pytest.fixture(scope="module")
def app():
    a = QApplication.instance() or QApplication([])
    theme.apply(a)
    return a


@pytest.fixture
def pencere(app, tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    p = AnaPencere()
    p.ayarlar.clear()
    p.show()
    yield p
    p.belge and p.belge.__setattr__("degisti", False)
    p.close()


def test_bos_acilis(pencere):
    assert pencere.windowTitle() == APP_NAME
    assert not pencere.e_sil.isEnabled()


def test_ac_ve_islemler(pencere, tmp_path, app):
    y = pdf_yap(tmp_path / "a.pdf", 4)
    pencere.ac(y)
    app.processEvents()
    assert pencere.belge.sayfa_sayisi == 4
    assert pencere.kucuk.count() == 4 and pencere.e_sil.isEnabled()
    pencere.goruntuleyici.git(2)
    app.processEvents()
    pencere.dondur(90)
    assert pencere.belge.degisti and pencere.windowTitle().startswith("* ")
    pencere.bos_sayfa_ekle()
    assert pencere.belge.sayfa_sayisi == 5
    pencere.kucuk.siraDegisti.emit([1, 0, 2, 3, 4])
    assert pencere.belge.ara("Sayfa 2")[0][0] == 0
    pencere.bul_kutu.setText("Sayfa 3")
    assert pencere.bul_bilgi.text() == "1 / 1"
    pencere.bul_kutu.setText("yokyok")
    assert pencere.bul_bilgi.text() == "Sonuç yok"
    pencere.goruntuleyici.olcek_ata(2.0)
    assert round(pencere.goruntuleyici.olcek, 2) == 2.0


def test_ekran_goruntusu(pencere, tmp_path, app):
    pencere.resize(1100, 750)
    pencere.ac(pdf_yap(tmp_path / "b.pdf", 6))
    for _ in range(5):
        app.processEvents()
    import time
    time.sleep(0.3)
    for _ in range(10):
        app.processEvents()
    pencere.grab().save(str(tmp_path / "ekran.png"))
    assert (tmp_path / "ekran.png").stat().st_size > 5000
    import shutil
    shutil.copy(tmp_path / "ekran.png", os.environ.get("EKRAN_CIKTI", str(tmp_path / "x.png")))


def test_yardim_ve_hakkinda():
    konular = konulari_yukle()
    assert len(konular) >= 5 and all(k.govde for k in konular)
    assert "{APP_NAME}" not in "".join(k.govde for k in konular)
    assert APP_NAME in hakkinda_metni() and "AGPL" in hakkinda_metni()
