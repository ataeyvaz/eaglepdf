import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from types import SimpleNamespace

import pytest
from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from eaglepdf.ui import pencere as pencere_modulu
from eaglepdf.ui import theme
from eaglepdf.ui.oturum import EN_COK_SEKME, komut_satiri_yollari
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


def yollar_yap(tmp_path, n, sayfa=2):
    return [str(pdf_yap(tmp_path / f"d{i}.pdf", sayfa)) for i in range(n)]


def adlar(p):
    return [o.belge.yol.name for o in p._oturumlar]


def uyarilari_yakala(monkeypatch):
    kayit = {"warning": [], "information": []}
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: kayit["warning"].append(a[2])))
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: kayit["information"].append(a[2])))
    return kayit


def mime(yollar):
    m = QMimeData()
    m.setUrls([QUrl.fromLocalFile(str(y)) for y in yollar])
    return m


# --- komut satırı ---
def test_komut_satiri_yollari():
    assert komut_satiri_yollari(["main.py"]) == []
    assert komut_satiri_yollari(["main.py", "a.pdf", "", "--x", "b.pdf", "a.pdf", '"c d.pdf"']) == ["a.pdf", "b.pdf", "c d.pdf"]


# --- ac_coklu ---
def test_ac_coklu_hepsi_sekme_son_etkin(pencere, tmp_path):
    y = yollar_yap(tmp_path, 3)
    assert pencere.ac_coklu(y) == 3
    assert adlar(pencere) == ["d0.pdf", "d1.pdf", "d2.pdf"] and pencere._etkin == 2


def test_ac_coklu_yineleme_ve_acik_dosya_cogaltilmaz(pencere, tmp_path):
    y = yollar_yap(tmp_path, 2)
    pencere.ac(y[0])
    assert pencere.ac_coklu([y[0], y[1], y[1]]) == 3   # açık olana geçmek de 'işlendi' sayılır
    assert adlar(pencere) == ["d0.pdf", "d1.pdf"]


def test_ac_coklu_bozuk_dosya_digerlerini_durdurmaz(pencere, tmp_path, monkeypatch):
    kayit = uyarilari_yakala(monkeypatch)
    iyi = yollar_yap(tmp_path, 2)
    (tmp_path / "bozuk.pdf").write_bytes(b"degil")
    sayi = pencere.ac_coklu([iyi[0], str(tmp_path / "bozuk.pdf"), str(tmp_path / "yok.pdf"), iyi[1]])
    assert sayi == 2 and adlar(pencere) == ["d0.pdf", "d1.pdf"] and len(kayit["warning"]) == 2


def test_ac_coklu_sinir_tek_uyari(pencere, tmp_path, monkeypatch):
    kayit = uyarilari_yakala(monkeypatch)
    y = yollar_yap(tmp_path, EN_COK_SEKME + 3, sayfa=1)
    assert pencere.ac_coklu(y) == EN_COK_SEKME
    assert len(pencere._oturumlar) == EN_COK_SEKME
    assert len(kayit["information"]) == 1 and "3 dosya" in kayit["information"][0]   # tek mesaj, atlanan sayısı


def test_ac_coklu_sinirdayken_acik_dosyaya_gecilir(pencere, tmp_path, monkeypatch):
    kayit = uyarilari_yakala(monkeypatch)
    y = yollar_yap(tmp_path, EN_COK_SEKME, sayfa=1)
    pencere.ac_coklu(y)
    assert pencere.ac_coklu([y[0]]) == 1 and pencere._etkin == 0 and kayit["information"] == []


def test_ac_sor_coklu(pencere, tmp_path, monkeypatch):
    y = yollar_yap(tmp_path, 3, sayfa=1)
    monkeypatch.setattr(QFileDialog, "getOpenFileNames", staticmethod(lambda *a, **k: (y, "")))
    pencere.ac_sor()
    assert len(pencere._oturumlar) == 3


# --- sürükle-bırak ---
def test_birak_birden_cok_pdf_ac_digerlerini_yok_sayar(pencere, tmp_path):
    y = yollar_yap(tmp_path, 3, sayfa=1)
    (tmp_path / "not.txt").write_text("x")
    veri = mime([y[0], tmp_path / "not.txt", y[1], y[2]])   # olay yalnızca işaretçi tutar: Python nesnesi canlı kalmalı
    olay = QDropEvent(QPointF(5, 5), Qt.CopyAction, veri, Qt.LeftButton, Qt.NoModifier)
    pencere.dropEvent(olay)
    assert adlar(pencere) == ["d0.pdf", "d1.pdf", "d2.pdf"] and olay.isAccepted()


def test_surukleme_girisi_yalniz_pdf_varsa_kabul(pencere, tmp_path):
    y = yollar_yap(tmp_path, 1, sayfa=1)
    (tmp_path / "x.txt").write_text("x")
    veri1, veri2 = mime([tmp_path / "x.txt", y[0]]), mime([tmp_path / "x.txt"])
    kabul = QDragEnterEvent(QPoint(5, 5), Qt.CopyAction, veri1, Qt.LeftButton, Qt.NoModifier)
    pencere.dragEnterEvent(kabul)
    assert kabul.isAccepted()
    ret = QDragEnterEvent(QPoint(5, 5), Qt.CopyAction, veri2, Qt.LeftButton, Qt.NoModifier)
    ret.ignore()
    pencere.dragEnterEvent(ret)
    assert not ret.isAccepted()


# --- dönüştürme çıktıları ---
def test_donusum_sonrasi_tum_pdf_ciktilari_sekmede(pencere, tmp_path, monkeypatch):
    y = yollar_yap(tmp_path, 3, sayfa=1)
    d = SimpleNamespace(acilacak=y + [str(tmp_path / "cikti.docx")], tur=SimpleNamespace(cikti_pdf=True))
    pencere._donusum_sonrasi(d)
    assert adlar(pencere) == ["d0.pdf", "d1.pdf", "d2.pdf"]


def test_donusum_sonrasi_pdf_olmayan_cikti_klasoru_acar(pencere, tmp_path, monkeypatch):
    acilan = []
    from eaglepdf.ui import donusum_arayuzu
    monkeypatch.setattr(donusum_arayuzu.QDesktopServices, "openUrl", staticmethod(lambda u: acilan.append(u.toLocalFile())))
    d = SimpleNamespace(acilacak=[str(tmp_path / "cikti.docx")], tur=SimpleNamespace(cikti_pdf=False))
    pencere._donusum_sonrasi(d)
    from pathlib import Path
    assert [Path(a) for a in acilan] == [tmp_path] and pencere._oturumlar == []


# --- açık dosyanın üzerine yazma engeli ---
def test_farkli_kaydet_baska_sekmede_acik_dosyaya_yazmaz(pencere, tmp_path, monkeypatch):
    kayit = uyarilari_yakala(monkeypatch)
    y = yollar_yap(tmp_path, 2)
    pencere.ac_coklu(y)
    once = (tmp_path / "d1.pdf").read_bytes()
    pencere.sekmeler.setCurrentIndex(0)
    pencere.belge.ozellikleri_ata(baslik="degisti")
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (y[1], "")))
    assert pencere.farkli_kaydet() is False
    assert kayit["warning"] and "d1.pdf" in kayit["warning"][0] and "açık" in kayit["warning"][0]
    assert (tmp_path / "d1.pdf").read_bytes() == once and pencere.belge.degisti


def test_farkli_kaydet_kendi_yoluna_hala_calisir(pencere, tmp_path, monkeypatch):
    y = yollar_yap(tmp_path, 1)
    pencere.ac(y[0])
    pencere.belge.ozellikleri_ata(baslik="yeni")
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (y[0], "")))
    assert pencere.farkli_kaydet() is True and not pencere.belge.degisti


def test_cikar_acik_dosyaya_yazmaz_ve_sonra_acmayi_sorar(pencere, tmp_path, monkeypatch):
    kayit = uyarilari_yakala(monkeypatch)
    y = yollar_yap(tmp_path, 2, sayfa=3)
    pencere.ac_coklu(y)
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (y[0], "")))
    pencere.sayfalari_cikar()
    assert kayit["warning"] and len(pencere._oturumlar) == 2
    hedef = str(tmp_path / "cikarilan.pdf")
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (hedef, "")))
    sorular = []
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: sorular.append(a[2]) or QMessageBox.Yes))
    pencere.sayfalari_cikar()
    assert sorular and "çıkarıldı" in sorular[0] and "Dosyayı şimdi açmak" in sorular[0]
    assert adlar(pencere)[-1] == "cikarilan.pdf" and len(pencere._oturumlar) == 3


def test_birlestir_sonucu_sekmede_acilir_hayirda_acilmaz(pencere, tmp_path, monkeypatch):
    kayit = uyarilari_yakala(monkeypatch)
    y = yollar_yap(tmp_path, 2, sayfa=2)
    pencere.ac(y[0])
    monkeypatch.setattr(pencere_modulu.BirlestirPenceresi, "exec", lambda self: True)
    monkeypatch.setattr(pencere_modulu.BirlestirPenceresi, "yollar", lambda self: y)
    # açık dosyanın üzerine birleştirme engellenir
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (y[0], "")))
    pencere.birlestir()
    assert kayit["warning"] and len(pencere._oturumlar) == 1
    hedef = str(tmp_path / "birlesik.pdf")
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (hedef, "")))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.No))
    pencere.birlestir()
    assert (tmp_path / "birlesik.pdf").is_file() and len(pencere._oturumlar) == 1
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes))
    (tmp_path / "birlesik.pdf").unlink()
    pencere.birlestir()
    assert adlar(pencere)[-1] == "birlesik.pdf" and pencere.belge.sayfa_sayisi == 4
