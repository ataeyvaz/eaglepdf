"""Sade, Türkçe, yerel çalışan PDF uygulaması."""

import sys
from pathlib import Path

__version__ = "0.1"
DEVELOPERS = "Developed By Usta ve Ata"
APP_NAME = "EaglePDF"  # geçici ad: kullanıcıya görünen ad yalnızca buradan okunur
PAKET_ADI = "Eagle Office"  # ürün ailesinin ortak adı
PAKET_URUNLERI = (("Sözcük", "kelime işlemci"), ("Tabcel", "hesap tablosu"), (APP_NAME, "PDF aracı"))
ILETISIM_EPOSTA = "ataeyvaz@gmail.com"


def resource_dir():
    """Uygulamayla gelen dosyaların (yardim.md, logo) klasörü; PyInstaller'da çıkarma klasörü."""
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        return base / "eaglepdf" if (base / "eaglepdf").is_dir() else base
    return Path(__file__).resolve().parent
