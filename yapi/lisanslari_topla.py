"""Çalışma zamanı bağımlılıklarının lisans metinlerini tek dosyada toplar (UCUNCU_TARAF_LISANSLAR.txt).

Paketle birlikte dağıtılır: AGPL-3.0 / LGPL / Apache / BSD / MIT lisansları atıf ve lisans metni dağıtımını ister.
Kaynak: kurulu paketlerin `importlib.metadata` bilgisi ve `*.dist-info/licenses` dosyaları. Ağa çıkmaz.
"""
from __future__ import annotations

import re
import sys
from importlib import metadata
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
# Çalışma zamanında dağıtılmayan (yalnızca geliştirme/derleme) araçlar
GELISTIRME_ARACLARI = {"pytest", "pluggy", "iniconfig", "packaging", "colorama", "pyinstaller", "pyinstaller-hooks-contrib",
                       "altgraph", "pefile", "pywin32-ctypes", "setuptools", "pip", "wheel"}
# PySide6 üst paketi Qt'nin tüm modüllerini (WebEngine/Chromium, Pdf, Addons…) çeker; uygulama yalnızca Essentials'tan
# (Core, Gui, Widgets, Svg, PrintSupport, Network) kullanır ve PyInstaller yalnızca içe aktarılanı pakete koyar.
# Dağıtılmayan bileşenin lisansını beyan etmemek için bunlar *listeden* çıkarılır (bağımlılık dolaşımında kalır ki
# Essentials + shiboken6 bulunsun).
DAGITILMAYAN_QT = {"pyside6", "pyside6-addons", "pyside6-pdf", "pyside6-webengine"}

LISANS_DOSYASI = re.compile(r"(^|/)(licen[sc]e|copying|notice|authors)[^/]*$", re.I)
EN_COK_METIN = 120_000   # tek paket için (bayt): dev lisans dosyalarını kırp


def _ad_norm(ad: str) -> str:
    return re.sub(r"[-_.]+", "-", ad).lower()


def gereksinim_adlari(requirements: Path | None = None) -> list[str]:
    """requirements.txt içindeki paket adları (sürüm/işaretçi/yorum atılır)."""
    adlar = []
    for satir in (requirements or KOK / "requirements.txt").read_text(encoding="utf-8").splitlines():
        satir = satir.split("#", 1)[0].strip()
        if not satir:
            continue
        m = re.match(r"[A-Za-z0-9][A-Za-z0-9._-]*", satir)
        if m and _ad_norm(m.group(0)) not in GELISTIRME_ARACLARI:
            adlar.append(m.group(0))
    return adlar


def bagimlilik_kapanisi(kokler: list[str]) -> dict[str, metadata.Distribution]:
    """Kökler ve (isteğe bağlı olmayan) dolaylı bağımlılıkları: {normalleşmiş ad: dağıtım}."""
    bulunan: dict[str, metadata.Distribution] = {}
    kuyruk = [_ad_norm(k) for k in kokler]
    while kuyruk:
        ad = kuyruk.pop()
        if ad in bulunan or ad in GELISTIRME_ARACLARI:
            continue
        try:
            d = metadata.distribution(ad)
        except metadata.PackageNotFoundError:
            continue
        bulunan[ad] = d
        for gereksinim in d.requires or []:
            if "extra ==" in gereksinim.replace('"', "'").replace("'", ""):   # isteğe bağlı ek paketler dağıtılmaz
                continue
            if "sys_platform" in gereksinim and "win32" not in gereksinim and sys.platform == "win32":
                continue
            m = re.match(r"[A-Za-z0-9][A-Za-z0-9._-]*", gereksinim)
            if m:
                kuyruk.append(_ad_norm(m.group(0)))
    return bulunan


def lisans_bilgisi(d: metadata.Distribution) -> tuple[str, str]:
    """(lisans adı, lisans/atıf dosyalarının birleşik metni)."""
    m = d.metadata
    ad = m.get("License-Expression") or ""
    if not ad:
        ham = m.get("License") or ""
        ad = ham if 0 < len(ham) < 120 and "\n" not in ham else ""
    if not ad:
        siniflar = [c.split("::")[-1].strip() for c in (m.get_all("Classifier") or []) if c.startswith("License ::")]
        ad = ", ".join(siniflar)
    metinler = []
    for f in d.files or []:
        if LISANS_DOSYASI.search(str(f).replace("\\", "/")):
            try:
                metin = Path(d.locate_file(f)).read_text(encoding="utf-8", errors="replace").strip()
            except OSError:
                continue
            if metin:
                metinler.append(f"--- {Path(str(f)).name} ---\n{metin}")
    govde = "\n\n".join(metinler)
    if not govde:
        govde = (m.get("License") or "").strip()[:EN_COK_METIN]   # bazı paketler metni License alanına koyar
    return ad or "belirtilmemiş", govde[:EN_COK_METIN]


def topla(requirements: Path | None = None) -> str:
    from eaglepdf import APP_NAME, __version__
    dagitimlar = bagimlilik_kapanisi(gereksinim_adlari(requirements))
    satirlar = [
        f"{APP_NAME} {__version__} — ÜÇÜNCÜ TARAF YAZILIMLAR VE LİSANSLARI",
        "=" * 72,
        "",
        f"{APP_NAME} açık kaynaktır: GNU Affero Genel Kamu Lisansı v3 (AGPL-3.0). Lisans metni LICENSE dosyasındadır.",
        "AGPL-3.0 gereği tam kaynak kodu bu paketle birlikte `*-kaynak.zip` olarak verilir.",
        "",
        "PySide6 / Qt (LGPL-3.0): Qt kütüphaneleri `_internal` klasöründe ayrı DLL/PYD dosyalarıdır. Bunları kendi sürümünüzle",
        "değiştirebilirsiniz (yeniden bağlama hakkı); bu yüzden uygulama tek dosya (onefile) değil klasör (onedir) olarak paketlenir.",
        "",
        "Aşağıda uygulamanın çalışma zamanında kullandığı paketler ve lisans metinleri listelenir.",
        "",
    ]
    for ad in sorted(dagitimlar):
        if ad in DAGITILMAYAN_QT:
            continue
        d = dagitimlar[ad]
        lisans, govde = lisans_bilgisi(d)
        satirlar += ["", "=" * 72, f"{d.metadata['Name']} {d.version}", f"Lisans: {lisans}", "=" * 72]
        satirlar.append(govde if govde else "(Paket lisans metni içermiyor; lisans adı yukarıda belirtilmiştir.)")
    return "\n".join(satirlar) + "\n"


if __name__ == "__main__":
    sys.path.insert(0, str(KOK))
    hedef = Path(sys.argv[1]) if len(sys.argv) > 1 else KOK / "build" / "UCUNCU_TARAF_LISANSLAR.txt"
    hedef.parent.mkdir(parents=True, exist_ok=True)
    hedef.write_text(topla(), encoding="utf-8")
    print("yazıldı:", hedef, hedef.stat().st_size, "bayt")
