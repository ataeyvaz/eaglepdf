import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import uuid

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QInputDialog, QMessageBox

from eaglepdf.core import koruma
from eaglepdf.core.belge import Belge
from eaglepdf.ui import theme
from eaglepdf.ui import tek_ornek as tek_modulu
from eaglepdf.ui.ayarlar_penceresi import AyarlarPenceresi
from eaglepdf.ui.pencere import AnaPencere
from test_belge import pdf_yap
from test_tek_ornek import bekle, cocuk


@pytest.fixture(scope="module")
def app():
    a = QApplication.instance() or QApplication([])
    theme.apply(a)
    return a


@pytest.fixture
def ad(monkeypatch):
    """Gerçekte çalışan bir EaglePDF ile çakışmasın: bu testlere özel soket adı."""
    ad = f"EaglePDF-test-{uuid.uuid4().hex}"
    monkeypatch.setattr(tek_modulu, "sunucu_adi", lambda: ad)
    return ad


@pytest.fixture
def pencere(app, tmp_path):
    p = AnaPencere(str(tmp_path / "ayar.ini"))
    p.show()
    yield p
    for o in p._oturumlar:
        o.belge.degisti = False
    if p.tek_ornek is not None:
        p.tek_ornek.durdur()
    p.close()


def yollar_yap(tmp_path, n, sayfa=1):
    return [str(pdf_yap(tmp_path / f"d{i}.pdf", sayfa)) for i in range(n)]


def adlar(p):
    return [o.belge.yol.name for o in p._oturumlar]


# --- tek örnek isteği ---
def test_istek_pencereyi_one_getirir_ve_dosyalari_sekmede_acar(pencere, tmp_path):
    y = yollar_yap(tmp_path, 2)
    pencere.showMinimized()
    assert pencere.isMinimized()
    pencere.tek_ornek_istegi(y)
    assert not pencere.isMinimized() and adlar(pencere) == ["d0.pdf", "d1.pdf"]


def test_bos_istek_yalniz_one_getirir(pencere):
    pencere.showMinimized()
    pencere.tek_ornek_istegi([])
    assert not pencere.isMinimized() and pencere._oturumlar == []


def test_istek_buyutulmus_pencereyi_kucultmez(pencere):
    pencere.showMaximized()
    pencere.tek_ornek_istegi([])
    assert pencere.windowState() & Qt.WindowMaximized


def test_ayri_surecten_gelen_dosya_calisan_pencerede_sekme_olur(pencere, tmp_path, ad):
    pencere.tek_ornek_destegi = True
    pencere.ayarlar.setValue("tek_ornek", True)
    pencere._tek_ornek_ayarla()
    assert pencere.tek_ornek is not None and pencere.tek_ornek.calisiyor
    y = yollar_yap(tmp_path, 2)
    assert cocuk("gonder", ad, y)
    assert bekle(lambda: len(pencere._oturumlar) == 2)
    assert adlar(pencere) == ["d0.pdf", "d1.pdf"]


# --- ayarla aç/kapat ---
def test_ayar_degisince_sunucu_acilir_kapanir(pencere, ad):
    pencere.tek_ornek_destegi = True
    pencere.ayarlar.setValue("tek_ornek", False)
    pencere._tek_ornek_ayarla()
    assert pencere.tek_ornek is None
    pencere.ayarlar.setValue("tek_ornek", True)
    pencere._tek_ornek_ayarla()
    assert pencere.tek_ornek is not None and pencere.tek_ornek.calisiyor
    pencere._tek_ornek_ayarla()   # tekrar çağrı ikinci sunucu açmaz
    sunucu = pencere.tek_ornek
    pencere._tek_ornek_ayarla()
    assert pencere.tek_ornek is sunucu
    pencere.ayarlar.setValue("tek_ornek", False)
    pencere._tek_ornek_ayarla()
    assert pencere.tek_ornek is None and not sunucu.calisiyor
    assert tek_modulu.gonder(ad, [], 200) is False


def test_destek_kapaliyken_ayar_sunucu_acmaz(pencere, ad):
    pencere.ayarlar.setValue("tek_ornek", True)
    pencere._tek_ornek_ayarla()   # tek_ornek_destegi False (testlerde/gömülü kullanımda)
    assert pencere.tek_ornek is None


def test_pencere_kapaninca_sunucu_kilidi_birakilir(pencere, ad):
    pencere.tek_ornek_destegi = True
    pencere.ayarlar.setValue("tek_ornek", True)
    pencere._tek_ornek_ayarla()
    olay = QCloseEvent()
    pencere.closeEvent(olay)
    assert olay.isAccepted() and not pencere.tek_ornek.calisiyor
    yeni = tek_modulu.TekOrnekSunucu(ad)
    assert yeni.baslat()   # kilit serbest
    yeni.durdur()


# --- meşgulken kuyruk ---
def test_mesgulken_acma_istegi_kuyruga_alinir_sonra_acilir(pencere, tmp_path):
    y = yollar_yap(tmp_path, 2)
    with pencere._mesgul_blok():
        pencere.ac(y[0])
        pencere.tek_ornek_istegi([y[1]])
        assert pencere._oturumlar == [] and len(pencere._bekleyen_yollar) == 2   # etkin sekme işlem sırasında değişmez
        assert "işlem sürüyor" in pencere.statusBar().currentMessage()
    assert bekle(lambda: len(pencere._oturumlar) == 2)
    assert adlar(pencere) == ["d0.pdf", "d1.pdf"] and pencere._bekleyen_yollar == []


def test_ic_ice_mesgul_bloklarda_kuyruk_yalniz_en_disarida_bosalir(pencere, tmp_path):
    y = yollar_yap(tmp_path, 1)
    with pencere._mesgul_blok():
        with pencere._mesgul_blok():
            pencere.ac(y[0])
        QApplication.processEvents()
        assert pencere._oturumlar == []   # dıştaki blok sürüyor
    assert bekle(lambda: len(pencere._oturumlar) == 1)


# --- oturum ---
def test_oturum_kaydet_ve_geri_yukle(app, tmp_path):
    ini = str(tmp_path / "ayar.ini")
    y = yollar_yap(tmp_path, 3)
    p = AnaPencere(ini)
    p.show()
    p.ac_coklu(y)
    p.sekmeler.setCurrentIndex(1)   # d1 etkin
    p.close()
    assert p._oturumlar == []
    q = AnaPencere(ini)
    q.show()
    assert q.oturumu_geri_yukle() == 3
    assert adlar(q) == ["d0.pdf", "d1.pdf", "d2.pdf"] and q.belge.yol.name == "d1.pdf"
    q.close()


def test_geri_yukleme_eksik_parolali_bozuk_dosyayi_sessizce_atlar(app, tmp_path, monkeypatch):
    ini = str(tmp_path / "ayar.ini")
    y = yollar_yap(tmp_path, 2)
    b = Belge.ac(pdf_yap(tmp_path / "kor.pdf", 1))
    koruma.parola_ekle(b, tmp_path / "parolali.pdf", acma_parolasi="pw")
    b.kapat()
    (tmp_path / "bozuk.pdf").write_bytes(b"degil")
    p = AnaPencere(ini)
    p.ayarlar.setValue("son_oturum", [y[0], str(tmp_path / "yok.pdf"), str(tmp_path / "parolali.pdf"),
                                      str(tmp_path / "bozuk.pdf"), y[1]])
    p.ayarlar.setValue("son_oturum_etkin", y[0])
    p.show()
    sorular = []
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: sorular.append(1) or ("pw", True)))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: sorular.append("uyari")))
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: sorular.append("bilgi")))
    assert p.oturumu_geri_yukle() == 2
    assert sorular == [] and adlar(p) == ["d0.pdf", "d1.pdf"] and p.belge.yol.name == "d0.pdf"
    p.close()


def test_bos_oturum_kaydi_hicbir_sey_acmaz(app, tmp_path):
    ini = str(tmp_path / "ayar.ini")
    p = AnaPencere(ini)
    p.show()
    p.ac(yollar_yap(tmp_path, 1)[0])
    p.kapat()           # tüm sekmeler kapatıldı
    p.close()           # boş oturum kaydedilir
    q = AnaPencere(ini)
    q.show()
    assert q.oturumu_geri_yukle() == 0
    q.close()


def test_geri_yukleme_sekme_sinirini_asmaz(app, tmp_path):
    from eaglepdf.ui.oturum import EN_COK_SEKME
    ini = str(tmp_path / "ayar.ini")
    y = yollar_yap(tmp_path, EN_COK_SEKME + 2)
    p = AnaPencere(ini)
    p.ayarlar.setValue("son_oturum", y)
    p.show()
    assert p.oturumu_geri_yukle() == EN_COK_SEKME
    p.close()


def test_oturum_geri_yukleme_bir_kez_listeyi_koruyan_tek_dosya(app, tmp_path):
    """Qt INI tek elemanlı listeyi düz metin döndürür; geri yükleme bunu da çözer."""
    ini = str(tmp_path / "ayar.ini")
    y = yollar_yap(tmp_path, 1)
    p = AnaPencere(ini)
    p.show()
    p.ac(y[0])
    p.close()
    q = AnaPencere(ini)
    q.show()
    assert q.oturumu_geri_yukle() == 1 and adlar(q) == ["d0.pdf"]
    q.close()


# --- ayarlar penceresi ---
def test_ayarlar_penceresi_varsayilanlar_ve_kayit(pencere):
    d = AyarlarPenceresi(pencere.ayarlar, pencere)
    assert d.tek_ornek.isChecked() is True       # varsayılan: tek pencere
    assert d.oturum_geri.isChecked() is False    # varsayılan: kapalı
    d.tek_ornek.setChecked(False)
    d.oturum_geri.setChecked(True)
    d.uygula()
    assert str(pencere.ayarlar.value("tek_ornek")).lower() == "false"
    assert str(pencere.ayarlar.value("oturumu_geri_yukle")).lower() == "true"
    yeni = AyarlarPenceresi(pencere.ayarlar, pencere)
    assert yeni.tek_ornek.isChecked() is False and yeni.oturum_geri.isChecked() is True
