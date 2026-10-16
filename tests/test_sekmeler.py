import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from eaglepdf.ui import theme
from eaglepdf.ui.oturum import EN_COK_SEKME
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


def ac_n(p, tmp_path, n, sayfa=3):
    yollar = [str(pdf_yap(tmp_path / f"d{i}.pdf", sayfa)) for i in range(n)]
    for y in yollar:
        p.ac(y)
    return yollar


def adlar(p):
    return [o.belge.yol.name for o in p._oturumlar]


def test_her_dosya_yeni_sekmede_acilir(pencere, tmp_path):
    ac_n(pencere, tmp_path, 3)
    assert adlar(pencere) == ["d0.pdf", "d1.pdf", "d2.pdf"] and pencere._etkin == 2
    assert pencere.sekmeler.count() == 3 and pencere.sekmeler.currentIndex() == 2
    assert pencere.belge.yol.name == "d2.pdf" and pencere.goruntuleyici.belge is pencere.belge


def test_ayni_dosya_ikinci_kez_acilirsa_o_sekmeye_gecilir(pencere, tmp_path):
    yollar = ac_n(pencere, tmp_path, 2)
    pencere.ac(yollar[0])
    assert len(pencere._oturumlar) == 2 and pencere._etkin == 0 and pencere.belge.yol.name == "d0.pdf"
    assert pencere.goruntuleyici.belge is pencere._oturumlar[0].belge
    assert "zaten açık" in pencere.statusBar().currentMessage()
    pencere.ac(str(tmp_path / "." / "D0.PDF"))   # dolaylı yol / harf farkı da aynı dosya
    assert len(pencere._oturumlar) == 2


def test_sekme_siniri(pencere, tmp_path, monkeypatch):
    ac_n(pencere, tmp_path, EN_COK_SEKME)
    bilgi = []
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: bilgi.append(a[2])))
    pencere.ac(str(pdf_yap(tmp_path / "fazla.pdf", 1)))
    assert len(pencere._oturumlar) == EN_COK_SEKME and bilgi and "en çok" in bilgi[0].lower()
    pencere.ac(str(tmp_path / "d0.pdf"))   # var olana geçmek sınırdan etkilenmez
    assert pencere._etkin == 0


def test_sekmeye_tiklayinca_gecer_ve_sayfa_olcek_geri_gelir(pencere, tmp_path):
    ac_n(pencere, tmp_path, 2, sayfa=5)
    pencere.sekmeler.setCurrentIndex(0)   # kullanıcı ilk sekmeyi seçer → currentChanged
    assert pencere._etkin == 0 and pencere.belge.yol.name == "d0.pdf"
    pencere.goruntuleyici.git(3)
    pencere.goruntuleyici.olcek_ata(0.8)
    pencere.sekmeler.setCurrentIndex(1)
    assert pencere._etkin == 1 and pencere.goruntuleyici.belge is pencere._oturumlar[1].belge
    assert pencere.goruntuleyici.gecerli_sayfa == 0   # ikinci belge kendi durumunda
    pencere.goruntuleyici.git(2)
    pencere.goruntuleyici.olcek_ata(1.5)
    pencere.sekmeler.setCurrentIndex(0)
    assert pencere.goruntuleyici.gecerli_sayfa == 3 and abs(pencere.goruntuleyici.olcek - 0.8) < 1e-3
    pencere.sekmeler.setCurrentIndex(1)
    assert pencere.goruntuleyici.gecerli_sayfa == 2 and abs(pencere.goruntuleyici.olcek - 1.5) < 1e-3


def test_menu_ve_baslik_etkin_belgeyi_izler(pencere, tmp_path):
    ac_n(pencere, tmp_path, 2)
    pencere.sekmeler.setCurrentIndex(0)
    assert pencere.belge_adi.text() == "d0.pdf" and "d0.pdf" in pencere.windowTitle()
    assert pencere.toplam_etiket.text() == " / 3" and pencere.e_kaydet.isEnabled()


def test_belgeler_birbirine_karismaz(pencere, tmp_path):
    ac_n(pencere, tmp_path, 2)
    pencere.belge.ozellikleri_ata(baslik="Sadece ikinci")
    pencere._durumu_guncelle()
    assert pencere.sekmeler.tabText(1) == "● d1.pdf" and pencere.sekmeler.tabText(0) == "d0.pdf"
    pencere.sekmeler.setCurrentIndex(0)
    assert not pencere.belge.degisti and pencere.belge.ozellikler()["Başlık"] == ""
    assert not pencere.belge.geri_alinabilir_mi   # geri al geçmişi belgeye özel
    pencere.sekmeler.setCurrentIndex(1)
    assert pencere.belge.geri_alinabilir_mi


def test_kapat_etkin_sekmeyi_kapatir_komsuya_gecer(pencere, tmp_path):
    ac_n(pencere, tmp_path, 3)
    pencere.sekmeler.setCurrentIndex(1)
    kapanan = pencere.belge
    pencere.kapat()
    assert adlar(pencere) == ["d0.pdf", "d2.pdf"] and kapanan._doc.is_closed
    assert pencere._etkin == 1 and pencere.belge.yol.name == "d2.pdf"   # sağdaki komşu
    pencere.kapat()   # d2 (sondaki) → soldaki komşu
    assert adlar(pencere) == ["d0.pdf"] and pencere._etkin == 0 and pencere.belge.yol.name == "d0.pdf"
    pencere.kapat()
    assert pencere.belge is None and pencere.sekmeler.isHidden() and not pencere.e_kaydet.isEnabled()


def test_degismis_sekmede_kapat_sorar_vazgec_sekmeyi_korur(pencere, tmp_path, monkeypatch):
    ac_n(pencere, tmp_path, 2)
    pencere.belge.degisti = True
    sorular = []
    monkeypatch.setattr(QMessageBox, "exec", lambda self_: sorular.append(self_.text()) or 0)
    monkeypatch.setattr(QMessageBox, "clickedButton", lambda self_: None)   # Vazgeç
    pencere.kapat()
    assert sorular and "d1.pdf" in sorular[0] and len(pencere._oturumlar) == 2


def test_pencere_kapatirken_tum_degismis_sekmeler_sorulur(pencere, tmp_path, monkeypatch):
    ac_n(pencere, tmp_path, 3)
    pencere._oturumlar[0].belge.degisti = True
    pencere._oturumlar[2].belge.degisti = True
    sorulan = []
    monkeypatch.setattr(QMessageBox, "exec", lambda self_: sorulan.append(self_.text()) or 0)
    monkeypatch.setattr(QMessageBox, "clickedButton", lambda self_: None)   # ilk soruda Vazgeç
    olay = QCloseEvent()
    pencere.closeEvent(olay)
    assert not olay.isAccepted() and len(sorulan) == 1 and "d0.pdf" in sorulan[0]
    assert len(pencere._oturumlar) == 3   # hiçbiri kapanmadı


def test_pencere_kapatma_hepsi_onaylanirsa_tum_belgeler_kapanir(pencere, tmp_path):
    ac_n(pencere, tmp_path, 3)
    belgeler = [o.belge for o in pencere._oturumlar]
    olay = QCloseEvent()
    pencere.closeEvent(olay)
    assert olay.isAccepted() and pencere._oturumlar == [] and all(b._doc.is_closed for b in belgeler)


def test_yeniden_yukle_ayni_sekmede(pencere, tmp_path):
    ac_n(pencere, tmp_path, 2, sayfa=2)
    pencere.sekmeler.setCurrentIndex(0)
    eski = pencere.belge
    eski.bos_sayfa_ekle(1)
    eski.kaydet(eski.yol, uzerine_yaz=True)   # diske 3 sayfa yazıldı
    pencere.ac(str(eski.yol), yeniden=True)
    assert len(pencere._oturumlar) == 2 and pencere._etkin == 0
    assert pencere.belge.sayfa_sayisi == 3 and pencere.goruntuleyici.belge is pencere.belge
    assert pencere.sekmeler.tabText(0) == "d0.pdf"


def test_ac_sor_birden_cok_dosya(pencere, tmp_path, monkeypatch):
    yollar = [str(pdf_yap(tmp_path / f"s{i}.pdf", 1)) for i in range(3)]
    monkeypatch.setattr(QFileDialog, "getOpenFileNames", staticmethod(lambda *a, **k: (yollar, "")))
    pencere.ac_sor()
    assert adlar(pencere) == ["s0.pdf", "s1.pdf", "s2.pdf"] and pencere._etkin == 2


def test_son_kullanilan_ve_surukle_birak_ayni_yolu_kullanir(pencere, tmp_path):
    yollar = ac_n(pencere, tmp_path, 2)
    assert pencere._son_liste()[:2] == [yollar[1], yollar[0]]
    pencere.ac(yollar[0])   # son kullanılanlar menüsü de ac() çağırır: yeni sekme açmaz
    assert len(pencere._oturumlar) == 2
