import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import time
from pathlib import Path

import pytest
from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from eaglepdf.core import ocr
from eaglepdf.ui import ocr_arayuzu, theme
from eaglepdf.ui.pencere import AnaPencere
from eaglepdf.ui.resim_ocr_penceresi import ResimOcrPenceresi
from test_belge import pdf_yap
from test_resim_ocr import metin_resmi

pytestmark = pytest.mark.skipif(not ocr.hazir_mi("eng"), reason="İngilizce OCR dil verisi kurulu değil")


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


def bekle(kosul, saniye=30.0):
    bitis = time.time() + saniye
    while time.time() < bitis:
        QApplication.processEvents()
        if kosul():
            return True
        time.sleep(0.01)
    return kosul()


def resim(tmp_path, ad, metin):
    yol = tmp_path / ad
    metin_resmi(metin).save(yol)
    return str(yol)


def dialog(**kw):
    d = ResimOcrPenceresi(**kw)
    d.dil.setCurrentIndex(d.dil.findData("eng") if d.dil.findData("eng") >= 0 else 0)
    return d


def olaylari_bosalt(tur=8):
    """İş parçacığı bitmeden hemen önce gönderdiği sinyaller sıradaki olay turunda teslim edilir."""
    for _ in range(tur):
        QApplication.processEvents()
        time.sleep(0.01)


def oku_ve_bekle(d):
    d.oku()
    assert bekle(lambda: d.sonuc is not None or not d._calisiyor())
    olaylari_bosalt()   # `bekle` olayları işleyip SONRA koşulu kontrol eder: son sinyaller henüz teslim edilmemiş olabilir
    assert not d._calisiyor()


def mime(yollar):
    m = QMimeData()
    m.setUrls([QUrl.fromLocalFile(str(y)) for y in yollar])
    return m


# --- liste ve düğme durumları ---
def test_baslangic_durumu(app):
    d = dialog()
    assert d.yollar() == [] and not d.oku_dugme.isEnabled()
    assert not (d.kopyala_dugme.isEnabled() or d.txt_dugme.isEnabled() or d.pdf_dugme.isEnabled())   # sonuç yokken kapalı
    assert d.dil.findData("eng") >= 0 and d.dpi.currentData() == 300


def test_resim_ekle_suzer(app, tmp_path):
    d = dialog()
    a, b = resim(tmp_path, "a.png", "A"), resim(tmp_path, "b.jpg", "B")
    (tmp_path / "x.txt").write_text("x")
    assert d.resim_ekle([a, str(tmp_path / "x.txt"), b, a, str(tmp_path / "belge.pdf")]) == 2
    assert d.yollar() == [a, b] and d.oku_dugme.isEnabled()
    d.liste.setCurrentRow(0)
    d._kaldir()
    assert d.yollar() == [b]


def test_varsayilan_dil_secilir(app, tmp_path):
    d = ResimOcrPenceresi(varsayilan_dil="eng")
    assert d.dil.currentData() == "eng"


# --- OCR akışı ---
def test_tam_akis_metin_gorunur_dugmeler_acilir(app, tmp_path):
    d = dialog(yollar=[resim(tmp_path, "a.png", "Hello World report")])
    assert d.yollar() and d.oku_dugme.isEnabled()
    oku_ve_bekle(d)
    assert d.sonuc is not None and "Hello" in d.metin.toPlainText() and "World" in d.metin.toPlainText()
    assert "1 sayfa okundu" in d.durum.text()
    assert d.kopyala_dugme.isEnabled() and d.txt_dugme.isEnabled() and d.pdf_dugme.isEnabled() and d.oku_dugme.isEnabled()
    assert not d.cubuk.isVisibleTo(d) and not d.iptal_dugme.isVisibleTo(d)


def test_cok_sayfali_tiff_basliklarla(app, tmp_path):
    kareler = [metin_resmi(m) for m in ("First alpha", "Second bravo")]
    yol = tmp_path / "cok.tif"
    kareler[0].save(yol, save_all=True, append_images=kareler[1:])
    d = dialog(yollar=[str(yol)])
    oku_ve_bekle(d)
    t = d.metin.toPlainText()
    assert "— cok.tif (kare 1) —" in t and "— cok.tif (kare 2) —" in t and t.index("alpha") < t.index("bravo")
    assert "2 sayfa okundu" in d.durum.text()


def test_bozuk_resim_durumda_listelenir(app, tmp_path):
    (tmp_path / "bozuk.png").write_bytes(b"degil")
    d = dialog(yollar=[str(tmp_path / "bozuk.png"), resim(tmp_path, "iyi.png", "Good image ok")])
    oku_ve_bekle(d)
    assert "Good" in d.metin.toPlainText() and "okunamayanlar" in d.durum.text() and "bozuk.png" in d.durum.text()


def test_hicbiri_okunamazsa_hata_durumda_sonuc_yok(app, tmp_path):
    (tmp_path / "bozuk.png").write_bytes(b"degil")
    d = dialog(yollar=[str(tmp_path / "bozuk.png")])
    oku_ve_bekle(d)
    assert d.sonuc is None and "Okunabilir resim bulunamadı" in d.durum.text() and d.oku_dugme.isEnabled()
    assert not d.pdf_dugme.isEnabled()


def test_bos_resimde_aciklayici_mesaj(app, tmp_path):
    from PIL import Image
    Image.new("RGB", (800, 400), "white").save(tmp_path / "bos.png")
    d = dialog(yollar=[str(tmp_path / "bos.png")])
    oku_ve_bekle(d)
    assert d.sonuc is not None and "hiç metin bulunamadı" in d.durum.text()


def test_iptal(app, tmp_path):
    d = dialog(yollar=[resim(tmp_path, f"p{i}.png", f"Page number {i}") for i in range(6)])
    d.oku()
    assert bekle(lambda: d.cubuk.value() >= 1 or d.sonuc is not None)
    d._iptal_et()
    assert bekle(lambda: not d._calisiyor() and "iptal edildi" in d.durum.text())   # son durum iletisi sinyalle gelir
    olaylari_bosalt()   # `finished` (düğme durumu) bir tur sonra teslim edilir
    assert d.sonuc is None and d.oku_dugme.isEnabled() and not d.pdf_dugme.isEnabled()
    assert "Okunuyor" not in d.durum.text()


def test_pencere_kapanirken_calisan_ocr_durdurulur(app, tmp_path):
    d = dialog(yollar=[resim(tmp_path, f"p{i}.png", f"Page number {i}") for i in range(6)])
    d.oku()
    assert bekle(lambda: d._calisiyor())
    d.reject()
    assert not d._is.isRunning()


def test_calisirken_ikinci_oku_baslamaz(app, tmp_path):
    d = dialog(yollar=[resim(tmp_path, f"p{i}.png", f"Page {i}") for i in range(3)])
    d.oku()
    ilk = d._is
    d.oku()
    assert d._is is ilk
    d._iptal_et()
    bekle(lambda: not d._calisiyor())


# --- çıktılar ---
def test_kopyala_duzenlenmis_metni_alir(app, tmp_path):
    d = dialog(yollar=[resim(tmp_path, "a.png", "Hello World report")])
    oku_ve_bekle(d)
    d.metin.setPlainText("Düzeltilmiş İstanbul şğüöç metni")
    d.kopyala()
    assert QApplication.clipboard().text() == "Düzeltilmiş İstanbul şğüöç metni" and "panoya" in d.durum.text()


def test_txt_kaydet_turkce_bomlu_utf8(app, tmp_path):
    d = dialog(yollar=[resim(tmp_path, "a.png", "Hello World report")])
    oku_ve_bekle(d)
    d.metin.setPlainText("Işık İstanbul şğüöç")
    hedef = tmp_path / "cikti.txt"
    d._txt_yaz(hedef)
    assert hedef.read_text(encoding="utf-8-sig") == "Işık İstanbul şğüöç" and hedef.read_bytes()[:3] == b"\xef\xbb\xbf"
    assert not [p for p in tmp_path.iterdir() if p.suffix == ".tmp"]


def test_txt_kaydet_dugmesi_dosya_penceresini_kullanir(app, tmp_path, monkeypatch):
    d = dialog(yollar=[resim(tmp_path, "a.png", "Hello World report")])
    oku_ve_bekle(d)
    hedef = tmp_path / "secilen"   # uzantısız: .txt eklenmeli
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(hedef), "")))
    d.txt_kaydet()
    assert (tmp_path / "secilen.txt").is_file()


def test_pdf_kaydet_aranabilir_ve_sinyal(app, tmp_path):
    from eaglepdf.core.belge import Belge
    d = dialog(yollar=[resim(tmp_path, "a.png", "Searchable output check")])
    oku_ve_bekle(d)
    kaydedilen = []
    d.pdfKaydedildi.connect(kaydedilen.append)
    hedef = tmp_path / "o.pdf"
    d._pdf_yaz(hedef)
    assert kaydedilen == [str(hedef)] and "kaydedildi" in d.durum.text()
    b = Belge.ac(hedef)
    try:
        assert b.sayfa_sayisi == 1 and b.ara("searchable")
    finally:
        b.kapat()


def test_pdf_engel_acik_dosyaya_yazmaz(app, tmp_path):
    d = dialog(yollar=[resim(tmp_path, "a.png", "Hello World report")], engel_fn=lambda yol: True)
    oku_ve_bekle(d)
    kaydedilen = []
    d.pdfKaydedildi.connect(kaydedilen.append)
    d._pdf_yaz(tmp_path / "engelli.pdf")
    assert not (tmp_path / "engelli.pdf").exists() and kaydedilen == []


def test_pdf_kaydet_dugmesi_uzantiyi_tamamlar(app, tmp_path, monkeypatch):
    d = dialog(yollar=[resim(tmp_path, "a.png", "Hello World report")])
    oku_ve_bekle(d)
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(tmp_path / "adsiz"), "")))
    d.pdf_kaydet()
    assert (tmp_path / "adsiz.pdf").is_file()


# --- sürükle-bırak (pencere içi) ---
def test_dialoga_birakilan_resimler_eklenir(app, tmp_path):
    d = dialog()
    a, b = resim(tmp_path, "a.png", "A"), resim(tmp_path, "b.tif", "B")
    (tmp_path / "x.pdf").write_bytes(b"%PDF")
    veri = mime([a, tmp_path / "x.pdf", b])   # olay yalnızca işaretçi tutar: Python nesnesi canlı kalmalı
    d.dropEvent(QDropEvent(QPointF(5, 5), Qt.CopyAction, veri, Qt.LeftButton, Qt.NoModifier))
    assert d.yollar() == [os.path.normpath(a), os.path.normpath(b)]   # Qt'nin düz eğik çizgili yolları tek biçime iner
    kabul_veri, ret_veri = mime([a]), mime([tmp_path / "x.pdf"])
    kabul = QDragEnterEvent(QPoint(5, 5), Qt.CopyAction, kabul_veri, Qt.LeftButton, Qt.NoModifier)
    d.dragEnterEvent(kabul)
    assert kabul.isAccepted()
    ret = QDragEnterEvent(QPoint(5, 5), Qt.CopyAction, ret_veri, Qt.LeftButton, Qt.NoModifier)
    ret.ignore()
    d.dragEnterEvent(ret)
    assert not ret.isAccepted()


# --- ana pencere entegrasyonu ---
def test_menu_belge_olmadan_kullanilabilir(pencere):
    assert "Resimden Metin Çıkar…" in [a.text() for a in pencere.m_ocr.actions()]
    assert pencere.e_resim_ocr.isEnabled() and not pencere.e_aranabilir.isEnabled()


def test_ana_pencere_dialogu_dil_ve_resimlerle_acar(pencere, tmp_path, monkeypatch):
    pencere.ayarlar.setValue("ocr_dil", "eng")
    gorulen = {}

    def sahte_exec(self_):
        gorulen.update(yollar=self_.yollar(), dil=self_.dil.currentData(), engel=self_.engel_fn is not None)
    monkeypatch.setattr(ocr_arayuzu_pencere(), "exec", sahte_exec)
    a = resim(tmp_path, "a.png", "A")
    pencere.resim_ocr_ac([a])
    assert gorulen == {"yollar": [a], "dil": "eng", "engel": True}


def ocr_arayuzu_pencere():
    return ResimOcrPenceresi


def test_dil_verisi_yoksa_dialog_acilmaz(pencere, monkeypatch):
    monkeypatch.setattr(ocr_arayuzu, "dil_secenekleri", lambda: [])
    acilan = []
    monkeypatch.setattr(ResimOcrPenceresi, "exec", lambda self_: acilan.append(1))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.No))
    pencere.resim_ocr_ac()
    assert acilan == []


def test_birakma_pdf_sekmede_resim_dialogda(pencere, tmp_path, monkeypatch):
    pdf = str(pdf_yap(tmp_path / "belge.pdf", 1))
    a, b = resim(tmp_path, "a.png", "A"), resim(tmp_path, "b.jpg", "B")
    (tmp_path / "x.txt").write_text("x")
    cagrilar = []
    monkeypatch.setattr(pencere, "resim_ocr_ac", lambda yollar=None: cagrilar.append(yollar))
    veri = mime([pdf, a, tmp_path / "x.txt", b])
    pencere.dropEvent(QDropEvent(QPointF(5, 5), Qt.CopyAction, veri, Qt.LeftButton, Qt.NoModifier))
    assert [o.belge.yol.name for o in pencere._oturumlar] == ["belge.pdf"]
    assert cagrilar == [[os.path.normpath(a), os.path.normpath(b)]]


def test_birakma_yalniz_resim_pdf_acmaz(pencere, tmp_path, monkeypatch):
    a = resim(tmp_path, "a.png", "A")
    cagrilar = []
    monkeypatch.setattr(pencere, "resim_ocr_ac", lambda yollar=None: cagrilar.append(yollar))
    veri = mime([a])
    pencere.dropEvent(QDropEvent(QPointF(5, 5), Qt.CopyAction, veri, Qt.LeftButton, Qt.NoModifier))
    assert pencere._oturumlar == [] and cagrilar == [[os.path.normpath(a)]]


def test_surukleme_girisi_resim_ve_pdf_kabul_digeri_ret(pencere, tmp_path):
    a = resim(tmp_path, "a.png", "A")
    (tmp_path / "x.txt").write_text("x")
    v1, v2 = mime([a]), mime([tmp_path / "x.txt"])
    e1 = QDragEnterEvent(QPoint(5, 5), Qt.CopyAction, v1, Qt.LeftButton, Qt.NoModifier)
    pencere.dragEnterEvent(e1)
    assert e1.isAccepted()
    e2 = QDragEnterEvent(QPoint(5, 5), Qt.CopyAction, v2, Qt.LeftButton, Qt.NoModifier)
    e2.ignore()
    pencere.dragEnterEvent(e2)
    assert not e2.isAccepted()


def test_kaydedilen_pdf_sekmede_acilir(pencere, tmp_path, monkeypatch):
    """Dialogda aranabilir PDF kaydedilince ana pencere 'şimdi açılsın mı?' sorar; Evet → yeni sekme."""
    from eaglepdf.core.resim_ocr import ResimOcrSonucu, SayfaMetni
    hedef = tmp_path / "sonuc.pdf"
    pdf_bayt = Path(pdf_yap(tmp_path / "kaynak.pdf", 1)).read_bytes()

    def sahte_exec(self_):
        self_.sonuc = ResimOcrSonucu([SayfaMetni("a.png", 0, "x")], pdf_bayt)
        self_._pdf_yaz(hedef)
    monkeypatch.setattr(ResimOcrPenceresi, "exec", sahte_exec)
    sorular = []
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: sorular.append(a[2]) or QMessageBox.Yes))
    pencere.resim_ocr_ac([])
    assert sorular and "Aranabilir PDF kaydedildi" in sorular[0]
    assert [o.belge.yol.name for o in pencere._oturumlar] == ["sonuc.pdf"]


def test_kaydedilen_pdf_acik_sekmenin_dosyasini_ezmez(pencere, tmp_path, monkeypatch):
    from eaglepdf.core.resim_ocr import ResimOcrSonucu, SayfaMetni
    acik = str(pdf_yap(tmp_path / "acik.pdf", 1))
    pencere.ac(acik)
    once = Path(acik).read_bytes()

    def sahte_exec(self_):
        self_.sonuc = ResimOcrSonucu([SayfaMetni("a.png", 0, "x")], b"%PDF-yeni")
        self_._pdf_yaz(Path(acik))
    monkeypatch.setattr(ResimOcrPenceresi, "exec", sahte_exec)
    uyari = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: uyari.append(a[2])))
    pencere.resim_ocr_ac([])
    assert uyari and "acik.pdf" in uyari[0] and Path(acik).read_bytes() == once
