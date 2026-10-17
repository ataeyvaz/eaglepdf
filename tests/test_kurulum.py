"""Eagle Office kurulum paketi: AKILLI KURULUM (sürüm denetimi) gerçek Inno Setup derlemesi + sessiz kurulumlarla sınanır.

Sahte (küçük) uygulama klasörleri ve ayrı AppId/kayıt anahtarı (`/DTEST=1`) kullanılır; gerçek Eagle Office kurulumuna dokunulmaz.
Inno Setup 6 kurulu değilse atlanır. Kurulumlar geçici klasöre ve geçerli kullanıcıya (/CURRENTUSER) yapılır, test sonunda kaldırılır.
"""
import os
import subprocess
import sys
import winreg
from pathlib import Path

import pytest

DERLE = Path(__file__).resolve().parent.parent / "yapi" / "kurulum" / "derle.py"
ISCC = [p for p in (r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe", r"C:\Program Files\Inno Setup 6\ISCC.exe") if os.path.exists(p)]
KAYIT = r"Software\Eagle Office TEST\Surumler"
EXE = r"C:\Windows\System32\whoami.exe"   # sahte uygulama (yalnızca var olması gerekir)

pytestmark = pytest.mark.skipif(not ISCC or sys.platform != "win32", reason="Inno Setup 6 kurulu değil")


def sahte_dist(kok: Path, isaret: str) -> dict:
    """Üç uygulamanın sahte paket klasörleri; `_internal\\veri.txt` içeriği hangi paketten geldiğini gösterir."""
    yollar = {}
    for ad, exe in (("Sozcuk", "Sozcuk.exe"), ("Tabcel", "Tabcel.exe"), ("EaglePDF", "EaglePDF.exe")):
        d = kok / ad
        (d / "_internal").mkdir(parents=True)
        (d / exe).write_bytes(Path(EXE).read_bytes())
        (d / "_internal" / "veri.txt").write_text(isaret, encoding="utf-8")
        yollar[ad] = d
    return yollar


def derle(tmp: Path, ad: str, isaret: str, sozcuk="1.5", tabcel="0.1", eaglepdf="0.1") -> Path:
    d = sahte_dist(tmp / f"dist_{ad}", isaret)
    cikis = tmp / f"cikis_{ad}"
    r = subprocess.run([sys.executable, str(DERLE), "--hizli", "--test", "--sozcuk-dist", str(d["Sozcuk"]),
                        "--tabcel-dist", str(d["Tabcel"]), "--eaglepdf-dist", str(d["EaglePDF"]), "--cikis", str(cikis),
                        "--sozcuk-surum", sozcuk, "--tabcel-surum", tabcel, "--eaglepdf-surum", eaglepdf],
                       capture_output=True, timeout=300)
    assert r.returncode == 0, r.stdout.decode("cp1254", "replace")[-1500:]
    return next(cikis.glob("*.exe"))


@pytest.fixture(scope="module")
def paketler(tmp_path_factory):
    t = tmp_path_factory.mktemp("kurulum_paketleri")
    return {
        "ilk": derle(t, "ilk", "v1"),                          # Sözcük 1.5, Tabcel 0.1, EaglePDF 0.1
        "ayni": derle(t, "ayni", "v2"),                        # aynı sürümler, içerik farklı (dokunulursa fark edilir)
        "tabcel_yeni": derle(t, "tabcel", "v2", tabcel="0.2"),  # yalnızca Tabcel daha yeni
    }


class Kurulum:
    def __init__(self, tmp: Path):
        self.dizin = tmp / "Hedef"
        self.log = tmp / "kurulum.log"
        self.tmp = tmp

    def calistir(self, paket: Path, *ek: str):
        r = subprocess.run([str(paket), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/CURRENTUSER", "/NORESTART",
                            f"/DIR={self.dizin}", f"/LOG={self.log}", *ek], capture_output=True, timeout=300)
        return r.returncode

    def veri(self, uygulama: str):
        d = self.dizin / ("Sözcük" if uygulama == "Sozcuk" else uygulama) / "_internal" / "veri.txt"
        return d.read_text(encoding="utf-8") if d.exists() else None

    def surum(self, ad: str):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KAYIT) as k:
                return winreg.QueryValueEx(k, ad)[0]
        except OSError:
            return None

    def surum_sil(self, ad: str):
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KAYIT, 0, winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, ad)

    def kaldir(self):
        unins = self.dizin / "unins000.exe"
        if unins.exists():
            subprocess.run([str(unins), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"], timeout=120)


@pytest.fixture
def kur(tmp_path):
    k = Kurulum(tmp_path)
    yield k
    k.kaldir()


def test_temiz_bilgisayara_uc_uygulama_kurulur_ve_surumler_kaydedilir(paketler, kur):
    kur.calistir(paketler["ilk"])
    assert [kur.veri(a) for a in ("Sozcuk", "Tabcel", "EaglePDF")] == ["v1", "v1", "v1"]
    assert (kur.surum("Sozcuk"), kur.surum("Tabcel"), kur.surum("EaglePDF")) == ("1.5", "0.1", "0.1")


def test_hepsi_guncelse_hicbir_seye_dokunulmaz(paketler, kur):
    kur.calistir(paketler["ilk"])
    kur.calistir(paketler["ayni"])   # sürümler aynı: güncelleme yok
    assert [kur.veri(a) for a in ("Sozcuk", "Tabcel", "EaglePDF")] == ["v1", "v1", "v1"]   # v2 yazılmadı


def test_yalniz_yeni_surumlu_uygulama_guncellenir(paketler, kur):
    kur.calistir(paketler["ilk"])
    kur.calistir(paketler["tabcel_yeni"])
    assert kur.veri("Tabcel") == "v2" and kur.surum("Tabcel") == "0.2"
    assert kur.veri("Sozcuk") == "v1" and kur.veri("EaglePDF") == "v1"   # eskiler olduğu gibi


def test_yalniz_eksik_olan_kurulur_ornek_sozcuk_ve_tabcel_varken_eaglepdf(paketler, kur):
    kur.calistir(paketler["ilk"], "/COMPONENTS=sozcuk,tabcel")   # makinede yalnızca Sözcük + Tabcel var
    assert kur.veri("EaglePDF") is None
    kur.calistir(paketler["ayni"])                               # varsayılan: eksik olanı kur, ötekilere dokunma
    assert kur.veri("EaglePDF") == "v2"
    assert kur.veri("Sozcuk") == "v1" and kur.veri("Tabcel") == "v1"
    assert kur.surum("EaglePDF") == "0.1"


def test_surum_kaydi_olmayan_eski_kurulum_varsayilan_olarak_korunur(paketler, kur):
    kur.calistir(paketler["ilk"])
    for ad in ("Sozcuk", "Tabcel"):   # 1.1 paketinden kalma kurulum gibi: dosya var, sürüm kaydı yok
        kur.surum_sil(ad)
    kur.calistir(paketler["ayni"])
    assert kur.veri("Sozcuk") == "v1" and kur.veri("Tabcel") == "v1"


def test_acikca_istenen_bilesen_yeniden_kurulur_digerleri_silinmez(paketler, kur):
    kur.calistir(paketler["ilk"])
    kur.calistir(paketler["ayni"], "/COMPONENTS=eaglepdf")   # kullanıcı yalnızca bunu seçti
    assert kur.veri("EaglePDF") == "v2"
    assert kur.veri("Sozcuk") == "v1" and kur.veri("Tabcel") == "v1"   # seçilmeyenler korunur (silinmez)
