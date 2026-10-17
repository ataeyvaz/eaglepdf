import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from eaglepdf.ui import pencere as pencere_modulu
from eaglepdf.ui import theme
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


def ac_n(p, tmp_path, n=3):
    for i in range(n):
        p.ac(str(pdf_yap(tmp_path / f"d{i}.pdf", 2)))


def adlar(p):
    return [o.belge.yol.name for o in p._oturumlar]


def cevap(monkeypatch, secenek):
    """_kapatmaya_izin kutusu: secenek 'farkli' | 'atla' | 'vazgec'. Sorulan metinleri döndürür."""
    sorulan = []

    def exec_(self_):
        sorulan.append(self_.text())
        return 0

    def tiklanan(self_):
        if secenek == "vazgec":
            return None
        onek = "Kaydetmeden" if secenek == "atla" else "Farklı"
        return next(b for b in self_.buttons() if b.text().startswith(onek))
    monkeypatch.setattr(QMessageBox, "exec", exec_)
    monkeypatch.setattr(QMessageBox, "clickedButton", tiklanan)
    return sorulan


def test_x_dugmesi_herhangi_bir_sekmeyi_kapatir(pencere, tmp_path):
    ac_n(pencere, tmp_path)
    pencere.sekmeler.tabCloseRequested.emit(0)   # etkin olmayan (ilk) sekme
    assert adlar(pencere) == ["d1.pdf", "d2.pdf"] and pencere.belge.yol.name == "d2.pdf"   # etkin değişmedi
    assert pencere._etkin == 1
    pencere.sekmeler.tabCloseRequested.emit(1)   # etkin sekme
    assert adlar(pencere) == ["d1.pdf"] and pencere._etkin == 0 and pencere.belge.yol.name == "d1.pdf"


def test_etkin_olmayan_sekme_kapaninca_etkin_belge_degismez(pencere, tmp_path):
    ac_n(pencere, tmp_path)
    pencere.sekmeler.setCurrentIndex(1)
    pencere._sekme_kapat(0)
    assert adlar(pencere) == ["d1.pdf", "d2.pdf"] and pencere._etkin == 0
    assert pencere.belge.yol.name == "d1.pdf" and pencere.goruntuleyici.belge is pencere.belge


def test_orta_tik_sekmeyi_kapatir(pencere, tmp_path):
    ac_n(pencere, tmp_path)
    kutu = pencere.sekmeler.tabRect(1)
    QTest.mouseClick(pencere.sekmeler, Qt.MiddleButton, Qt.NoModifier, kutu.center())
    assert adlar(pencere) == ["d0.pdf", "d2.pdf"]
    # boş yere orta tık hiçbir şey kapatmaz
    QTest.mouseClick(pencere.sekmeler, Qt.MiddleButton, Qt.NoModifier, QPoint(pencere.sekmeler.width() - 2, 5))
    assert len(pencere._oturumlar) == 2


def test_sol_tik_sekme_secer_kapatmaz(pencere, tmp_path):
    ac_n(pencere, tmp_path)
    QTest.mouseClick(pencere.sekmeler, Qt.LeftButton, Qt.NoModifier, pencere.sekmeler.tabRect(0).center())
    assert len(pencere._oturumlar) == 3 and pencere._etkin == 0


def test_degismis_sekme_x_ile_kapatilirken_sorulur(pencere, tmp_path, monkeypatch):
    ac_n(pencere, tmp_path)
    pencere._oturumlar[0].belge.degisti = True
    sorulan = cevap(monkeypatch, "vazgec")
    pencere._sekme_kapat(0)
    assert sorulan and "d0.pdf" in sorulan[0] and len(pencere._oturumlar) == 3
    assert pencere.belge.yol.name == "d0.pdf"   # soru sorulan sekme gösterilir
    cevap(monkeypatch, "atla")
    pencere._sekme_kapat(0)
    assert adlar(pencere) == ["d1.pdf", "d2.pdf"]


def test_diger_sekmeleri_kapat(pencere, tmp_path):
    ac_n(pencere, tmp_path, 4)
    pencere.diger_sekmeleri_kapat(1)
    assert adlar(pencere) == ["d1.pdf"] and pencere.belge.yol.name == "d1.pdf"
    assert pencere.goruntuleyici.belge is pencere.belge


def test_diger_sekmeleri_kapat_vazgec_durdurur(pencere, tmp_path, monkeypatch):
    ac_n(pencere, tmp_path, 4)
    pencere._oturumlar[2].belge.degisti = True   # d2 değişmiş; diğerleri temiz
    cevap(monkeypatch, "vazgec")
    pencere.diger_sekmeleri_kapat(0)
    # sırayla: d1 kapandı, d2'de vazgeçildi → durur; d2 ve d3 açık kalır
    assert adlar(pencere) == ["d0.pdf", "d2.pdf", "d3.pdf"]


def test_tumunu_kapat(pencere, tmp_path):
    ac_n(pencere, tmp_path, 3)
    belgeler = [o.belge for o in pencere._oturumlar]
    pencere.tum_sekmeleri_kapat()
    assert pencere._oturumlar == [] and pencere.belge is None and pencere.sekmeler.isHidden()
    assert all(b._doc.is_closed for b in belgeler) and not pencere.e_tumunu_kapat.isEnabled()


def test_tumunu_kapat_vazgec_orada_durur(pencere, tmp_path, monkeypatch):
    ac_n(pencere, tmp_path, 3)
    pencere._oturumlar[1].belge.degisti = True
    cevap(monkeypatch, "vazgec")
    pencere.tum_sekmeleri_kapat()
    assert adlar(pencere) == ["d1.pdf", "d2.pdf"]   # d0 kapandı, d1'de vazgeçildi → d1 ve sonrası açık


def test_mesgulken_sekme_kapanmaz(pencere, tmp_path):
    ac_n(pencere, tmp_path, 2)
    with pencere._mesgul_blok():
        assert pencere._sekme_kapat(0) is False
        pencere.tum_sekmeleri_kapat()
    assert len(pencere._oturumlar) == 2 and "işlem sürüyor" in pencere.statusBar().currentMessage()


def test_sekme_gezme_dongusel_ve_kisayollar(pencere, tmp_path):
    assert not pencere.e_sonraki_sekme.isEnabled()
    ac_n(pencere, tmp_path, 3)
    assert pencere.e_sonraki_sekme.isEnabled() and pencere.e_onceki_sekme.isEnabled()
    pencere.sekmeler.setCurrentIndex(0)
    pencere.sekme_gez(-1)
    assert pencere._etkin == 2          # başa sararak sona
    pencere.sekme_gez(1)
    assert pencere._etkin == 0
    assert [k.toString() for k in pencere.e_sonraki_sekme.shortcuts()] == ["Ctrl+Tab", "Ctrl+PgDown"]
    assert [k.toString() for k in pencere.e_onceki_sekme.shortcuts()] == ["Ctrl+Shift+Tab", "Ctrl+PgUp"]
    assert pencere.e_tumunu_kapat.shortcut().toString() == "Ctrl+Shift+W"
    pencere.tum_sekmeleri_kapat()
    assert not pencere.e_sonraki_sekme.isEnabled()


def test_gezme_tek_sekmede_bir_sey_yapmaz(pencere, tmp_path):
    ac_n(pencere, tmp_path, 1)
    pencere.sekme_gez(1)
    assert pencere._etkin == 0


def test_sag_tik_menusu_icerigi_ve_durumlari(pencere, tmp_path):
    ac_n(pencere, tmp_path, 2)
    menu = pencere._sekme_menusu(pencere._oturumlar[0])
    ad_eylem = {a.text(): a for a in menu.actions() if a.text()}
    assert list(ad_eylem) == ["Kapat", "Diğerlerini Kapat", "Tümünü Kapat", "Yolu Kopyala", "Klasörde Göster"]
    assert all(a.isEnabled() for a in ad_eylem.values())
    pencere._sekme_kapat(1)
    tek = {a.text(): a for a in pencere._sekme_menusu(pencere._oturumlar[0]).actions() if a.text()}
    assert not tek["Diğerlerini Kapat"].isEnabled()   # tek sekmede anlamsız
    from eaglepdf.core.belge import Belge
    from eaglepdf.ui.oturum import BelgeOturumu
    yeni = BelgeOturumu(Belge.yeni(1))   # yolu olmayan belge
    adsiz = {a.text(): a for a in pencere._sekme_menusu(yeni).actions() if a.text()}
    assert not adsiz["Yolu Kopyala"].isEnabled() and not adsiz["Klasörde Göster"].isEnabled()
    yeni.belge.kapat()


def test_sag_tik_menusu_eylemleri_calisir(pencere, tmp_path, monkeypatch):
    ac_n(pencere, tmp_path, 3)
    menu = pencere._sekme_menusu(pencere._oturumlar[1])
    eylem = {a.text(): a for a in menu.actions() if a.text()}
    eylem["Yolu Kopyala"].trigger()
    assert QApplication.clipboard().text() == str(tmp_path / "d1.pdf")
    cagrilar = []
    monkeypatch.setattr(pencere_modulu.subprocess, "Popen", lambda args, *a, **k: cagrilar.append(args))
    eylem["Klasörde Göster"].trigger()
    assert cagrilar == [["explorer", f"/select,{tmp_path / 'd1.pdf'}"]]
    eylem["Kapat"].trigger()
    assert adlar(pencere) == ["d0.pdf", "d2.pdf"]
    # menü açıldığı sekmeyi (nesne olarak) izler; sıra kayması yanlış sekmeyi kapatmaz
    menu2 = pencere._sekme_menusu(pencere._oturumlar[1])   # d2
    pencere._sekme_kapat(0)                                  # d0 kapandı → d2'nin sırası 0'a düştü
    {a.text(): a for a in menu2.actions() if a.text()}["Kapat"].trigger()
    assert pencere._oturumlar == [] and pencere.belge is None


def test_sag_tik_istegi_bos_alanda_menu_acmaz(pencere, tmp_path, monkeypatch):
    ac_n(pencere, tmp_path, 1)
    acilan = []

    class SahteMenu:   # gerçek QMenu.exec modal döngüye girer; yamalanamaz
        def exec(self, *a):
            acilan.append(1)

    istenen = []
    monkeypatch.setattr(pencere, "_sekme_menusu", lambda oturum: istenen.append(oturum) or SahteMenu())
    pencere._sekme_sag_tik(QPoint(pencere.sekmeler.width() - 2, 5))
    assert acilan == [] and istenen == []
    pencere._sekme_sag_tik(pencere.sekmeler.tabRect(0).center())
    assert acilan == [1] and istenen == [pencere._oturumlar[0]]
