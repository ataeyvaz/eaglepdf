import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import time
import urllib.error

import pytest
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from eaglepdf.core import ocr, ocr_veri
from eaglepdf.ui import ocr_arayuzu, theme
from eaglepdf.ui.ayarlar_penceresi import AyarlarPenceresi
from eaglepdf.ui.ocr_arayuzu import dil_secenekleri
from eaglepdf.ui.ocr_veri_penceresi import OcrVeriPenceresi, boyut_metni
from eaglepdf.ui.pencere import AnaPencere
from test_ocr_veri import SahteCevap

_ENG = ocr.tessdata_bul("eng")
pytestmark = pytest.mark.skipif(_ENG is None, reason="Doğrulama için kurulu bir eng.traineddata gerekir")


@pytest.fixture(scope="module")
def app():
    a = QApplication.instance() or QApplication([])
    theme.apply(a)
    return a


@pytest.fixture(scope="module")
def gercek() -> bytes:
    return (_ENG / "eng.traineddata").read_bytes()


@pytest.fixture
def klasor(tmp_path, monkeypatch):
    """Gerçek kullanıcı klasörüne dokunmayan, izole bir tessdata klasörü."""
    k = tmp_path / "tessdata"
    k.mkdir()
    monkeypatch.setattr(ocr, "kullanici_tessdata", lambda: k)
    monkeypatch.setattr(ocr, "tessdata_adaylari", lambda: [k])
    return k


def bekle(kosul, saniye=15.0):
    bitis = time.time() + saniye
    while time.time() < bitis:
        QApplication.processEvents()
        if kosul():
            return True
        time.sleep(0.01)
    return kosul()


class YavasCevap(SahteCevap):
    """Her okumada bekler: iptal/kapatma testleri için."""
    def read(self, n=-1):
        time.sleep(0.03)
        return super().read(n)


def pencere_kur(app, klasor, acici=None, onay=True, monkeypatch=None):
    d = OcrVeriPenceresi(None, acici=acici)
    d.onay_sor = lambda kod, kalite: onay
    return d


def indirme_bitsin(d):
    assert bekle(lambda: d._is is not None and not d._is.isRunning() and d.indir_dugme.isEnabled())


# --- liste ---
def test_bos_durum(app, klasor):
    d = OcrVeriPenceresi()
    assert d.liste.topLevelItemCount() == 0 and "Henüz hiç dil verisi yok" in d.durum.text()
    assert not d.sil_dugme.isEnabled()


def test_kurulu_diller_listelenir_turkce_basta(app, klasor, gercek):
    (klasor / "eng.traineddata").write_bytes(gercek)
    (klasor / "tur.traineddata").write_bytes(gercek)
    (klasor / "deu.traineddata").write_bytes(gercek)
    d = OcrVeriPenceresi()
    assert d.kurulu_kodlar() == ["tur", "eng", "deu"]
    satir = d.liste.topLevelItem(0)
    assert [satir.text(i) for i in range(4)] == ["Türkçe", "tur", boyut_metni(len(gercek)), "Kullanıcı klasörü"]
    assert boyut_metni(1024 * 1024) == "1.0 MB"


# --- indirme ---
def test_indirme_basarili_liste_ve_sinyal(app, klasor, gercek):
    d = pencere_kur(app, klasor, acici=lambda url: SahteCevap(gercek))
    degisen = []
    d.degisti.connect(lambda: degisen.append(1))
    d.dil.setCurrentIndex(d.dil.findData("eng"))
    d.indir_baslat()
    assert not d.indir_dugme.isEnabled() and d.iptal_dugme.isVisibleTo(d)   # indirirken kilitli, iptal görünür
    indirme_bitsin(d)
    assert d.kurulu_kodlar() == ["eng"] and degisen == [1] and "doğrulandı" in d.durum.text()
    assert (klasor / "eng.traineddata").read_bytes() == gercek
    assert not d.cubuk.isVisibleTo(d) and not d.iptal_dugme.isVisibleTo(d)
    assert not [p for p in klasor.iterdir() if p.name.startswith(".")]


def test_onay_verilmezse_aga_gidilmez(app, klasor):
    cagrilar = []
    d = pencere_kur(app, klasor, acici=lambda url: cagrilar.append(url), onay=False)
    d.indir_baslat()
    assert cagrilar == [] and d._is is None and d.indir_dugme.isEnabled()


def test_onay_metni_adresi_ve_gizlilik_soyler(app, klasor, monkeypatch):
    d = OcrVeriPenceresi()
    d.dil.setCurrentIndex(d.dil.findData("tur"))
    gorulen = []
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: gorulen.append(a[2]) or QMessageBox.No))
    assert d.onay_sor("tur", "fast") is False
    metin = gorulen[0]
    assert "https://github.com/tesseract-ocr/tessdata_fast/raw/main/tur.traineddata" in metin
    assert "belgeleriniz" in metin and "gönderilmez" in metin and "Türkçe" in metin
    d.onay_sor("tur", "best")
    assert "tessdata_best" in gorulen[1]


def test_ag_hatasi_durum_satirinda_ve_yeniden_denenebilir(app, klasor):
    def acici(url):
        raise urllib.error.URLError("Name or service not known")
    d = pencere_kur(app, klasor, acici=acici)
    d.indir_baslat()
    indirme_bitsin(d)
    assert "İnternet bağlantınızı" in d.durum.text() and "Dosyadan Ekle" in d.durum.text()
    assert d.kurulu_kodlar() == [] and d.indir_dugme.isEnabled() and d.ekle_dugme.isEnabled()


def test_bozuk_icerik_kurulmaz(app, klasor):
    d = pencere_kur(app, klasor, acici=lambda url: SahteCevap(b"\x00" * 100_000))
    d.indir_baslat()
    indirme_bitsin(d)
    assert d.kurulu_kodlar() == [] and not any(klasor.iterdir()) and "geçersiz" in d.durum.text().lower()


def test_iptal(app, klasor, gercek):
    d = pencere_kur(app, klasor, acici=lambda url: YavasCevap(gercek))
    d.dil.setCurrentIndex(d.dil.findData("eng"))
    d.indir_baslat()
    assert bekle(lambda: d.cubuk.value() > 0 or "İndiriliyor…" in d.durum.text())
    d._iptal_et()
    assert "İptal ediliyor" in d.durum.text()
    indirme_bitsin(d)
    assert "iptal edildi" in d.durum.text() and d.kurulu_kodlar() == [] and not any(klasor.iterdir())


def test_pencere_kapatilirken_calisan_indirme_iptal_edilir(app, klasor, gercek):
    d = pencere_kur(app, klasor, acici=lambda url: YavasCevap(gercek))
    d.indir_baslat()
    assert bekle(lambda: d._is.isRunning())
    d.reject()
    assert not d._is.isRunning() and not any(klasor.iterdir())   # iş parçacığı bitti, geçici dosya kalmadı


# --- dosyadan ekle / sil ---
def test_dosyadan_ekle(app, klasor, gercek, tmp_path):
    kaynak = tmp_path / "kaynak"
    kaynak.mkdir()
    (kaynak / "tur.traineddata").write_bytes(gercek)
    (kaynak / "bozuk.traineddata").write_bytes(b"x" * 100_000)
    d = OcrVeriPenceresi()
    degisen = []
    d.degisti.connect(lambda: degisen.append(1))
    assert d._dosyalari_ekle([str(kaynak / "tur.traineddata"), str(kaynak / "bozuk.traineddata")]) == ["tur"]
    assert d.kurulu_kodlar() == ["tur"] and degisen == [1]
    assert "Eklendi: tur" in d.durum.text() and "Eklenemedi" in d.durum.text() and "bozuk.traineddata" in d.durum.text()


def test_dosyadan_ekle_dugmesi_dosya_penceresini_kullanir(app, klasor, gercek, tmp_path, monkeypatch):
    (tmp_path / "eng.traineddata").write_bytes(gercek)
    monkeypatch.setattr(QFileDialog, "getOpenFileNames",
                        staticmethod(lambda *a, **k: ([str(tmp_path / "eng.traineddata")], "")))
    d = OcrVeriPenceresi()
    d.dosyadan_ekle()
    assert d.kurulu_kodlar() == ["eng"]


def test_sil_yalniz_kullanici_klasorundekini(app, klasor, gercek, tmp_path, monkeypatch):
    sistem = tmp_path / "sistem"
    sistem.mkdir()
    (klasor / "tur.traineddata").write_bytes(gercek)
    (sistem / "eng.traineddata").write_bytes(gercek)
    monkeypatch.setattr(ocr, "tessdata_adaylari", lambda: [klasor, sistem])
    d = OcrVeriPenceresi()
    assert d.kurulu_kodlar() == ["tur", "eng"]
    d.liste.setCurrentItem(d.liste.topLevelItem(1))     # eng: sistem klasöründe
    assert not d.sil_dugme.isEnabled()
    d.liste.setCurrentItem(d.liste.topLevelItem(0))     # tur: kullanıcı klasöründe
    assert d.sil_dugme.isEnabled()
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.No))
    d.sil()
    assert (klasor / "tur.traineddata").exists()        # vazgeçildi
    degisen = []
    d.degisti.connect(lambda: degisen.append(1))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes))
    d.sil()
    assert not (klasor / "tur.traineddata").exists() and d.kurulu_kodlar() == ["eng"] and degisen == [1]
    assert (sistem / "eng.traineddata").exists()        # sistem dosyasına dokunulmadı


# --- OCR menüsü / yönlendirme ---
def test_dil_secenekleri_kurulu_diger_dilleri_ekler(app, klasor, gercek):
    assert dil_secenekleri() == []
    (klasor / "tur.traineddata").write_bytes(gercek)
    (klasor / "eng.traineddata").write_bytes(gercek)
    assert [k for k, _ in dil_secenekleri()] == ["tur+eng", "tur", "eng"]
    (klasor / "deu.traineddata").write_bytes(gercek)
    assert dil_secenekleri()[-1] == ("deu", "Almanca")
    (klasor / "osd.traineddata").write_bytes(gercek)
    assert "osd" not in [k for k, _ in dil_secenekleri()]


@pytest.fixture
def pencere(app, tmp_path):
    p = AnaPencere(str(tmp_path / "ayar.ini"))
    p.show()
    yield p
    for o in p._oturumlar:
        o.belge.degisti = False
    p.close()


def test_menu_dil_verisi_belge_olmadan_calisir(pencere, monkeypatch):
    assert "Dil Verisi…" in [a.text() for a in pencere.m_ocr.actions()]
    assert pencere.e_ocr_veri.isEnabled() and not pencere.e_aranabilir.isEnabled()
    acilan = []
    monkeypatch.setattr(ocr_arayuzu.OcrVeriPenceresi, "exec", lambda self_: acilan.append(1))
    pencere.e_ocr_veri.trigger()
    assert acilan == [1]


def test_dil_verisi_yoksa_pencereyi_onerir_evet_ise_acar(pencere, klasor, gercek, monkeypatch):
    sorular = []
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: sorular.append(a[2]) or QMessageBox.No))
    assert pencere._ocr_hazir_mi() is False
    assert "traineddata" in sorular[0] and str(klasor) in sorular[0] and "indirmek ya da dosyadan eklemek" in sorular[0]

    def sahte_exec(self_):   # kullanıcı pencerede dili kurdu
        (klasor / "tur.traineddata").write_bytes(gercek)
        (klasor / "eng.traineddata").write_bytes(gercek)
    monkeypatch.setattr(ocr_arayuzu.OcrVeriPenceresi, "exec", sahte_exec)
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes))
    assert pencere._ocr_hazir_mi() is True      # pencere açıldı, veri kuruldu → OCR devam edebilir


def test_dil_verisi_varsa_soru_sorulmaz(pencere, klasor, gercek, monkeypatch):
    (klasor / "tur.traineddata").write_bytes(gercek)
    (klasor / "eng.traineddata").write_bytes(gercek)
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: pytest.fail("soru sorulmamalı")))
    assert pencere._ocr_hazir_mi() is True


# --- Ayarlar ---
def test_ayarlar_dil_verisi_dugmesi_kutuyu_yeniler(pencere, klasor, gercek, monkeypatch):
    d = AyarlarPenceresi(pencere.ayarlar, pencere)
    assert not d.ocr_dil.isEnabled() and d.ocr_dil.currentText() == "Dil verisi kurulu değil"

    def sahte_exec(self_):
        (klasor / "tur.traineddata").write_bytes(gercek)
        (klasor / "eng.traineddata").write_bytes(gercek)
    import eaglepdf.ui.ayarlar_penceresi as ap
    monkeypatch.setattr(ap.OcrVeriPenceresi, "exec", sahte_exec)
    d.ocr_veri_dugme.click()
    assert d.ocr_dil.isEnabled() and d.ocr_dil.findData("tur+eng") >= 0
    d.ocr_dil.setCurrentIndex(d.ocr_dil.findData("tur"))
    d._ocr_veri_ac()   # yeniden açılıp kapanınca seçim korunur
    assert d.ocr_dil.currentData() == "tur"
