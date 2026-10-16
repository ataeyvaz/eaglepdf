import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pymupdf
import pytest
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import QApplication, QMessageBox

from eaglepdf.core import koruma
from eaglepdf.core.belge import Belge
from eaglepdf.ui import theme
from eaglepdf.ui.pencere import AnaPencere
from eaglepdf.ui.toplu_yazdir import TopluYazdirPenceresi, toplu_yazdir
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


def pdf_yazici():
    y = QPrinter(QPrinter.HighResolution)
    y.setOutputFormat(QPrinter.PdfFormat)
    return y


def cikti_ayarla(klasor):
    """Her dosya için ayrı PDF çıktı adı (yazıcı 'PDF'e yazdır')."""
    adlar = []

    def hook(yazici, yol):
        hedef = klasor / f"cikti_{len(adlar)}.pdf"
        yazici.setOutputFileName(str(hedef))
        adlar.append(hedef)
    return hook, adlar


def sayfa_say(yol):
    d = pymupdf.open(yol)
    n = d.page_count
    d.close()
    return n


def test_tum_dosyalar_yazilir(app, tmp_path):
    a, b = pdf_yap(tmp_path / "a.pdf", 2), pdf_yap(tmp_path / "b.pdf", 3)
    hook, adlar = cikti_ayarla(tmp_path)
    sonuc = toplu_yazdir([str(a), str(b)], pdf_yazici(), her_dosya_icin=hook)
    assert [s.sayfa for s in sonuc] == [2, 3] and all(s.tamam for s in sonuc)
    assert [sayfa_say(x) for x in adlar] == [2, 3]


def test_aralik_her_dosyaya_uygulanir_ve_tasanlar_sinirlanir(app, tmp_path):
    a, b = pdf_yap(tmp_path / "a.pdf", 5), pdf_yap(tmp_path / "b.pdf", 2)
    hook, adlar = cikti_ayarla(tmp_path)
    sonuc = toplu_yazdir([str(a), str(b)], pdf_yazici(), "2-4", her_dosya_icin=hook)
    assert sonuc[0].sayfa == 3
    assert sonuc[1].sayfa == 1  # 2 sayfalık dosyada yalnızca 2. sayfa
    assert sonuc[0].tamam and sonuc[1].tamam


def test_aralik_dosyada_yoksa_hata_digerleri_devam(app, tmp_path):
    kisa, uzun = pdf_yap(tmp_path / "k.pdf", 1), pdf_yap(tmp_path / "u.pdf", 4)
    hook, _ = cikti_ayarla(tmp_path)
    sonuc = toplu_yazdir([str(kisa), str(uzun)], pdf_yazici(), "3-4", her_dosya_icin=hook)
    assert not sonuc[0].tamam and "aralığı" in sonuc[0].hata
    assert sonuc[1].tamam and sonuc[1].sayfa == 2


def test_bozuk_ve_eksik_dosya_digerlerini_durdurmaz(app, tmp_path):
    bozuk = tmp_path / "bozuk.pdf"
    bozuk.write_bytes(b"pdf degil")
    iyi = pdf_yap(tmp_path / "i.pdf", 1)
    hook, _ = cikti_ayarla(tmp_path)
    sonuc = toplu_yazdir([str(bozuk), str(tmp_path / "yok.pdf"), str(iyi)], pdf_yazici(), her_dosya_icin=hook)
    assert [s.tamam for s in sonuc] == [False, False, True]
    assert "açılamadı" in sonuc[0].hata or "PDF" in sonuc[0].hata


def test_parolali_dosya(app, tmp_path):
    b = Belge.ac(pdf_yap(tmp_path / "k.pdf", 1))
    koruma.parola_ekle(b, tmp_path / "p.pdf", acma_parolasi="pw")
    b.kapat()
    hook, _ = cikti_ayarla(tmp_path)
    atla = toplu_yazdir([str(tmp_path / "p.pdf")], pdf_yazici(), parola_sor=lambda y: None, her_dosya_icin=hook)
    assert not atla[0].tamam and "atlandı" in atla[0].hata
    ok = toplu_yazdir([str(tmp_path / "p.pdf")], pdf_yazici(), parola_sor=lambda y: "pw", her_dosya_icin=hook)
    assert ok[0].tamam and ok[0].sayfa == 1


def test_iptal(app, tmp_path):
    dosyalar = [str(pdf_yap(tmp_path / f"{i}.pdf", 1)) for i in range(3)]
    hook, _ = cikti_ayarla(tmp_path)
    sonuc = toplu_yazdir(dosyalar, pdf_yazici(), ilerleme=lambda n, t: n >= 1 and n < t, her_dosya_icin=hook)
    assert len(sonuc) == 1


def test_dialog(app, tmp_path):
    d = TopluYazdirPenceresi(str(tmp_path))
    d._onayla()
    assert "ekleyin" in d.hata.text()
    d.dosya_ekle(["a.pdf", "b.pdf", "a.pdf"])  # yineleme eklenmez
    assert d.yollar() == ["a.pdf", "b.pdf"]
    d.aralik.setText("x")
    d._onayla()
    assert "Geçersiz" in d.hata.text()
    d.aralik.setText("1-2")
    d.liste.setCurrentRow(0)
    d._kaldir()
    assert d.yollar() == ["b.pdf"]
    d._onayla()
    assert d.result() == 1


def test_ana_pencere_ozeti(pencere, tmp_path, monkeypatch):
    assert pencere.e_toplu_yazdir.isEnabled()  # belge açık olmasa da çalışır
    a = pdf_yap(tmp_path / "a.pdf", 2)
    bozuk = tmp_path / "x.pdf"
    bozuk.write_bytes(b"degil")
    uyari = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a_, **k: uyari.append(a_[2])))
    y = pdf_yazici()
    y.setOutputFileName(str(tmp_path / "toplam.pdf"))
    sonuc = pencere.toplu_yazdir_calistir([str(a), str(bozuk)], y)
    assert [s.tamam for s in sonuc] == [True, False]
    assert uyari and "1 dosya, 2 sayfa" in uyari[0] and "x.pdf" in uyari[0]
    pencere.toplu_yazdir_calistir([str(a)], y)
    assert "1 dosya, 2 sayfa" in pencere.statusBar().currentMessage()
