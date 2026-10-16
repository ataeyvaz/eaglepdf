import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import time

import pymupdf
import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QInputDialog, QMessageBox

from eaglepdf.core import imzalar
from eaglepdf.core.belge import Belge, BelgeHatasi
from eaglepdf.ui import dialoglar, theme
from eaglepdf.ui.dialoglar import MetinPenceresi
from eaglepdf.ui.duzenleme_arayuzu import muhur_adi
from eaglepdf.ui.pencere import AnaPencere
from eaglepdf.ui.sayfa_islem_dialoglari import (
    AralikKutusu, ArkaPlanPenceresi, BoyutPenceresi, DuzlestirPenceresi, FiligranKaldirPenceresi, FiligranPenceresi,
    KirpPenceresi,
    MuhurPenceresi, SayfaNumarasiPenceresi, UstAltBilgiPenceresi, muhur_resmi,
)
from test_belge import ARIAL, pdf_yap


@pytest.fixture(scope="module")
def app():
    a = QApplication.instance() or QApplication([])
    theme.apply(a)
    return a


@pytest.fixture
def pencere(app, tmp_path):
    p = AnaPencere(str(tmp_path / "ayar.ini"))
    p.show()
    p.resize(1100, 800)
    yield p
    if p.belge:
        p.belge.degisti = False
    p.close()


def bekle(app, n=8):
    for _ in range(n):
        app.processEvents()
        time.sleep(0.03)


def ac(pencere, app, yol):
    pencere.ac(yol)
    bekle(app)
    return pencere.belge


def dialog_yama(monkeypatch, sinif, doldur):
    """`sinif.exec()` çağrısını, alanları `doldur(pencere)` ile doldurup kabul eden sürümle değiştirir."""
    def exec_(self):
        doldur(self)
        self._tamam()
        return 1 if not self.hata.text() else 0
    monkeypatch.setattr(sinif, "exec", exec_)


def png_bayt(renk=(0, 0, 255), boyut=(60, 30)) -> bytes:
    img = QImage(*boyut, QImage.Format_ARGB32)
    img.fill(0xFF000000 | (renk[0] << 16) | (renk[1] << 8) | renk[2])
    return dialoglar.png_baytlari(img)


def test_aralik_kutusu(app):
    k = AralikKutusu(10, 3, [1, 2, 5])
    assert k.secili_rb.isChecked() and k.sayfalar() == [1, 2, 5]
    k.tumu.setChecked(True)
    k.suzgec.setCurrentIndex(1)  # tek numaralı: 1, 3, 5, 7, 9 → 0 tabanlı çift indeksler
    assert k.sayfalar() == [0, 2, 4, 6, 8]
    k.suzgec.setCurrentIndex(2)
    assert k.sayfalar() == [1, 3, 5, 7, 9]
    k.suzgec.setCurrentIndex(0)
    k.gecerli_rb.setChecked(True)
    assert k.sayfalar() == [3]
    k.aralik_kutu.setText("2-4, 9")
    k.aralik_rb.setChecked(True)
    assert k.sayfalar() == [1, 2, 3, 8]
    k.aralik_kutu.setText("11")
    with pytest.raises(BelgeHatasi):
        k.sayfalar()
    tek = AralikKutusu(1, 0, [])
    tek.suzgec.setCurrentIndex(2)  # tek sayfalı belgede çift sayfa yok
    with pytest.raises(BelgeHatasi):
        tek.sayfalar()
    assert not tek.secili_rb.isEnabled()


def test_dialog_degerleri(app, tmp_path):
    k = KirpPenceresi(5, 0, [])
    k.birim.setCurrentText("cm")
    k.kutular["sol"].setValue(2)
    k.kutular["alt"].setValue(1)
    k._tamam()
    v = k.degerler()
    assert abs(v["sol"] - 2 * 72 / 2.54) < 0.01 and v["ust"] == 0 and v["sayfalar"] == [0, 1, 2, 3, 4] and not v["otomatik"]
    k2 = KirpPenceresi(5, 0, [])
    k2._tamam()
    assert "en az bir kenar" in k2.hata.text().lower()
    k2.oto_kutu.setChecked(True)
    k2._tamam()
    assert k2.degerler()["otomatik"]

    b = BoyutPenceresi(3, 0, [])
    b.birim.setCurrentText("mm")
    b._tamam()
    assert abs(b.degerler()["genislik"] - 595) < 1 and abs(b.degerler()["yukseklik"] - 842) < 1
    b.yatay.setChecked(True)
    assert abs(b.en.value() * 72 / 25.4 - 842) < 1
    b.hazir.setCurrentText("Özel")
    assert b.en.isEnabled()

    f = FiligranPenceresi(3, 1, [])
    f._tamam()
    assert "filigran metnini" in f.hata.text().lower()
    f.metin.setText(" GİZLİ ")
    f.opaklik.setValue(40)
    f.aci.setValue(-30)
    f.on_plan.setCurrentIndex(1)
    f._tamam()
    v = f.degerler()
    assert v["tur"] == "metin" and v["metin"] == "GİZLİ" and v["opaklik"] == 0.4 and v["aci"] == -30 and not v["on_plan"]
    resim = tmp_path / "f.png"
    resim.write_bytes(png_bayt())
    f2 = FiligranPenceresi(3, 1, [])
    f2.sekmeler.setCurrentIndex(1)
    f2._tamam()
    assert "resim seçin" in f2.hata.text().lower()
    f2.resim_yolu.setText(str(resim))
    f2.aci.setValue(30)
    f2.opaklik.setValue(50)
    f2._tamam()
    v2 = f2.degerler()
    img = QImage.fromData(v2["png"])
    assert v2["tur"] == "resim" and img.width() > 60 and (img.pixel(img.width() // 2, img.height() // 2) >> 24) & 0xFF in range(120, 135)

    a = ArkaPlanPenceresi(2, 0, [])
    a._tamam()
    assert a.degerler()["renk"] == "#fff8e1" and a.degerler()["png"] is None
    a.resim_yolu.setText(str(resim))
    a.resim_rb.setChecked(True)
    a._tamam()
    assert a.degerler()["png"].startswith(imzalar.PNG_IMZASI) and a.degerler()["renk"] is None

    u = UstAltBilgiPenceresi(4, 0, [])
    u._tamam()
    assert "metni girin" in u.hata.text()
    u.ust[0].setText("Rapor")
    u.alt[1].setText("{sayfa}/{toplam}")
    u._tamam()
    v = u.degerler()
    assert v["ust"] == ("Rapor", "", "") and v["alt"] == ("", "{sayfa}/{toplam}", "") and v["kenar"] == 36

    n = SayfaNumarasiPenceresi(4, 0, [])
    n.bicim.setCurrentText("sabit")
    n._tamam()
    assert "{n}" in n.hata.text()
    n.bicim.setCurrentText("Sayfa {n} / {toplam}")
    n.konum.setCurrentIndex(2)
    n._tamam()
    assert n.degerler()["konum"] == "ust-sag" and n.degerler()["bicim"] == "Sayfa {n} / {toplam}"

    d = DuzlestirPenceresi()
    d.ek.setChecked(False)
    d.form.setChecked(False)
    d._tamam()
    assert d.hata.text()
    d.form.setChecked(True)
    d._tamam()
    assert d.degerler() == {"ek_aciklamalar": False, "form_alanlari": True}


def test_muhur_resmi_ve_penceresi(app):
    img = muhur_resmi("ONAYLANDI", "#2e7d32", "16.10.2026")
    assert img.width() > 300 and (img.pixel(2, 2) >> 24) == 0  # köşe saydam
    assert any((img.pixel(x, img.height() // 2) >> 24) > 200 for x in range(img.width()))  # çerçeve/yazı opak
    m = MuhurPenceresi()
    m._tamam()
    assert "yazın" in m.hata.text()
    m.metin.setText("KABUL EDİLDİ")
    m._tamam()
    assert m.ad() == "KABUL EDİLDİ" and m.png().startswith(imzalar.PNG_IMZASI)
    from pathlib import Path
    assert muhur_adi(Path("20261016-120000-KABUL EDİLDİ.png")) == "KABUL EDİLDİ"
    assert muhur_adi(Path("20261016-120000-KABUL EDİLDİ-2.png")) == "KABUL EDİLDİ"


def test_kirp_sayfa_islemi(pencere, tmp_path, app, monkeypatch):
    ac(pencere, app, pdf_yap(tmp_path / "k.pdf", 3))

    def doldur(d):
        d.birim.setCurrentText("pt")
        d.kutular["sol"].setValue(50)
        d.kutular["sag"].setValue(45)
        d.aralik.tumu.setChecked(True)
    dialog_yama(monkeypatch, KirpPenceresi, doldur)
    pencere.kirp_ac()
    assert all(pencere.belge.sayfa_boyutu(i) == (500, 842) for i in range(3))
    assert pencere.goruntuleyici._etiketler[0].width() == round(500 * pencere.goruntuleyici.olcek)
    assert pencere.windowTitle().startswith("* ")
    pencere.geri_al()
    assert pencere.belge.sayfa_boyutu(0) == (595, 842)
    pencere.kirp_ac()
    pencere.kirpmayi_kaldir()
    assert pencere.belge.sayfa_boyutu(0) == (595, 842)


def test_boyut_filigran_arkaplan_ustalt_numara(pencere, tmp_path, app, monkeypatch):
    b = ac(pencere, app, pdf_yap(tmp_path / "p.pdf", 4, "Merhaba dunya"))
    dialog_yama(monkeypatch, BoyutPenceresi, lambda d: (d.hazir.setCurrentText("A5"), d.aralik.tumu.setChecked(True)))
    pencere.boyut_ac()
    assert abs(b.sayfa_boyutu(0)[0] - 420) < 0.5 and abs(b.sayfa_boyutu(0)[1] - 595) < 0.5  # mm'den pt'ye yuvarlama
    dialog_yama(monkeypatch, FiligranPenceresi, lambda d: (d.metin.setText("GİZLİ"), d.aralik.tumu.setChecked(True)))
    pencere.filigran_ac()
    assert "GİZLİ" in b._doc[2].get_text()
    dialog_yama(monkeypatch, ArkaPlanPenceresi, lambda d: d.aralik.gecerli_rb.setChecked(True))
    pencere.arka_plan_ac()
    assert b.render(0, 1.0).pixel(2, 2) == (255, 248, 225)
    assert b.render(1, 1.0).pixel(2, 2) == (255, 255, 255)

    def ustalt(d):
        d.ust[2].setText("{sayfa}/{toplam}")
        d.aralik.tumu.setChecked(True)
    dialog_yama(monkeypatch, UstAltBilgiPenceresi, ustalt)
    pencere.ustalt_ac()
    assert "3/4" in b._doc[2].get_text()
    dialog_yama(monkeypatch, SayfaNumarasiPenceresi, lambda d: (d.aralik.tumu.setChecked(True), d.baslangic.setValue(10)))
    pencere.numara_ac()
    assert "13" in b._doc[3].get_text()
    assert pencere.e_geri.isEnabled()
    for _ in range(5):
        pencere.geri_al()
    assert not pencere.belge.geri_alinabilir_mi
    assert pencere.belge.sayfa_boyutu(0) == (595, 842) and "GİZLİ" not in pencere.belge._doc[2].get_text()


def test_kalici_sil_araci_ve_metin_ara(pencere, tmp_path, app, monkeypatch):
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    b = ac(pencere, app, pdf_yap(tmp_path / "s.pdf", 2, "GIZLI TC 12345"))
    r = b.ara("12345")[0][1]
    pencere.goruntuleyici.aracEylemi.emit("redaction", 0, ((r[0] - 1, r[1] - 1), (r[2] + 1, r[3] + 1)))
    assert "12345" not in b._doc[0].get_text() and "12345" in b._doc[1].get_text()
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("GIZLI", True))
    pencere.metin_ara_ve_sil()
    assert pencere.belge.ara("GIZLI") == []
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("yokyok", True))
    gosterilen = []
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: gosterilen.append(a[2]))
    pencere.metin_ara_ve_sil()
    assert gosterilen and "bulunamadı" in gosterilen[0]
    # onay verilmezse silinmez
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.No)
    pencere.goruntuleyici.aracEylemi.emit("redaction", 1, ((50, 50), (400, 130)))
    assert "12345" in pencere.belge._doc[1].get_text()


def test_metin_duzenle_araci(pencere, tmp_path, app, monkeypatch):
    if not ARIAL.exists():
        pytest.skip("Arial yok")
    b = ac(pencere, app, pdf_yap(tmp_path / "m.pdf", 1, "Merhaba dunya"))

    def exec_(self):
        assert self.kutu.toPlainText() == "Merhaba dunya 1"
        self.kutu.setPlainText("Güncel ışık metni")
        return 1
    monkeypatch.setattr(MetinPenceresi, "exec", exec_)
    pencere._arac_eylemleri["metin_duzenle"].setChecked(True)
    pencere._arac_uygula()
    g = pencere.goruntuleyici
    QTest.mouseClick(g._etiketler[0], Qt.LeftButton, pos=QPoint(round(100 * g.olcek), round(95 * g.olcek)))
    metin = pencere.belge._doc[0].get_text()
    assert "Merhaba" not in metin and "Güncel ışık metni" in metin
    # metin olmayan yere tıklamak mesaj gösterir
    QTest.mouseClick(g._etiketler[0], Qt.LeftButton, pos=QPoint(round(400 * g.olcek), round(700 * g.olcek)))
    assert "düzenlenebilir metin yok" in pencere.statusBar().currentMessage()


def test_resim_muhur_yerlestir_tasi_boyutlandir(pencere, tmp_path, app):
    b = ac(pencere, app, pdf_yap(tmp_path / "r.pdf", 1))
    g = pencere.goruntuleyici
    pencere._yerlestirmeyi_hazirla(png_bayt((0, 0, 255), (80, 40)), "mavi", 200, "resim")
    assert g.arac == "resim"
    g.aracEylemi.emit("resim", 0, ((300, 300), None))  # tıklama: varsayılan 200 pt genişlik, oran korunur
    e = b.ek_listele()[0]
    assert e.etiket == "Mühür / Resim" and e.metin == "mavi"
    assert abs((e.rect[2] - e.rect[0]) - 200) < 2 and abs((e.rect[3] - e.rect[1]) - 100) < 2
    assert g.arac == "duzenle" and g.secili_ek.xref == e.xref   # yerleştirince seçilir
    assert b.render(0, 1.0).pixel(300, 300) == (0, 0, 255)
    # sayfa dışına taşan tıklama içeri alınır; sürüklenen kutuya sığdırılır
    pencere._yerlestirmeyi_hazirla(png_bayt((255, 0, 0), (80, 40)), "kirmizi", 200, "resim")
    g.aracEylemi.emit("resim", 0, ((5, 5), None))
    son = b.ek_listele()[-1].rect
    assert son[0] >= -1 and son[1] >= -1
    g.aracEylemi.emit("resim", 0, ((100, 600), (160, 700)))
    kutu = b.ek_listele()[-1].rect
    assert abs((kutu[2] - kutu[0]) - 60) < 2 and abs((kutu[3] - kutu[1]) - 30) < 2

    # tutamaçtan boyutlandırma ve sürükleyerek taşıma (gerçek fare olaylarıyla)
    xref = b.ek_listele()[0].xref
    r0 = b.ek_listele()[0].rect
    g.ek_secimini_ayarla(b.ek_listele()[0])
    et = g._etiketler[0]
    o = g.olcek
    r = g.secili_ek.rect
    QTest.mousePress(et, Qt.LeftButton, pos=QPoint(round(r[2] * o), round(r[3] * o)))
    QTest.mouseMove(et, QPoint(round((r[2] + 100) * o), round((r[3] + 50) * o)))
    QTest.mouseRelease(et, Qt.LeftButton, pos=QPoint(round((r[2] + 100) * o), round((r[3] + 50) * o)))
    yeni = [x for x in b.ek_listele() if x.xref == xref][0].rect
    assert abs((yeni[2] - r[2]) - 100) < 3 and abs((yeni[3] - r[3]) - 50) < 3
    r = yeni
    QTest.mousePress(et, Qt.LeftButton, pos=QPoint(round((r[0] + 20) * o), round((r[1] + 20) * o)))
    QTest.mouseMove(et, QPoint(round((r[0] + 60) * o), round((r[1] + 50) * o)))
    QTest.mouseRelease(et, Qt.LeftButton, pos=QPoint(round((r[0] + 60) * o), round((r[1] + 50) * o)))
    tasinmis = [x for x in b.ek_listele() if x.xref == xref][0].rect
    assert abs((tasinmis[0] - r[0]) - 40) < 3 and abs((tasinmis[1] - r[1]) - 30) < 3
    pencere.geri_al()
    pencere.geri_al()
    geri = [x for x in pencere.belge.ek_listele() if x.xref == xref][0].rect
    assert all(abs(a - b_) < 2 for a, b_ in zip(geri, r0))


def test_hazir_ve_ozel_muhur(pencere, tmp_path, app, monkeypatch):
    b = ac(pencere, app, pdf_yap(tmp_path / "h.pdf", 1))
    pencere._muhur_menusunu_doldur()
    adlar = [e.text() for e in pencere.m_muhur.actions() if e.text()]
    assert "ONAYLANDI" in adlar and "GİZLİ" in adlar and "Özel Mühür Oluştur…" in adlar
    pencere._hazir_muhur("ONAYLANDI", "#2e7d32")
    pencere.goruntuleyici.aracEylemi.emit("muhur", 0, ((300, 400), None))
    e = b.ek_listele()[0]
    assert e.metin == "ONAYLANDI" and abs((e.rect[2] - e.rect[0]) - 160) < 2
    monkeypatch.setattr(MuhurPenceresi, "exec", lambda self: (self.metin.setText("KABUL"), self._tamam(), 1)[2])
    pencere.ozel_muhur_olustur()
    kayitli = imzalar.listele(pencere.muhur_klasoru)
    assert len(kayitli) == 1 and muhur_adi(kayitli[0]) == "KABUL"
    assert pencere._bekleyen_ad == "KABUL" and pencere.goruntuleyici.arac == "muhur"
    pencere._muhur_menusunu_doldur()
    assert "KABUL" in [e.text() for e in pencere.m_muhur.actions()]
    pencere.goruntuleyici.aracEylemi.emit("muhur", 0, ((300, 600), (400, 640)))
    assert len(b.ek_listele()) == 2
    # bekleyen resim yokken yerleştirme uyarı verir
    pencere._bekleyen_png = None
    uyari = []
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: uyari.append(1))
    pencere.goruntuleyici.aracEylemi.emit("muhur", 0, ((10, 10), None))
    assert uyari and len(b.ek_listele()) == 2


def test_duzlestir_arayuzden(pencere, tmp_path, app, monkeypatch):
    b = ac(pencere, app, pdf_yap(tmp_path / "d.pdf", 1))
    pencere.goruntuleyici.aracEylemi.emit("elips", 0, ((100, 100), (200, 160)))
    assert len(b.ek_listele()) == 1
    dialog_yama(monkeypatch, DuzlestirPenceresi, lambda d: None)
    pencere.duzlestir_ac()
    assert pencere.belge.ek_listele() == [] and pencere.aciklama_paneli.agac.topLevelItemCount() == 0


def test_arac_cubuklari_gorunurlugu(pencere, tmp_path):
    assert pencere.ek_arac.isVisibleTo(pencere) and pencere.duzenleme_arac.isVisibleTo(pencere)
    pencere.e_duzenleme_arac.setChecked(False)
    pencere._arac_cubugu_ayarla("duzenleme_arac_goster", pencere.duzenleme_arac, pencere.e_duzenleme_arac)
    assert not pencere.duzenleme_arac.isVisibleTo(pencere)
    assert str(pencere.ayarlar.value("duzenleme_arac_goster")).lower() == "false"
    assert [m.title() for m in [a.menu() for a in pencere.menuBar().actions()]] == \
        ["&Dosya", "&Düzen", "&Görünüm", "&Açıklama", "Dü&zenle", "&Sayfa", "&Yardım"]


def test_filigran_kaldir_arayuzden(pencere, tmp_path, app, monkeypatch):
    b = ac(pencere, app, pdf_yap(tmp_path / "w.pdf", 3, "Merhaba dunya"))
    dialog_yama(monkeypatch, FiligranPenceresi, lambda d: (d.metin.setText("GİZLİ"), d.aralik.tumu.setChecked(True)))
    pencere.filigran_ac()
    assert pencere.belge.filigran_sayfalari() == [0, 1, 2]
    gosterilen = []
    orijinal_init = FiligranKaldirPenceresi.__init__

    def init(self, *a, **k):
        orijinal_init(self, *a, **k)
        gosterilen.append(a[3])
    monkeypatch.setattr(FiligranKaldirPenceresi, "__init__", init)
    dialog_yama(monkeypatch, FiligranKaldirPenceresi, lambda d: d.aralik.aralik_rb.setChecked(True) or d.aralik.aralik_kutu.setText("1-2"))
    pencere.filigran_kaldir_ac()
    assert gosterilen == [[0, 1, 2]] and pencere.belge.filigran_sayfalari() == [2]
    assert "2 filigran kaldırıldı" in pencere.statusBar().currentMessage()
    pencere.geri_al()
    assert pencere.belge.filigran_sayfalari() == [0, 1, 2]
    assert "Filigranı Kaldır…" in [e.text() for e in pencere.m_sayfa.actions()]
