import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from eaglepdf.core import iliskilendirme
from eaglepdf.ui import ayarlar_penceresi, theme
from eaglepdf.ui.ayarlar_penceresi import AyarlarPenceresi
from eaglepdf.ui.goruntuleyici import MOD_TEK
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


def test_menu_ve_kisayol(pencere):
    assert pencere.e_ayarlar.isEnabled()
    assert pencere.e_ayarlar.shortcut().toString() == "Ctrl+,"


def test_degerler_yazilir_ve_uygulanir(pencere, tmp_path, monkeypatch):
    monkeypatch.setattr(iliskilendirme, "kayitli_mi", lambda *a, **k: False)
    d = AyarlarPenceresi(pencere.ayarlar, pencere)
    d.yazar.setText("Ata")
    d.mod.setCurrentIndex(d.mod.findData("tek"))
    d.cift.setChecked(True)
    d.gece.setChecked(True)
    d.acilis.setCurrentIndex(d.acilis.findData("yuzde100"))
    d.donusum.setText(str(tmp_path))
    d.uygula()
    pencere.ayarlari_uygula()
    assert pencere._yazar == "Ata"
    assert pencere.e_tek.isChecked() and pencere.e_cift.isChecked() and pencere.e_gece.isChecked()
    assert pencere.ayarlar.value("gorunum_mod") == MOD_TEK
    assert pencere.ayarlar.value("donusum_klasoru") == str(tmp_path)


def test_acilis_yakinlastirma(pencere, tmp_path):
    pencere.ayarlar.setValue("acilis_yakinlastirma", "yuzde100")
    pencere.ac(str(pdf_yap(tmp_path / "k.pdf", 1)))
    assert abs(pencere.goruntuleyici.olcek - 1.0) < 1e-6
    pencere.ayarlar.setValue("acilis_yakinlastirma", "genislik")
    pencere.ac(str(pdf_yap(tmp_path / "k2.pdf", 1)))
    assert abs(pencere.goruntuleyici.olcek - 1.0) > 1e-3


def test_son_listesini_temizle(pencere, tmp_path):
    pencere.ac(str(pdf_yap(tmp_path / "k.pdf", 1)))
    assert pencere._son_liste()
    d = AyarlarPenceresi(pencere.ayarlar, pencere)
    d._temizle_isaretle()
    d.uygula()
    pencere.ayarlari_uygula()
    assert pencere._son_liste() == []


def test_gecersiz_klasor_reddedilir(pencere, monkeypatch):
    uyari = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: uyari.append(a[2])))
    d = AyarlarPenceresi(pencere.ayarlar, pencere)
    d.donusum.setText("C:\yok\boyle\klasor")
    d._tamam()
    assert uyari and d.result() == 0


def test_iliski_dugmeleri(pencere, monkeypatch):
    durum = {"k": False}
    monkeypatch.setattr(iliskilendirme, "kayitli_mi", lambda *a, **k: durum["k"])
    monkeypatch.setattr(iliskilendirme, "kaydet", lambda *a, **k: durum.update(k=True))
    monkeypatch.setattr(iliskilendirme, "kaldir", lambda *a, **k: durum.update(k=False))
    d = AyarlarPenceresi(pencere.ayarlar, pencere)
    assert d.btn_ekle.isEnabled() and not d.btn_kaldir.isEnabled()
    d._iliski_ekle()
    assert not d.btn_ekle.isEnabled() and d.btn_kaldir.isEnabled() and "✔" in d.iliski_durum.text()
    d._iliski_kaldir()
    assert d.btn_ekle.isEnabled()


def test_ocr_dili_kullanilir(pencere, tmp_path):
    from eaglepdf.core import ocr
    if not ocr.hazir_mi("tur"):
        pytest.skip("OCR dil verisi yok")
    pencere.ayarlar.setValue("ocr_dil", "tur")
    from eaglepdf.ui.ocr_arayuzu import AranabilirPenceresi
    assert AranabilirPenceresi(1, 1, None, "tur").secili_dil() == "tur"
