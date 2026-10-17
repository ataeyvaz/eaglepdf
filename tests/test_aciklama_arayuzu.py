import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import time

import pymupdf
import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLineEdit

from eaglepdf.core import imzalar
from eaglepdf.core.belge import Belge, BelgeHatasi
from eaglepdf.ui import dialoglar, theme
from eaglepdf.ui.dialoglar import BaglantiPenceresi, ImzaPenceresi, MetinPenceresi, icerige_kirp
from eaglepdf.ui.pencere import AnaPencere
from test_belge import pdf_yap
from test_ekaciklama import form_pdf, koyu_piksel


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


def metin_penceresini_otomatiklestir(monkeypatch, metin="Deneme ışık"):
    def exec_(self):
        self.kutu.setPlainText(metin)
        return 1
    monkeypatch.setattr(MetinPenceresi, "exec", exec_)


def test_isaretleme_ve_geri_al(pencere, tmp_path, app):
    b = ac(pencere, app, pdf_yap(tmp_path / "a.pdf", 2, "Merhaba dunya"))
    g = pencere.goruntuleyici
    pencere._arac_eylemleri["vurgu"].setChecked(True)
    pencere._arac_uygula()
    assert g.arac == "vurgu" and not pencere.e_geri.isEnabled()
    satirlar = {0: [(72, 90, 150, 105)]}
    g.aracEylemi.emit("vurgu", -1, satirlar)
    assert [e.etiket for e in b.ek_listele()] == ["Vurgu"]
    assert pencere.aciklama_paneli.agac.topLevelItemCount() == 1
    assert pencere.e_geri.isEnabled() and not pencere.e_yinele.isEnabled()
    pencere.geri_al()
    assert b.ek_listele() == [] and pencere.aciklama_paneli.agac.topLevelItemCount() == 0
    assert pencere.e_yinele.isEnabled()
    pencere.yinele()
    assert len(pencere.belge.ek_listele()) == 1


def test_cizim_sekil_not_metin(pencere, tmp_path, app, monkeypatch):
    b = ac(pencere, app, pdf_yap(tmp_path / "b.pdf", 1))
    g = pencere.goruntuleyici
    g.aracEylemi.emit("ciz", 0, [[(100, 200), (150, 230), (200, 200)]])
    g.aracEylemi.emit("ok", 0, ((100, 300), (250, 330)))
    g.aracEylemi.emit("dikdortgen", 0, ((300, 300), (400, 360)))
    metin_penceresini_otomatiklestir(monkeypatch, "Not: ışık")
    g.aracEylemi.emit("not", 0, (400, 100))
    g.aracEylemi.emit("metin", 0, ((100, 500), (300, 540)))
    g.aracEylemi.emit("metin", 0, ((100, 600), None))  # tıklama: varsayılan boyut
    etiketler = [e.etiket for e in pencere.belge.ek_listele()]
    assert etiketler == ["Çizim", "Çizgi / ok", "Dikdörtgen", "Not", "Metin kutusu", "Metin kutusu"]
    assert pencere.belge.ek_listele()[3].metin == "Not: ışık"
    pencere.aciklama_paneli.tur_kutu.setCurrentIndex(pencere.aciklama_paneli.tur_kutu.findText("Metin kutusu"))
    assert pencere.aciklama_paneli.agac.topLevelItemCount() == 2


def test_sec_tasi_sil(pencere, tmp_path, app):
    b = ac(pencere, app, pdf_yap(tmp_path / "c.pdf", 3))
    g = pencere.goruntuleyici
    g.aracEylemi.emit("dikdortgen", 0, ((100, 100), (200, 160)))
    pencere._arac_eylemleri["duzenle"].setChecked(True)
    pencere._arac_uygula()
    etiket = g._etiketler[0]
    o = g.olcek
    QTest.mouseClick(etiket, Qt.LeftButton, pos=QPoint(round(150 * o), round(130 * o)))
    assert g.secili_ek is not None and g.secili_ek.etiket == "Dikdörtgen"
    once = g.secili_ek.rect
    g.aracEylemi.emit("tasi", 0, (g.secili_ek.xref, 30, 10))
    assert abs(g.secili_ek.rect[0] - once[0] - 30) <= 2
    sayfa_sayisi = b.sayfa_sayisi
    pencere.sayfalari_sil()  # Del: seçili açıklama silinir, sayfa değil
    assert b.sayfa_sayisi == sayfa_sayisi and b.ek_listele() == [] and g.secili_ek is None


def test_renk_degistir_secili(pencere, tmp_path, app):
    b = ac(pencere, app, pdf_yap(tmp_path / "r.pdf", 1))
    g = pencere.goruntuleyici
    g.aracEylemi.emit("elips", 0, ((100, 100), (200, 160)))
    pencere._arac_eylemleri["duzenle"].setChecked(True)
    pencere._arac_uygula()
    QTest.mouseClick(g._etiketler[0], Qt.LeftButton, pos=QPoint(round(150 * g.olcek), round(130 * g.olcek)))
    pencere._renk_sec("#1565c0")
    assert b.ek_listele()[0].renk == "#1565c0"


def test_ek_metnini_duzenle(pencere, tmp_path, app, monkeypatch):
    b = ac(pencere, app, pdf_yap(tmp_path / "d.pdf", 1))
    g = pencere.goruntuleyici
    metin_penceresini_otomatiklestir(monkeypatch, "ilk metin")
    g.aracEylemi.emit("metin", 0, ((100, 100), (300, 140)))
    metin_penceresini_otomatiklestir(monkeypatch, "değişen ŞĞİ")
    g.aracEylemi.emit("ek_duzenle", 0, b.ek_listele()[0])
    assert b.ek_listele()[0].metin == "değişen ŞĞİ"


def test_baglanti(pencere, tmp_path, app, monkeypatch):
    b = ac(pencere, app, pdf_yap(tmp_path / "l.pdf", 3))
    g = pencere.goruntuleyici
    monkeypatch.setattr(BaglantiPenceresi, "exec", lambda self: (self.adres.setText("example.com"), 1)[1])
    g.aracEylemi.emit("baglanti", 0, ((50, 50), (150, 70)))
    assert b.baglantilar(0)[0]["uri"] == "https://example.com"
    def sayfa_baglantisi(self):
        self.sayfa.setChecked(True)
        self.sayfa_no.setValue(3)
        return 1
    monkeypatch.setattr(BaglantiPenceresi, "exec", sayfa_baglantisi)
    g.aracEylemi.emit("baglanti", 0, ((50, 100), (150, 120)))
    assert [x["tur"] for x in b.baglantilar(0)] == ["uri", "sayfa"]
    # bağlantıya tıklayınca hedef sayfaya gidilir (el aracı)
    gidilen = []
    g.sayfaDegisti.connect(gidilen.append)
    QTest.mouseClick(g._etiketler[0], Qt.LeftButton, pos=QPoint(round(100 * g.olcek), round(110 * g.olcek)))
    assert gidilen and gidilen[-1] == 2


def test_imza_yerlestir(pencere, tmp_path, app):
    b = ac(pencere, app, pdf_yap(tmp_path / "i.pdf", 1))
    img = QImage(60, 30, QImage.Format_ARGB32)
    img.fill(0xFFCC0000)
    png = dialoglar.png_baytlari(img)
    yol = imzalar.kaydet(pencere.imza_klasoru, png, "Ata")
    pencere._imza_kullan(yol)
    g = pencere.goruntuleyici
    assert g.arac == "imza"
    g.aracEylemi.emit("imza", 0, ((300, 400), None))
    assert koyu_piksel(b, 0, (230, 380, 380, 420)) > 1000
    g.aracEylemi.emit("imza", 0, ((10, 10), (20, 15)))  # küçük kutu da olur
    assert b.geri_alinabilir_mi
    # sayfa dışına taşan tıklama sayfaya kaydırılır
    g.aracEylemi.emit("imza", 0, ((2, 2), None))
    pencere.geri_al()
    pencere.geri_al()
    pencere.geri_al()
    assert koyu_piksel(b, 0, (230, 380, 380, 420)) == 0


def test_form_doldurma(pencere, tmp_path, app):
    b = ac(pencere, app, form_pdf(tmp_path / "f.pdf"))
    g = pencere.goruntuleyici
    bekle(app)
    kutular = g._etiketler[0].form_widgetlari
    assert len(kutular) == 3
    metin = [w for w in kutular if isinstance(w, QLineEdit)][0]
    metin.setText("Işık Şahin")
    metin.editingFinished.emit()
    bekle(app)
    assert {a.ad: a.deger for a in b.form_alanlari()}["ad"] == "Işık Şahin"
    # görünüm yeniden kurulur; geri al
    pencere.geri_al()
    bekle(app)
    assert {a.ad: a.deger for a in pencere.belge.form_alanlari()}["ad"] == ""
    pencere.e_form.setChecked(False)
    pencere._form_uygula()
    assert g._etiketler[0].form_widgetlari == []


def test_yer_imleri_paneli(pencere, tmp_path, app):
    b = ac(pencere, app, pdf_yap(tmp_path / "y.pdf", 3))
    pencere._yer_imleri_degisti([(1, "Giriş", 0), (2, "Ayrıntı", 1)])
    assert b.icindekiler() == [(1, "Giriş", 0), (2, "Ayrıntı", 1)]
    pencere.geri_al()
    assert pencere.belge.icindekiler() == []
    # panel ağacından liste üretimi
    pencere.yer_imleri.agac.clear()
    from PySide6.QtWidgets import QTreeWidgetItem
    ust = QTreeWidgetItem(["Bölüm"])
    ust.setData(0, Qt.UserRole, 0)
    alt = QTreeWidgetItem(["Alt"])
    alt.setData(0, Qt.UserRole, 2)
    ust.addChild(alt)
    pencere.yer_imleri.agac.addTopLevelItem(ust)
    assert pencere.yer_imleri.liste() == [(1, "Bölüm", 0), (2, "Alt", 2)]
    pencere.yer_imleri.agac.setCurrentItem(alt)
    pencere.yer_imleri._cikar()
    assert pencere.yer_imleri.liste() == [(1, "Bölüm", 0), (1, "Alt", 2)]
    pencere.yer_imleri._gir()
    assert pencere.yer_imleri.liste() == [(1, "Bölüm", 0), (2, "Alt", 2)]


def test_panelden_toplu_sil(pencere, tmp_path, app, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Yes)
    b = ac(pencere, app, pdf_yap(tmp_path / "t.pdf", 2))
    g = pencere.goruntuleyici
    for s in (0, 1):
        g.aracEylemi.emit("elips", s, ((100, 100), (200, 160)))
        g.aracEylemi.emit("cizgi", s, ((100, 300), (200, 360)))
    assert len(b.ek_listele()) == 4
    pencere.aciklama_paneli.agac.selectAll()
    pencere.aciklama_paneli._sil()
    assert b.ek_listele() == []


def test_kaydet_gidis_donus_arayuzden(pencere, tmp_path, app, monkeypatch):
    b = ac(pencere, app, pdf_yap(tmp_path / "k.pdf", 1))
    metin_penceresini_otomatiklestir(monkeypatch, "Kalıcı")
    pencere.goruntuleyici.aracEylemi.emit("metin", 0, ((100, 100), (300, 140)))
    pencere.goruntuleyici.aracEylemi.emit("ok", 0, ((100, 300), (250, 330)))
    hedef = tmp_path / "k2.pdf"
    b.kaydet(hedef)
    c = Belge.ac(hedef)
    assert [e.etiket for e in c.ek_listele()] == ["Metin kutusu", "Çizgi / ok"]


def test_imza_penceresi_yaz_ve_ciz(app, monkeypatch):
    d = ImzaPenceresi()
    d.sekmeler.setCurrentIndex(1)
    d.ad_kutu.setText("Ata Eyvaz")
    d._tamam()
    assert d.png() and d.png().startswith(imzalar.PNG_IMZASI)
    d2 = ImzaPenceresi()
    d2._tamam()
    assert d2.png() is None and "çizin" in d2.hata.text()
    from PySide6.QtCore import QPointF
    d2.tuval._cizgiler = [[QPointF(10, 10), QPointF(60, 40), QPointF(120, 20)]]
    d2.tuval._renkler = ["#111111"]
    d2._tamam()
    img = QImage.fromData(d2.png())
    assert not img.isNull() and img.width() > 100 and (img.pixel(img.width() // 2, img.height() // 2) >> 24) >= 0


def test_icerige_kirp():
    img = QImage(100, 80, QImage.Format_ARGB32)
    img.fill(0)
    for x in range(40, 60):
        for y in range(30, 50):
            img.setPixel(x, y, 0xFF000000)
    k = icerige_kirp(img, pay=2)
    assert (k.width(), k.height()) == (24, 24)


def test_imzalar_deposu(tmp_path):
    img = QImage(10, 10, QImage.Format_ARGB32)
    img.fill(0xFF000000)
    png = dialoglar.png_baytlari(img)
    k = tmp_path / "imzalar"
    y1 = imzalar.kaydet(k, png, "Ata / Eyvaz?")
    y2 = imzalar.kaydet(k, png, "Ata / Eyvaz?")
    assert y1 != y2 and imzalar.listele(k) == sorted([y1, y2])
    assert imzalar.oku(y1) == png
    imzalar.sil(y1)
    assert imzalar.listele(k) == [y2]
    imzalar.sil(y1)  # olmayanı silmek hata vermez
    with pytest.raises(BelgeHatasi):
        imzalar.kaydet(k, b"png degil")
    with pytest.raises(BelgeHatasi):
        imzalar.kaydet(k, imzalar.PNG_IMZASI + b"x" * (6 * 1024 * 1024))
    assert imzalar.listele(tmp_path / "yok") == []


def test_ok_secilir_ve_tasininca_secim_yeni_nesnede_kalir(pencere, tmp_path, app):
    b = ac(pencere, app, pdf_yap(tmp_path / "ok.pdf", 1))
    g = pencere.goruntuleyici
    g.aracEylemi.emit("ok", 0, ((100, 300), (200, 300)))
    pencere._arac_eylemleri["duzenle"].setChecked(True)
    pencere._arac_uygula()
    QTest.mouseClick(g._etiketler[0], Qt.LeftButton, pos=QPoint(round(150 * g.olcek), round(300 * g.olcek)))
    assert g.secili_ek is not None and g.secili_ek.etiket == "Çizgi / ok"
    once = g.secili_ek.rect
    g.aracEylemi.emit("tasi", 0, (g.secili_ek.xref, 40, 25))       # xref değişir (yeniden oluşturulur)
    assert g.secili_ek is not None and g.secili_ek.etiket == "Çizgi / ok"
    assert abs(g.secili_ek.rect[0] - once[0] - 40) <= 3 and abs(g.secili_ek.rect[1] - once[1] - 25) <= 3
    assert len(b.ek_listele()) == 1
    pencere.geri_al()
    assert abs(b.ek_listele()[0].rect[0] - once[0]) <= 3
