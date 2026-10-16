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
def pencere(app, tmp_path):
    p = AnaPencere(str(tmp_path / "ayar.ini"))
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


def _bekle(app, n=8):
    import time
    for _ in range(n):
        app.processEvents()
        time.sleep(0.03)


def test_gorunum_modlari(pencere, tmp_path, app):
    pencere.ac(pdf_yap(tmp_path / "m.pdf", 5))
    _bekle(app)
    g = pencere.goruntuleyici
    pencere.e_tek.setChecked(True)
    pencere._gorunum_uygula()
    _bekle(app)
    assert g.mod == "tek" and sum(e.isVisible() for e in g._etiketler) == 1
    g.git(3)
    assert [e.indeks for e in g._etiketler if e.isVisible()] == [3]
    pencere.e_cift.setChecked(True)
    pencere._gorunum_uygula()
    _bekle(app)
    assert g.sutun == 2 and sorted(e.indeks for e in g._etiketler if e.isVisible()) == [2, 3]
    g.git(4)
    assert [e.indeks for e in g._etiketler if e.isVisible()] == [4]
    pencere.e_surekli.setChecked(True)
    pencere._gorunum_uygula()
    _bekle(app)
    assert all(e.isVisible() for e in g._etiketler)
    assert pencere.ayarlar.value("gorunum_mod") == "sureklu" and str(pencere.ayarlar.value("gorunum_sutun")) == "2"


def test_gece_modu(pencere, tmp_path, app):
    pencere.ac(pdf_yap(tmp_path / "g.pdf", 1))
    _bekle(app)
    g = pencere.goruntuleyici
    acik = g._etiketler[0].pix.toImage().pixelColor(5, 5)
    pencere.e_gece.setChecked(True)
    pencere._gece_uygula()
    _bekle(app)
    koyu = g._etiketler[0].pix.toImage().pixelColor(5, 5)
    assert acik.lightness() > 240 and koyu.lightness() < 20


def test_metin_secme_ve_kopyala(pencere, tmp_path, app):
    pencere.ac(pdf_yap(tmp_path / "s.pdf", 2, "Merhaba dunya"))
    _bekle(app)
    pencere.e_sec.setChecked(True)
    pencere._arac_uygula()
    g = pencere.goruntuleyici
    assert g.arac == "sec"
    # ilk sayfanın ilk kelimesinden ikinci sayfanın ikinci kelimesine kadar seç
    g._secim_bas = (0, 0)
    g._secim_son = (1, 1)
    g._secimi_boya()
    assert g.secili_metin() == "Merhaba dunya 1" + chr(10) + "Merhaba dunya"
    pencere.kopyala()
    assert QApplication.clipboard().text() == g.secili_metin()
    g.secimi_temizle()
    assert g.secili_metin() == ""


def test_yazdir_pdf_dosyasina(pencere, tmp_path, app):
    from PySide6.QtPrintSupport import QPrinter
    pencere.ac(pdf_yap(tmp_path / "y.pdf", 3))
    _bekle(app)
    yazici = QPrinter(QPrinter.HighResolution)
    yazici.setOutputFormat(QPrinter.PdfFormat)
    yazici.setOutputFileName(str(tmp_path / "cikti.pdf"))
    assert pencere.yazici_ile_yazdir(yazici) == 3
    import pymupdf
    assert pymupdf.open(tmp_path / "cikti.pdf").page_count == 3
    yazici2 = QPrinter(QPrinter.HighResolution)
    yazici2.setOutputFormat(QPrinter.PdfFormat)
    yazici2.setOutputFileName(str(tmp_path / "cikti2.pdf"))
    yazici2.setPrintRange(QPrinter.CurrentPage)
    assert pencere.yazici_ile_yazdir(yazici2) == 1


def test_simgeler(app):
    from eaglepdf.ui import simgeler
    for ad in simgeler.simge_adlari():
        assert not simgeler.simge(ad).pixmap(20, 20).isNull()
