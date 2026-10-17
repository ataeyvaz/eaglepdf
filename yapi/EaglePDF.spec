# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller tanımı (onedir). Doğrudan çalıştırılmaz: `python yapi/paketle.py` kullanın.

onedir zorunlu: PySide6 (LGPL) kütüphaneleri ayrı DLL/PYD dosyaları olarak kalmalı ki kullanıcı değiştirip yeniden bağlayabilsin
(CLAUDE.md kural 3). UPX kapalı: antivirüs yanlış alarmlarını azaltır.
"""
import os

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

KOK = os.path.abspath(os.path.join(SPECPATH, ".."))
SURUM_DOSYASI = os.path.join(KOK, "build", "surum_bilgisi.txt")   # paketle.py üretir

# Uygulamayla gelen veri dosyaları (resource_dir() donmuş çalışmada <paket>/eaglepdf altına bakar)
datas = [
    (os.path.join(KOK, "eaglepdf", "yardim.md"), "eaglepdf"),
    (os.path.join(KOK, "eaglepdf", "eagle-office-logo.png"), "eaglepdf"),
]
# Bağımlılıkların kendi veri dosyaları (Noto Sans, docx/pptx şablonları, sertifika paketi, saat dilimleri…)
for paket in ("pymupdf_fonts", "docx", "pptx", "pdf2docx", "pyhanko", "pyhanko_certvalidator", "certifi", "openpyxl",
              "mammoth", "tzdata", "fontTools"):
    try:
        datas += collect_data_files(paket)
    except Exception:
        pass

# Dinamik içe aktarılan modüller (PyInstaller statik analizle göremez)
hiddenimports = []
for paket in ("pyhanko", "pyhanko_certvalidator", "oscrypto", "asn1crypto", "pdf2docx", "comtypes"):
    try:
        hiddenimports += collect_submodules(paket)
    except Exception:
        pass
hiddenimports += ["uharfbuzz", "tzlocal", "lxml._elementpath", "comtypes.client"]

excludes = ["tkinter", "pytest", "IPython", "matplotlib", "scipy", "PyInstaller", "setuptools", "pip"]

a = Analysis(
    [os.path.join(KOK, "main.py")],
    pathex=[KOK],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="EaglePDF",
    debug=False,
    strip=False,
    upx=False,
    console=False,   # pencereli uygulama (konsol açılmaz); kendini sınama raporu dosyaya yazılır
    icon=os.path.join(KOK, "yapi", "eaglepdf.ico"),
    version=SURUM_DOSYASI if os.path.isfile(SURUM_DOSYASI) else None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="EaglePDF")
