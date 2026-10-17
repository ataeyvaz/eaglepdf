"""Eagle Office kurulum paketini derler (Inno Setup). Sürümleri üç uygulamanın `__version__` değerinden okur.

Kullanım (EaglePDF klasöründen):
    .venv\\Scripts\\python yapi\\kurulum\\derle.py            tam derleme (lzma2/max; dist\\EagleOffice-<sürüm>-kurulum.exe)
    .venv\\Scripts\\python yapi\\kurulum\\derle.py --hizli    sıkıştırmasız deneme derlemesi
    .venv\\Scripts\\python yapi\\kurulum\\derle.py --test --sozcuk-dist D --tabcel-dist D --eaglepdf-dist D --cikis D
        ayrı AppId/kayıt anahtarıyla (gerçek kurulumu ezmez) ve verilen sahte klasörlerle derleme (testler kullanır)

Önce üç PyInstaller çıktısı güncel olmalı (Sözcük, Tabcel, EaglePDF: `yapi\\paketle.py`).
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

KLASOR = Path(__file__).resolve().parent
EAGLEPDF = KLASOR.parent.parent
MASAUSTU = EAGLEPDF.parent
ISCC_ADAYLARI = (r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe", r"C:\Program Files\Inno Setup 6\ISCC.exe")
SURUM_DOSYALARI = {
    "Sozcuk": MASAUSTU / "sozcuk" / "sozcuk" / "__init__.py",
    "Tabcel": MASAUSTU / "tabcel" / "tabcel" / "__init__.py",
    "EaglePdf": EAGLEPDF / "eaglepdf" / "__init__.py",
}
DIST = {
    "Sozcuk": MASAUSTU / "sozcuk" / "dist" / "Sozcuk",
    "Tabcel": MASAUSTU / "tabcel" / "dist" / "Tabcel",
    "EaglePdf": EAGLEPDF / "dist" / "EaglePDF",
}
EXE = {"Sozcuk": "Sozcuk.exe", "Tabcel": "Tabcel.exe", "EaglePdf": "EaglePDF.exe"}


def surum_oku(yol: Path) -> str:
    m = re.search(r'^__version__\s*=\s*"([^"]+)"', yol.read_text(encoding="utf-8"), re.M)
    if not m:
        raise SystemExit(f"Sürüm bulunamadı: {yol}")
    return m.group(1)


def iscc_bul() -> str:
    for a in ISCC_ADAYLARI:
        if Path(a).exists():
            return a
    raise SystemExit("Inno Setup 6 bulunamadı (winget install JRSoftware.InnoSetup).")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hizli", action="store_true", help="sıkıştırmasız deneme derlemesi")
    ap.add_argument("--test", action="store_true", help="ayrı AppId ve kayıt anahtarı (/DTEST=1)")
    ap.add_argument("--suite-surum", default="1.2", help="paket (Eagle Office) sürümü")
    ap.add_argument("--sozcuk-dist")
    ap.add_argument("--tabcel-dist")
    ap.add_argument("--eaglepdf-dist")
    ap.add_argument("--sozcuk-surum")
    ap.add_argument("--tabcel-surum")
    ap.add_argument("--eaglepdf-surum")
    ap.add_argument("--cikis", help="çıktı klasörü (varsayılan: EaglePDF\\dist)")
    a = ap.parse_args()

    dist = {"Sozcuk": Path(a.sozcuk_dist) if a.sozcuk_dist else DIST["Sozcuk"],
            "Tabcel": Path(a.tabcel_dist) if a.tabcel_dist else DIST["Tabcel"],
            "EaglePdf": Path(a.eaglepdf_dist) if a.eaglepdf_dist else DIST["EaglePdf"]}
    for ad, yol in dist.items():
        if not (yol / EXE[ad]).exists():
            raise SystemExit(f"{ad} paketi yok: {yol / EXE[ad]} (önce PyInstaller derlemesi)")
    surum = {"Sozcuk": a.sozcuk_surum or surum_oku(SURUM_DOSYALARI["Sozcuk"]),
             "Tabcel": a.tabcel_surum or surum_oku(SURUM_DOSYALARI["Tabcel"]),
             "EaglePdf": a.eaglepdf_surum or surum_oku(SURUM_DOSYALARI["EaglePdf"])}
    komut = [iscc_bul(), f"/DSuiteVersion={a.suite_surum}"]
    for ad in dist:
        komut += [f"/D{ad}Version={surum[ad]}", f"/D{ad}Dist={dist[ad]}"]
    if a.hizli:
        komut.append("/DHIZLI=1")
    if a.test:
        komut.append("/DTEST=1")
    if a.cikis:
        komut.append(f"/DCikisKlasoru={a.cikis}")
    komut.append(str(KLASOR / "eagle-office.iss"))
    print("Sürümler:", ", ".join(f"{k} {v}" for k, v in surum.items()), "· paket", a.suite_surum)
    return subprocess.call(komut)


if __name__ == "__main__":
    sys.exit(main())
