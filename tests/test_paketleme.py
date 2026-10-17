"""Paketleme altyapısı (yapi/) ve kendini sınama modülü testleri. Gerçek PyInstaller derlemesi burada yapılmaz;
o `python yapi/paketle.py` ile yapılır ve paketlenmiş exe'de `--oz-sinama` ile doğrulanır."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys
from pathlib import Path

import pytest
from PIL import Image
from PySide6.QtWidgets import QApplication

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK / "yapi"))

import ikon_uret  # noqa: E402
import lisanslari_topla  # noqa: E402

from eaglepdf import oz_sinama  # noqa: E402
from eaglepdf.oz_sinama import ATLANDI, Atla, Sonuc  # noqa: E402


@pytest.fixture(scope="module")
def app():
    from eaglepdf.ui import theme
    a = QApplication.instance() or QApplication([])
    theme.apply(a)
    return a


# --- lisans toplama ---
def test_gereksinim_adlari_ayrisir(tmp_path):
    r = tmp_path / "r.txt"
    r.write_text("# yorum\n-r baska.txt\nPySide6>=6.6   # LGPL\nPyMuPDF>=1.24\npytest>=8\ncomtypes>=1.4; sys_platform == 'win32'\n\n"
                 "pymupdf-fonts>=1.0\n", encoding="utf-8")
    adlar = lisanslari_topla.gereksinim_adlari(r)
    assert adlar == ["PySide6", "PyMuPDF", "comtypes", "pymupdf-fonts"]   # pytest (geliştirme aracı), yorum, -r atıldı


def test_gercek_requirements_ayrisir_ve_kapanis_dolayli_paketleri_bulur():
    adlar = lisanslari_topla.gereksinim_adlari()
    assert "PyMuPDF" in adlar and "pytest" not in [a.lower() for a in adlar]
    kapanis = lisanslari_topla.bagimlilik_kapanisi(adlar)
    assert "pymupdf" in kapanis and "pyside6-essentials" in kapanis and "shiboken6" in kapanis   # PySide6 → Essentials dolaylı
    assert "cryptography" in kapanis                                                               # pyHanko dolaylı
    assert "pytest" not in kapanis and "pyinstaller" not in kapanis


def test_lisans_dosyasi_icerigi():
    metin = lisanslari_topla.topla()
    assert "AGPL-3.0" in metin and "kaynak" in metin.lower() and "yeniden bağlama" in metin
    assert "PySide6_Essentials" in metin and "shiboken6" in metin
    for dagitilmayan in ("PySide6_WebEngine", "PySide6_Addons", "PySide6_Pdf"):
        assert f"\n{dagitilmayan} " not in metin, f"{dagitilmayan} dağıtılmıyor; lisansı listelenmemeli"
    assert metin.count("\nLisans: ") >= 30
    basliklar = [satir.lower() for satir in metin.splitlines() if satir[:1].isalpha() and satir.split(" ")[-1][:1].isdigit()]
    assert basliklar and not [b for b in basliklar if b.startswith(("pytest ", "pyinstaller "))]   # geliştirme araçları listelenmez
    assert "pymupdf" in metin.lower() and "Artifex" in metin   # PyMuPDF çift lisans (AGPL veya ticari)


def test_lisans_bilgisi_her_paket_icin_ad_dondurur():
    for ad, d in lisanslari_topla.bagimlilik_kapanisi(["pyhanko", "pillow", "numpy"]).items():
        lisans, _ = lisanslari_topla.lisans_bilgisi(d)
        assert lisans and lisans != "", ad


# --- simge, sürüm bilgisi, spec ---
def test_simge_gecerli_ve_cok_boyutlu():
    ico = KOK / "yapi" / "eaglepdf.ico"
    assert ico.is_file() and ico.stat().st_size > 5000
    with Image.open(ico) as im:
        boyutlar = set(im.info.get("sizes", []))
    assert {(256, 256), (48, 48), (32, 32), (16, 16)} <= boyutlar


def test_simge_ciziminde_kose_saydam_cerceve_kirmizi():
    im = ikon_uret.ciz(256)
    assert im.size == (256, 256) and im.mode == "RGBA"
    assert im.getpixel((0, 0))[3] == 0                                   # yuvarlatılmış köşe dışı saydam
    r, g, b, a = im.getpixel((128, 12))                                  # üst kenar çerçevesi
    assert a == 255 and r > 150 and g < 80 and b < 80                    # tema vurgu rengine yakın kırmızı
    assert im.getpixel((128, 128))[3] == 255                             # orta dolu


def test_spec_dosyasi_derlenir_ve_veri_dosyalari_var():
    spec = KOK / "yapi" / "EaglePDF.spec"
    compile(spec.read_text(encoding="utf-8"), str(spec), "exec")        # sözdizimi (PyInstaller genel adları çalışırken gelir)
    icerik = spec.read_text(encoding="utf-8")
    assert "console=False" in icerik and "COLLECT(" in icerik and "upx=False" in icerik
    assert "exclude_binaries=True" in icerik                            # onedir (onefile değil): LGPL yeniden bağlama
    for dosya in ("eaglepdf/yardim.md", "eaglepdf/eagle-office-logo.png", "yapi/eaglepdf.ico", "main.py"):
        assert (KOK / dosya).is_file(), dosya
        assert Path(dosya).name in icerik or dosya in icerik.replace("os.path.join(KOK, ", "").replace('"', "")


def test_surum_bilgisi_yazilir():
    pytest.importorskip("PyInstaller")
    import paketle
    yol = paketle.surum_bilgisi_yaz()
    metin = yol.read_text(encoding="utf-8")
    from eaglepdf import APP_NAME, PAKET_ADI, __version__
    ilk = tuple(int(x) for x in (__version__.split(".") + ["0", "0", "0"])[:4])
    assert f"filevers={ilk}" in metin and "041f04b0" in metin
    assert APP_NAME in metin and PAKET_ADI in metin and "AGPL-3.0" in metin
    assert "[1055, 1200]" in metin   # Türkçe (0x041F) çeviri bilgisi


def test_derleme_bagimliliklari_ayri_dosyada():
    yapi = (KOK / "requirements-yapi.txt").read_text(encoding="utf-8")
    assert "-r requirements.txt" in yapi and "pyinstaller" in yapi.lower()
    assert "pyinstaller" not in (KOK / "requirements.txt").read_text(encoding="utf-8").lower()   # çalışma zamanına girmez
    ignore = (KOK / ".gitignore").read_text(encoding="utf-8")
    assert "build/" in ignore and "dist/" in ignore                      # derleme çıktıları depoya girmez


# --- kendini sınama ---
def test_sonuc_ve_rapor_metni():
    sonuclar = [Sonuc("A", "TAMAM", "iyi"), Sonuc("B", ATLANDI, "veri yok"), Sonuc("C", "HATA", "ImportError: x")]
    rapor = oz_sinama.rapor_metni(sonuclar)
    assert "[TAMAM  ] A — iyi" in rapor and f"[{ATLANDI:7}] B — veri yok" in rapor and "[HATA   ] C" in rapor
    assert "SONUÇ: 1 tamam, 1 atlandı, 1 hata" in rapor
    assert [s.basarisiz for s in sonuclar] == [False, False, True]


def test_calistir_atla_hata_ve_gecici_klasoru_siler():
    gorulen = []

    def iyi(t):
        gorulen.append(t)
        (t / "x").write_text("a")
        return "tamam"

    def atla(t):
        raise Atla("neden")

    def kotu(t):
        raise ImportError("eksik paket")

    s = oz_sinama.calistir((("iyi", iyi), ("atla", atla), ("kotu", kotu)))
    assert [(x.ad, x.durum) for x in s] == [("iyi", "TAMAM"), ("atla", ATLANDI), ("kotu", "HATA")]
    assert s[1].ayrinti == "neden" and "ImportError: eksik paket" in s[2].ayrinti
    assert not gorulen[0].exists() and not gorulen[0].parent.exists()    # geçici kök silindi


def test_calistir_kesme_istisnalarini_yutmaz():
    def kes(t):
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        oz_sinama.calistir((("kes", kes),))


def test_komut_satirindan_bayrak_yoksa_none(app):
    assert oz_sinama.komut_satirindan(["main.py", "a.pdf"]) is None


def test_komut_satirindan_rapor_yazar_ve_cikis_kodu(app, tmp_path, monkeypatch):
    sonuc = {"liste": [Sonuc("A", "TAMAM")]}
    monkeypatch.setattr(oz_sinama, "calistir", lambda: sonuc["liste"])
    rapor = tmp_path / "alt" / "rapor.txt"
    assert oz_sinama.komut_satirindan(["main.py", f"--oz-sinama={rapor}"]) == 0
    assert "SONUÇ: 1 tamam" in rapor.read_text(encoding="utf-8")
    sonuc["liste"] = [Sonuc("A", "TAMAM"), Sonuc("B", "HATA", "x")]
    monkeypatch.setattr(sys, "stdout", None)                              # pencereli exe'de konsol yok: çökmemeli
    assert oz_sinama.komut_satirindan(["main.py", f"--oz-sinama={rapor}"]) == 1
    assert "1 hata" in rapor.read_text(encoding="utf-8")


def test_oz_sinama_secenegi_dosya_yolu_olarak_acilmaz():
    from eaglepdf.ui.oturum import komut_satiri_yollari
    assert komut_satiri_yollari(["main.py", "--oz-sinama", "--oz-sinama=r.txt", "a.pdf"]) == ["a.pdf"]


def test_gercek_kendini_sinama_hatasiz(app):
    """Tüm kritik yollar (PDF, dönüştürme, imza, XMP, OCR(varsa), yazdırma, soket, pencere…) geliştirme ortamında çalışır."""
    sonuclar = oz_sinama.calistir()
    hatalar = [f"{s.ad}: {s.ayrinti}" for s in sonuclar if s.basarisiz]
    assert not hatalar, "\n".join(hatalar)
    assert len(sonuclar) == len(oz_sinama.KONTROLLER) and sum(s.durum == "TAMAM" for s in sonuclar) >= len(sonuclar) - 2
