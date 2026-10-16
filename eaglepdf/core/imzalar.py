"""Kayıtlı görsel imzalar: klasörde saydam PNG dosyaları (Qt'siz). Yalnızca bu bilgisayarda saklanır."""

import re
import time
from pathlib import Path

from .hatalar import BelgeHatasi

PNG_IMZASI = b"\x89PNG\r\n\x1a\n"
EN_COK_BAYT = 5 * 1024 * 1024


def _guvenli_ad(ad: str) -> str:
    ad = re.sub(r"[^\w\- ]", "", ad, flags=re.UNICODE).strip()
    return ad[:40] or "imza"


def kaydet(klasor: Path, png: bytes, ad: str = "") -> Path:
    if not png.startswith(PNG_IMZASI):
        raise BelgeHatasi("İmza bir PNG resmi olmalı.")
    if len(png) > EN_COK_BAYT:
        raise BelgeHatasi("İmza resmi çok büyük (en çok 5 MB).")
    klasor = Path(klasor)
    klasor.mkdir(parents=True, exist_ok=True)
    taban = f"{time.strftime('%Y%m%d-%H%M%S')}-{_guvenli_ad(ad)}"
    yol = klasor / f"{taban}.png"
    n = 2
    while yol.exists():
        yol = klasor / f"{taban}-{n}.png"
        n += 1
    yol.write_bytes(png)
    return yol


def listele(klasor: Path) -> list[Path]:
    """En yeni en sonda olacak şekilde ada göre sıralı."""
    klasor = Path(klasor)
    return sorted(klasor.glob("*.png")) if klasor.is_dir() else []


def sil(yol: Path):
    Path(yol).unlink(missing_ok=True)


def oku(yol: Path) -> bytes:
    return Path(yol).read_bytes()
