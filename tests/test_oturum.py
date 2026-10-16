import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from eaglepdf.core.belge import Belge
from eaglepdf.ui import theme
from eaglepdf.ui.oturum import EN_COK_SEKME, BelgeOturumu
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


def test_sinir_sabiti():
    assert EN_COK_SEKME == 8


def test_oturum_varsayilanlari_ve_ayni_dosya(tmp_path):
    yol = pdf_yap(tmp_path / "A.pdf", 1)
    b = Belge.ac(yol)
    o = BelgeOturumu(b)
    assert (o.gecerli_sayfa, o.olcek, o.arama_sonuclari, o.arama_no) == (0, 1.0, [], -1)
    assert o.ayni_dosya_mi(yol)
    assert o.ayni_dosya_mi(str(tmp_path / "." / "A.pdf"))       # dolaylı yol
    assert o.ayni_dosya_mi(str(tmp_path / "a.PDF"))              # Windows: harf duyarsız
    assert not o.ayni_dosya_mi(tmp_path / "baska.pdf")
    assert not o.ayni_dosya_mi(None)
    assert not BelgeOturumu(Belge.yeni(1)).ayni_dosya_mi(yol)    # yolu olmayan belge
    b.kapat()


def test_oturum_ornek_listeleri_birbirine_karismaz():
    x, y = BelgeOturumu(Belge.yeni(1)), BelgeOturumu(Belge.yeni(1))
    x.arama_sonuclari.append(1)
    assert y.arama_sonuclari == []
    x.belge.kapat(); y.belge.kapat()


def test_belge_property_bos_ve_dolu(pencere, tmp_path):
    assert pencere.belge is None and pencere._oturumlar == [] and pencere._etkin == -1
    pencere.ac(str(pdf_yap(tmp_path / "k.pdf", 2)))
    assert pencere.belge is not None and pencere.belge.sayfa_sayisi == 2
    assert len(pencere._oturumlar) == 1 and pencere._etkin == 0
    assert pencere._oturumlar[0].belge is pencere.belge


def test_belge_atamasi_uyumlulugu(pencere, tmp_path):
    a = Belge.ac(pdf_yap(tmp_path / "a.pdf", 1))
    b = Belge.ac(pdf_yap(tmp_path / "b.pdf", 1))
    pencere.belge = a                      # oturum yokken: yeni oturum
    assert pencere.belge is a and len(pencere._oturumlar) == 1
    pencere.belge = b                      # varken: etkin oturumun belgesi değişir, oturum sayısı artmaz
    assert pencere.belge is b and len(pencere._oturumlar) == 1
    pencere.belge = None                   # temizler
    assert pencere.belge is None and pencere._etkin == -1
    a.kapat()
    b.kapat()


def test_kapat_oturumu_temizler(pencere, tmp_path):
    pencere.ac(str(pdf_yap(tmp_path / "k.pdf", 1)))
    pencere.kapat()
    assert pencere.belge is None and pencere._oturumlar == []
    assert not pencere.e_kaydet.isEnabled()  # belge yokken eylemler kapalı
