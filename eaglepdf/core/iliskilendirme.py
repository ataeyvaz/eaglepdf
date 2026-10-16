"""Windows dosya ilişkilendirme (Qt'siz): uygulamayı PDF için “Birlikte aç” listesine ekler / kaldırır.

Yalnızca kullanıcı düzeyinde (HKCU) yazılır; yönetici izni gerekmez, sistem ayarlarına dokunulmaz.
Windows 10/11 varsayılan uygulamayı programdan değiştirmeye izin vermez: kullanıcı “Varsayılan uygulamalar” ekranından
seçer (`varsayilan_uygulamalari_ac`).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from .. import APP_NAME
from .hatalar import BelgeHatasi

try:
    import winreg
except ImportError:  # Windows dışı
    winreg = None

PROG_ID = "EaglePDF.PDF"
TABAN = r"Software\Classes"


def _gerekli():
    if winreg is None:
        raise BelgeHatasi("Dosya ilişkilendirme yalnızca Windows'ta desteklenir.")


def baslatici_komutu() -> str:
    """`"pythonw.exe" "main.py" "%1"` (pythonw varsa konsol penceresi açılmaz)."""
    py = Path(sys.executable)
    pyw = py.with_name("pythonw.exe")
    ana = Path(__file__).resolve().parents[2] / "main.py"
    return f'"{pyw if pyw.exists() else py}" "{ana}" "%1"'


def kaydet(komut: str | None = None, taban: str = TABAN) -> None:
    """ProgID oluşturur ve `.pdf` için “Birlikte aç” listesine ekler."""
    _gerekli()
    komut = komut or baslatici_komutu()
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"{taban}\{PROG_ID}") as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, f"{APP_NAME} PDF Belgesi")
            winreg.SetValueEx(k, "FriendlyTypeName", 0, winreg.REG_SZ, f"{APP_NAME} PDF Belgesi")
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"{taban}\{PROG_ID}\shell\open") as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, "Aç")
            winreg.SetValueEx(k, "FriendlyAppName", 0, winreg.REG_SZ, APP_NAME)
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"{taban}\{PROG_ID}\shell\open\command") as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, komut)
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"{taban}\.pdf\OpenWithProgids") as k:
            winreg.SetValueEx(k, PROG_ID, 0, winreg.REG_NONE, b"")
    except OSError as h:
        raise BelgeHatasi(f"Kayıt defterine yazılamadı: {h}") from None


def kayitli_mi(taban: str = TABAN) -> bool:
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, rf"{taban}\.pdf\OpenWithProgids") as k:
            winreg.QueryValueEx(k, PROG_ID)
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, rf"{taban}\{PROG_ID}\shell\open\command"):
            return True
    except OSError:
        return False


def _anahtar_sil(yol: str):
    """Alt anahtarlarıyla birlikte siler (yoksa sessiz geçer)."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, yol, 0, winreg.KEY_ALL_ACCESS) as k:
            while True:
                try:
                    alt = winreg.EnumKey(k, 0)
                except OSError:
                    break
                _anahtar_sil(rf"{yol}\{alt}")
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, yol)
    except FileNotFoundError:
        pass


def kaldir(taban: str = TABAN) -> None:
    """Yalnızca kendi eklediğimiz kayıtları siler; `.pdf`in başka kayıtlarına dokunmaz."""
    _gerekli()
    try:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, rf"{taban}\.pdf\OpenWithProgids", 0, winreg.KEY_SET_VALUE) as k:
                winreg.DeleteValue(k, PROG_ID)
        except FileNotFoundError:
            pass
        _anahtar_sil(rf"{taban}\{PROG_ID}")
    except OSError as h:
        raise BelgeHatasi(f"Kayıt silinemedi: {h}") from None


def varsayilan_uygulamalari_ac() -> None:
    """Windows'un “Varsayılan uygulamalar” ayar ekranını açar."""
    if hasattr(os, "startfile"):
        os.startfile("ms-settings:defaultapps")
