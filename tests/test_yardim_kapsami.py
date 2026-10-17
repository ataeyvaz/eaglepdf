"""Yardım ile arayüz arasındaki uyum: her kısayol ve her ana menü eylemi yardımda geçmeli (CLAUDE.md kural 8)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication

from eaglepdf import APP_NAME
from eaglepdf.ui import theme
from eaglepdf.ui.oturum import EN_COK_SEKME
from eaglepdf.ui.pencere import AnaPencere
from eaglepdf.ui.yardim import konulari_yukle


@pytest.fixture(scope="module")
def app():
    a = QApplication.instance() or QApplication([])
    theme.apply(a)
    return a


@pytest.fixture
def pencere(app, tmp_path):
    p = AnaPencere(str(tmp_path / "ayar.ini"))
    yield p
    p.close()


@pytest.fixture(scope="module")
def konular():
    return {k.kimlik: k for k in konulari_yukle()}


def tum_metin(konular) -> str:
    return "\n".join(k.govde for k in konular.values())


def test_her_kisayol_yardimda_geciyor(pencere, konular):
    metin = tum_metin(konular)
    eksik = {}
    for eylem in pencere.findChildren(QAction):
        for ks in eylem.shortcuts():
            t = ks.toString()
            if t and t not in metin:
                eksik.setdefault(t, eylem.text())
    assert not eksik, f"Yardımda geçmeyen kısayollar (kısayollar tablosuna ekleyin): {eksik}"


def test_sekmeler_konusu_var_ve_onemli_basliklari_icerir(konular):
    assert "sekmeler" in konular
    govde = konular["sekmeler"].govde
    for beklenen in ("Ctrl+Tab", "Ctrl+Shift+W", "Ctrl+W", "Diğerlerini Kapat", "Klasörde Göster", "Geri Al geçmişi",
                     "Çakışma koruması", "400 MB", "Tek pencere", "Açılışta son oturum"):
        assert beklenen in govde, beklenen
    assert str(EN_COK_SEKME) in govde   # sekme sınırı koddaki sabitle tutarlı


def test_sekmeler_konusu_baslarken_ten_sonra_gelir(konular):
    sira = list(konular)
    assert sira.index("baslarken") + 1 == sira.index("sekmeler")


def test_ayarlar_konusu_yeni_secenekleri_anlatir(konular):
    govde = konular["ayarlar"].govde
    assert "çalışan pencerede sekme" in govde and "son oturumu geri yükle" in govde


def test_yer_tutucu_cozulur(konular):
    assert "{APP_NAME}" not in tum_metin(konular)
    assert all(k.baslik and k.govde.strip() for k in konular.values())


def test_kisayol_tablosunda_sekme_satirlari_dogru(konular):
    tablo = konular["kisayollar"].govde
    satir = {s.split("|")[1].strip(): s.split("|")[2].strip() for s in tablo.splitlines() if s.startswith("| ") and s.count("|") >= 3}
    assert satir["Ctrl+W"].startswith("Kapat") and "etkin sekme" in satir["Ctrl+W"]
    assert "Ctrl+Shift+W" in satir and "Ctrl+Tab, Ctrl+PgDown" in satir and "Ctrl+Shift+Tab, Ctrl+PgUp" in satir
    assert satir["Alt+F4"] == "Çıkış"


def test_yardimda_bozuk_kacis_karakteri_yok(konular):
    """Ters eğik çizgili kaçışlar kabuk/araç yüzünden gerçek TAB/satır sonuna dönüşüp yol metinlerini bozabilir."""
    ham = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "eaglepdf", "yardim.md"),
               encoding="utf-8").read()
    assert "\t" not in ham
    assert not [c for c in ham if ord(c) < 32 and c not in "\n\r"]
    assert "\\tessdata" in konular["ocr"].govde   # OCR dil verisi yolu doğru yazılmış (ters eğik çizgi + tessdata)


def test_ocr_dil_verisi_ve_gizlilik_agi_acikca_soyler(konular):
    """Uygulamanın tek ağ erişimi (OCR dil dosyası indirme) yardımda ve gizlilik metinlerinde açıkça yazılı olmalı."""
    ocr = konular["ocr"].govde
    for beklenen in ("Dil Verisi…", "İndir…", "Dosyadan Ekle…", "gönderilmez", "doğrulan"):
        assert beklenen in ocr, beklenen
    gizlilik = konular["gizlilik"].govde
    assert "ağ erişimi" in gizlilik and "dil dosyasının" in gizlilik and "kişisel veri gönderilmez" in gizlilik
    from eaglepdf.ui.hakkinda import GIZLILIK
    assert "ağ erişimi" in GIZLILIK and "OCR dil dosyasının indirilmesi" in GIZLILIK and "belgeleriniz hiçbir sunucuya gönderilmez" in GIZLILIK
