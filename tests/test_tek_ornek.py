import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import json
import subprocess
import sys
import time
import uuid

import pytest
from PySide6.QtWidgets import QApplication

from eaglepdf.ui import tek_ornek
from eaglepdf.ui.tek_ornek import TekOrnekSunucu, baslat_veya_devret, gonder, mesaji_coz, sunucu_adi

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MUTLAK = os.path.abspath("C:/belgeler/a.pdf")

# Ayrı süreçte çalışan istemci (gerçek kullanımdaki gibi): işlem 'gonder' | 'devret' | 'ham'
COCUK = """
import sys, json, time
sys.path.insert(0, {kok!r})
from PySide6.QtWidgets import QApplication
from PySide6.QtNetwork import QLocalSocket
app = QApplication([])
from eaglepdf.ui import tek_ornek
o = json.loads(sys.argv[1])
if o["islem"] == "gonder":
    sys.exit(0 if tek_ornek.gonder(o["ad"], o["yollar"]) else 3)
if o["islem"] == "devret":
    d, s = tek_ornek.baslat_veya_devret(o["yollar"], o["ad"])
    sys.exit(0 if d and s is None else 3)
k = QLocalSocket(); k.connectToServer(o["ad"])
if not k.waitForConnected(1500):
    sys.exit(3)
k.write(bytes.fromhex(o["ham"]) + b"x" * o.get("ham_boyut", 0))
t = time.monotonic() + 3
while k.bytesToWrite() > 0 and time.monotonic() < t:
    k.waitForBytesWritten(50); app.processEvents()
k.disconnectFromServer()
if k.state() != QLocalSocket.UnconnectedState:
    k.waitForDisconnected(1000)
sys.exit(0)
""".format(kok=KOK)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def ad():
    return f"EaglePDF-test-{uuid.uuid4().hex}"


@pytest.fixture
def sunucu(app, ad):
    s = TekOrnekSunucu(ad)
    assert s.baslat()
    yield s
    s.durdur()


def bekle(kosul, saniye=20.0):   # yalnızca üst sınır: koşul sağlanınca hemen döner (yüklü makinede süreç başlatma yavaşlayabilir)
    bitis = time.time() + saniye
    while time.time() < bitis:
        QApplication.processEvents()
        if kosul():
            return True
        time.sleep(0.01)
    return kosul()


def cocuk(islem, ad, yollar=(), ham: bytes = b"", ham_boyut: int = 0) -> bool:
    """İstemciyi ayrı süreçte çalıştırır; bu sırada sunucunun olay döngüsünü döndürür. True: süreç 0 koduyla çıktı."""
    spec = json.dumps({"islem": islem, "ad": ad, "yollar": list(yollar), "ham": ham.hex(), "ham_boyut": ham_boyut})
    surec = subprocess.Popen([sys.executable, "-c", COCUK, spec], env={**os.environ, "QT_QPA_PLATFORM": "offscreen"})
    bitis = time.time() + 40
    while surec.poll() is None and time.time() < bitis:
        QApplication.processEvents()
        time.sleep(0.01)
    if surec.poll() is None:
        surec.kill()
        pytest.fail("istemci süreci zamanında bitmedi")
    return surec.poll() == 0


def test_sunucu_adi_kullaniciya_ozel(monkeypatch):
    monkeypatch.setenv("USERNAME", "Ata Şahin/x")
    assert sunucu_adi().startswith("EaglePDF-tek-ornek-") and "/" not in sunucu_adi() and " " not in sunucu_adi()


def test_dinleyen_yoksa_gonder_false(app, ad):
    assert gonder(ad, [MUTLAK], zaman_asimi_ms=200) is False


def test_mesaji_coz_suzer():
    ok = json.dumps({"ac": [MUTLAK, MUTLAK, "goreli.pdf", "C:/x.txt", 5, "", None, "C:/" + "u" * 5000 + ".pdf"]}).encode()
    assert mesaji_coz(ok) == [MUTLAK]   # yinelenen, göreli, pdf olmayan, tür hatalı, boş, uzun elenir
    assert mesaji_coz(b"degil json") is None
    assert mesaji_coz(b'{"baska": 1}') is None
    assert mesaji_coz(b'{"ac": "tek.pdf"}') is None
    assert mesaji_coz(b"\xff\xfe") is None
    assert mesaji_coz(b"[1,2]") is None


def test_en_cok_yol_sayisi():
    yollar = [os.path.abspath(f"C:/d{i}.pdf") for i in range(tek_ornek.EN_COK_YOL + 30)]
    assert len(mesaji_coz(json.dumps({"ac": yollar}).encode())) == tek_ornek.EN_COK_YOL


def test_gonder_ve_alma_ayri_surecten(sunucu, ad):
    alinan = []
    sunucu.istekGeldi.connect(alinan.append)
    b = os.path.abspath("C:/b.PDF")
    assert cocuk("gonder", ad, [MUTLAK, b])
    assert bekle(lambda: alinan) and alinan == [[MUTLAK, b]]


def test_bos_liste_one_getirmek_icin_gelir(sunucu, ad):
    alinan = []
    sunucu.istekGeldi.connect(alinan.append)
    assert cocuk("gonder", ad, [])
    assert bekle(lambda: alinan) and alinan == [[]]


def test_art_arda_birden_cok_istemci(sunucu, ad):
    alinan = []
    sunucu.istekGeldi.connect(alinan.append)
    yollar = [os.path.abspath(f"C:/d{i}.pdf") for i in range(3)]
    for y in yollar:
        assert cocuk("gonder", ad, [y])
    assert bekle(lambda: len(alinan) == 3)
    assert sorted(a[0] for a in alinan) == sorted(yollar)


def test_bozuk_ve_buyuk_mesaj_cokertmez_sonraki_calisir(sunucu, ad):
    alinan = []
    sunucu.istekGeldi.connect(alinan.append)
    assert cocuk("ham", ad, ham=b"{bozuk json\n")
    assert cocuk("ham", ad, ham_boyut=tek_ornek.EN_COK_BAYT + 5000)   # satır sonu yok, çok büyük (komut satırı sınırı için çocuk üretir)
    bekle(lambda: False, 0.3)
    assert alinan == []   # hiçbiri iletilmedi
    assert cocuk("gonder", ad, [MUTLAK]) and bekle(lambda: alinan) and alinan == [[MUTLAK]]   # sunucu ayakta


def test_satir_sonu_olmadan_kapanan_baglanti_yine_islenir(sunucu, ad):
    alinan = []
    sunucu.istekGeldi.connect(alinan.append)
    assert cocuk("ham", ad, ham=json.dumps({"ac": [MUTLAK]}).encode())   # '\n' yok
    assert bekle(lambda: alinan) and alinan == [[MUTLAK]]


def test_ikinci_sunucu_ayni_adi_alamaz(sunucu, ad, app):
    ikinci = TekOrnekSunucu(ad)
    assert ikinci.baslat() is False and not ikinci.calisiyor   # kilit birincide


def test_durdur_kilidi_birakir_tekrar_baslatilabilir(app, ad):
    s = TekOrnekSunucu(ad)
    assert s.baslat() and s.calisiyor
    s.durdur()
    assert not s.calisiyor and gonder(ad, [MUTLAK], 200) is False
    baska = TekOrnekSunucu(ad)   # kilit serbest: başkası alabilir
    assert baska.baslat()
    baska.durdur()
    assert s.baslat()
    s.durdur()


def test_baslat_veya_devret_ilk_surec_sunucu_olur(app, ad):
    devredildi, s = baslat_veya_devret([MUTLAK], ad)
    assert devredildi is False and s is not None and s.calisiyor
    s.durdur()


def test_baslat_veya_devret_ikinci_surec_birinciye_devreder(sunucu, ad):
    """Uçtan uca: ayrı süreç `baslat_veya_devret` çağırır, dosyayı bize yollar, sunucu kurmadan 0 koduyla çıkar."""
    alinan = []
    sunucu.istekGeldi.connect(alinan.append)
    assert cocuk("devret", ad, [MUTLAK])
    assert bekle(lambda: alinan) and alinan == [[MUTLAK]]


def test_baslat_veya_devret_yarista_kaybeden_tekrar_dener(app, ad, monkeypatch):
    kazanan = TekOrnekSunucu(ad)
    assert kazanan.baslat()
    sirayla = iter([False, True])   # ilk gönderme (henüz yokmuş gibi) başarısız; ikinci başarılı
    monkeypatch.setattr(tek_ornek, "gonder", lambda *a, **k: next(sirayla))
    devredildi, s = baslat_veya_devret([MUTLAK], ad)   # baslat() kilit yüzünden False → yeniden gönderir
    assert devredildi is True and s is None
    kazanan.durdur()


def test_baslat_veya_devret_kimse_yoksa_sunucusuz_devam(app, ad, monkeypatch):
    monkeypatch.setattr(tek_ornek, "gonder", lambda *a, **k: False)
    monkeypatch.setattr(tek_ornek.TekOrnekSunucu, "baslat", lambda self: False)
    assert baslat_veya_devret([MUTLAK], ad) == (False, None)
