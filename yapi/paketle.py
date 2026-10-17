"""EaglePDF'i Windows için paketler (PyInstaller onedir) ve paketi doğrular.

Kullanım:  .venv\\Scripts\\python yapi\\paketle.py [--sinama-yok] [--zip-yok]

Adımlar: simge → sürüm bilgisi → lisans toplama → PyInstaller → LICENSE/README/lisanslar kopyası →
**kendini sınama** (paketlenmiş exe kritik yolları gerçekten çalıştırır; başarısızsa çıkış kodu 1) → taşınabilir zip + kaynak zip.
Çıktı: dist\\EaglePDF\\EaglePDF.exe, dist\\EaglePDF-<sürüm>-tasinabilir.zip, dist\\EaglePDF-<sürüm>-kaynak.zip
Derleme aracı PyInstaller yalnızca geliştirme bağımlılığıdır (requirements-yapi.txt); pakete girmez.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK))
sys.path.insert(0, str(KOK / "yapi"))

from eaglepdf import APP_NAME, PAKET_ADI, __version__  # noqa: E402

DIST = KOK / "dist"
BUILD = KOK / "build"
UYGULAMA = DIST / APP_NAME


def adim(metin: str):
    print(f"\n=== {metin}", flush=True)


def surum_bilgisi_yaz() -> Path:
    from PyInstaller.utils.win32.versioninfo import (FixedFileInfo, StringFileInfo, StringStruct, StringTable, VarFileInfo,
                                                     VarStruct, VSVersionInfo)
    v = tuple(int(x) for x in (__version__.split(".") + ["0", "0", "0"])[:4])
    bilgi = VSVersionInfo(
        ffi=FixedFileInfo(filevers=v, prodvers=v, mask=0x3F, flags=0, OS=0x40004, fileType=1, subtype=0, date=(0, 0)),
        kids=[StringFileInfo([StringTable("041f04b0", [
            StringStruct("CompanyName", PAKET_ADI), StringStruct("FileDescription", f"{APP_NAME} PDF aracı"),
            StringStruct("FileVersion", __version__), StringStruct("InternalName", APP_NAME),
            StringStruct("LegalCopyright", "AGPL-3.0 — açık kaynak"), StringStruct("OriginalFilename", f"{APP_NAME}.exe"),
            StringStruct("ProductName", APP_NAME), StringStruct("ProductVersion", __version__)])]),
            VarFileInfo([VarStruct("Translation", [0x041F, 1200])])])
    BUILD.mkdir(exist_ok=True)
    hedef = BUILD / "surum_bilgisi.txt"
    hedef.write_text(str(bilgi), encoding="utf-8")
    return hedef


def klasor_boyutu(k: Path) -> int:
    return sum(f.stat().st_size for f in k.rglob("*") if f.is_file())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sinama-yok", action="store_true", help="paketlenmiş uygulamada kendini sınamayı atla (önerilmez)")
    ap.add_argument("--zip-yok", action="store_true", help="zip dosyalarını üretme")
    ap.add_argument("--derleme-yok", action="store_true", help="PyInstaller'ı çalıştırma; mevcut dist klasörünü doğrula ve zip'le")
    arg = ap.parse_args()
    for akis in (sys.stdout, sys.stderr):   # Windows konsol kod sayfası (cp1254) → ve ✓ gibi karakterlerde çökmesin
        try:
            akis.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    t0 = time.time()

    adim("Simge")
    ico = KOK / "yapi" / "eaglepdf.ico"
    if not ico.is_file():
        import ikon_uret
        ikon_uret.ciz().save(ico, format="ICO", sizes=ikon_uret.BOYUTLAR)
    print(ico)

    adim("Sürüm bilgisi")
    print(surum_bilgisi_yaz())

    adim("Lisanslar")
    import lisanslari_topla
    lisans = BUILD / "UCUNCU_TARAF_LISANSLAR.txt"
    lisans.write_text(lisanslari_topla.topla(), encoding="utf-8")
    print(lisans, lisans.stat().st_size, "bayt")

    if arg.derleme_yok:
        adim("PyInstaller atlandı (--derleme-yok): mevcut paket kullanılıyor")
    else:
        adim("PyInstaller (birkaç dakika sürebilir; RAM yoğun)")
        if UYGULAMA.exists():
            shutil.rmtree(UYGULAMA)
        komut = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--distpath", str(DIST),
                 "--workpath", str(BUILD / "pyinstaller"), str(KOK / "yapi" / "EaglePDF.spec")]
        if subprocess.run(komut, cwd=KOK).returncode != 0:
            print("PyInstaller başarısız.")
            return 1
    exe = UYGULAMA / f"{APP_NAME}.exe"
    if not exe.is_file():
        print("Beklenen exe yok:", exe)
        return 1

    adim("Belgeler paketin içine")
    for kaynak in (KOK / "LICENSE", KOK / "README.md"):
        shutil.copy2(kaynak, UYGULAMA / kaynak.name)
    shutil.copy2(lisans, UYGULAMA / lisans.name)
    print("LICENSE, README.md, UCUNCU_TARAF_LISANSLAR.txt")

    if not arg.sinama_yok:
        adim("Paketlenmiş uygulamada kendini sınama")
        rapor = BUILD / "paket_oz_sinama.txt"
        rapor.unlink(missing_ok=True)
        try:
            kod = subprocess.run([str(exe), f"--oz-sinama={rapor}"], timeout=900).returncode
        except subprocess.TimeoutExpired:
            print("Kendini sınama zaman aşımına uğradı.")
            return 1
        print(rapor.read_text(encoding="utf-8") if rapor.is_file() else "(rapor yazılmadı!)")
        if kod != 0 or not rapor.is_file():
            print(f"KENDİNİ SINAMA BAŞARISIZ (çıkış kodu {kod}) — paket dağıtılmamalı.")
            return 1

    if not arg.zip_yok:
        adim("Zip dosyaları")
        tasinabilir = shutil.make_archive(str(DIST / f"{APP_NAME}-{__version__}-tasinabilir"), "zip", DIST, APP_NAME)
        kaynak_zip = DIST / f"{APP_NAME}-{__version__}-kaynak.zip"
        sonuc = subprocess.run(["git", "archive", "--format=zip", f"--prefix={APP_NAME}-kaynak/", "-o", str(kaynak_zip), "HEAD"],
                               cwd=KOK, capture_output=True, text=True)
        print(tasinabilir, Path(tasinabilir).stat().st_size // (1024 * 1024), "MB")
        print(kaynak_zip if sonuc.returncode == 0 else f"kaynak zip üretilemedi: {sonuc.stderr.strip()}")

    print(f"\nTAMAM: {UYGULAMA} ({klasor_boyutu(UYGULAMA) // (1024 * 1024)} MB) — {time.time() - t0:.0f} sn")
    return 0


if __name__ == "__main__":
    sys.exit(main())
