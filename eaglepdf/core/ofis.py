"""Yüksek sadakatli Word/Excel → PDF: bilgisayarda Microsoft Word/Excel ya da LibreOffice kuruluysa dönüştürmeyi onlar yapar
(sayfa düzeni, üst/alt bilgi, sütun, metin kutusu, grafik birebir gelir). Kurulu değilse çağıran taraf yerleşik dönüştürücüye düşer.

Her şey bu bilgisayarda yapılır, ağa çıkılmaz. Word/Excel PowerShell COM betiğiyle, LibreOffice komut satırıyla ayrı bir süreçte
çalıştırılır: donarsa zaman aşımı ya da iptalde süreç (ve bizim başlattığımız Office süreci) sonlandırılır; kullanıcının zaten açık
olan Word/Excel penceresine dokunulmaz (kapatılmaz). Belgeler salt okunur açılır, kaynak dosya değişmez.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from .hatalar import BelgeHatasi

ZAMAN_ASIMI = 180.0   # saniye (büyük belge/yavaş makine için cömert)
_SURUCU_KOMUTU = ("powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File")
_GIZLI = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# $bizim: Office'i BİZ başlattıysak (yeni süreç belirdiyse) kapatılır; kullanıcının açık penceresine bağlandıysak yalnızca belgemiz kapatılır
_WORD_BETIGI = """param([string]$Kaynak, [string]$Hedef)
$ErrorActionPreference = 'Stop'
$once = @(Get-Process WINWORD -ErrorAction SilentlyContinue | ForEach-Object { $_.Id })
$w = $null; $d = $null; $bizim = $false
try {
  $w = New-Object -ComObject Word.Application
  $bizim = @(Get-Process WINWORD -ErrorAction SilentlyContinue | Where-Object { $once -notcontains $_.Id }).Count -gt 0
  $w.DisplayAlerts = 0
  $d = $w.Documents.Open($Kaynak, $false, $true, $false)
  $d.ExportAsFixedFormat($Hedef, 17)
} finally {
  if ($d) { try { $d.Close($false) } catch {} }
  if ($w -and $bizim) { try { $w.Quit() } catch {} }
}
"""

_EXCEL_BETIGI = """param([string]$Kaynak, [string]$Hedef)
$ErrorActionPreference = 'Stop'
$once = @(Get-Process EXCEL -ErrorAction SilentlyContinue | ForEach-Object { $_.Id })
$e = $null; $k = $null; $bizim = $false
try {
  $e = New-Object -ComObject Excel.Application
  $bizim = @(Get-Process EXCEL -ErrorAction SilentlyContinue | Where-Object { $once -notcontains $_.Id }).Count -gt 0
  $e.DisplayAlerts = $false
  $k = $e.Workbooks.Open($Kaynak, 0, $true)
  $k.ExportAsFixedFormat(0, $Hedef)
} finally {
  if ($k) { try { $k.Close($false) } catch {} }
  if ($e -and $bizim) { try { $e.Quit() } catch {} }
}
"""


class OfisYok(BelgeHatasi):
    """Bu tür için kullanılabilir Office/LibreOffice yok."""


@dataclass
class OfisDurumu:
    word: bool
    excel: bool
    libreoffice: str | None   # soffice.exe yolu

    def motorlar(self, tur: str) -> list[str]:
        """Bu tür ('word' | 'excel') için denenecek motorlar, öncelik sırasıyla."""
        sonuc = []
        if tur == "word" and self.word:
            sonuc.append("Microsoft Word")
        if tur == "excel" and self.excel:
            sonuc.append("Microsoft Excel")
        if self.libreoffice:
            sonuc.append("LibreOffice")
        return sonuc


def _com_kayitli_mi(prog_id: str) -> bool:
    """COM sınıfı kayıtlı mı (Office kurulu mu); yalnızca kayıt defterine bakar, uygulamayı başlatmaz."""
    if sys.platform != "win32":
        return False
    import winreg
    for kok in (winreg.HKEY_CLASSES_ROOT,):
        try:
            with winreg.OpenKey(kok, rf"{prog_id}\CLSID"):
                return True
        except OSError:
            continue
    return False


def libreoffice_yolu() -> str | None:
    adaylar = [shutil.which("soffice")]
    for kok in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")):
        if kok:
            adaylar.append(os.path.join(kok, "LibreOffice", "program", "soffice.exe"))
    return next((a for a in adaylar if a and os.path.exists(a)), None)


def durum() -> OfisDurumu:
    return OfisDurumu(_com_kayitli_mi("Word.Application"), _com_kayitli_mi("Excel.Application"), libreoffice_yolu())


def _surec_numaralari(ad: str) -> set[str]:
    try:
        cikti = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {ad}", "/FO", "CSV", "/NH"], capture_output=True, text=True,
                               timeout=15, creationflags=_GIZLI).stdout
    except Exception:  # noqa: BLE001
        return set()
    return {satir.split('","')[1] for satir in cikti.splitlines() if satir.count('","') >= 1 and ad.lower() in satir.lower()}


def _agaci_sonlandir(surec: subprocess.Popen):
    try:
        subprocess.run(["taskkill", "/PID", str(surec.pid), "/T", "/F"], capture_output=True, timeout=15, creationflags=_GIZLI)
    except Exception:  # noqa: BLE001
        surec.kill()


def _calistir(komut: list[str], hedef: Path, zaman_asimi: float, iptal, yeni_surec_adi: str | None = None):
    """Komutu çalıştırır; `hedef` PDF'i oluşmazsa hata verir. Zaman aşımı/iptalde süreç sonlandırılır; bu çağrıyla BAŞLAYAN
    Office süreçleri de kapatılır (kullanıcının önceden açık olanına dokunulmaz)."""
    onceki = _surec_numaralari(yeni_surec_adi) if yeni_surec_adi else set()
    surec = subprocess.Popen(komut, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=_GIZLI,
                             encoding="utf-8", errors="replace")
    baslangic = time.monotonic()
    iptal_edildi = zaman_doldu = False
    try:
        while surec.poll() is None:
            if iptal and iptal():
                iptal_edildi = True
                break
            if time.monotonic() - baslangic > zaman_asimi:
                zaman_doldu = True
                break
            time.sleep(0.2)
        if iptal_edildi or zaman_doldu:
            _agaci_sonlandir(surec)
            if yeni_surec_adi:   # bizim başlattığımız (yetim kalmış) Office süreci
                for pid in _surec_numaralari(yeni_surec_adi) - onceki:
                    subprocess.run(["taskkill", "/PID", pid, "/F"], capture_output=True, timeout=15, creationflags=_GIZLI)
            from .donustur import Iptal
            if iptal_edildi:
                raise Iptal("İşlem iptal edildi.")
            raise BelgeHatasi(f"Dönüştürme {int(zaman_asimi)} sn içinde bitmedi.")
        cikti, hata = surec.communicate(timeout=10)
    finally:
        if surec.poll() is None:
            _agaci_sonlandir(surec)
    if surec.returncode != 0 or not hedef.exists() or hedef.stat().st_size == 0:
        ayrinti = " ".join((hata or cikti or "").split())[:300]
        raise BelgeHatasi(f"Çıkış kodu {surec.returncode}" + (f": {ayrinti}" if ayrinti else ""))


def _com_ile(tur: str, kaynak: Path, hedef: Path, zaman_asimi: float, iptal):
    betik = _WORD_BETIGI if tur == "word" else _EXCEL_BETIGI
    with tempfile.TemporaryDirectory(prefix="eaglepdf_ofis_") as gecici:
        dosya = Path(gecici) / "donustur.ps1"
        dosya.write_text(betik, encoding="utf-8-sig")
        _calistir([*_SURUCU_KOMUTU, str(dosya), "-Kaynak", str(kaynak), "-Hedef", str(hedef)], hedef, zaman_asimi, iptal,
                  "WINWORD.EXE" if tur == "word" else "EXCEL.EXE")


def _libreoffice_ile(soffice: str, kaynak: Path, hedef: Path, zaman_asimi: float, iptal):
    with tempfile.TemporaryDirectory(prefix="eaglepdf_lo_") as gecici:
        # kullanıcının açık LibreOffice'ine takılmamak ve kilit çakışmasını önlemek için ayrı profil klasörü
        profil = Path(gecici) / "profil"
        cikis = Path(gecici) / "cikis"
        cikis.mkdir()
        ara_kaynak = Path(gecici) / ("kaynak" + kaynak.suffix.lower())   # Türkçe/boşluklu ad sorunlarına karşı
        shutil.copyfile(kaynak, ara_kaynak)
        beklenen = cikis / (ara_kaynak.stem + ".pdf")
        _calistir([soffice, f"-env:UserInstallation={profil.as_uri()}", "--headless", "--norestore", "--convert-to", "pdf",
                   "--outdir", str(cikis), str(ara_kaynak)], beklenen, zaman_asimi, iptal)
        shutil.copyfile(beklenen, hedef)


def pdf_yap(tur: str, kaynak, hedef, iptal=None, zaman_asimi: float = ZAMAN_ASIMI) -> str:
    """`kaynak` Word/Excel dosyasını `hedef` PDF'e çevirir; kullanılan motorun adını döndürür ('Microsoft Word', 'Microsoft Excel',
    'LibreOffice'). Motorlar sırayla denenir; hiçbiri yoksa `OfisYok`, hepsi başarısızsa `BelgeHatasi` (nedenleriyle) verir.
    `tur`: 'word' | 'excel'. `iptal`: True dönerse işlem iptal edilir (`donustur.Iptal`)."""
    kaynak, hedef = Path(kaynak), Path(hedef)
    d = durum()
    motorlar = d.motorlar(tur)
    if not motorlar:
        raise OfisYok("Bu bilgisayarda Microsoft Office ya da LibreOffice bulunamadı.")
    nedenler = []
    for motor in motorlar:
        try:
            if hedef.exists():
                hedef.unlink()
            if motor == "LibreOffice":
                _libreoffice_ile(d.libreoffice, kaynak, hedef, zaman_asimi, iptal)
            else:
                _com_ile(tur, kaynak, hedef, zaman_asimi, iptal)
            return motor
        except BelgeHatasi as h:
            from .donustur import Iptal
            if isinstance(h, Iptal):
                raise
            nedenler.append(f"{motor}: {h}")
        except OSError as h:
            nedenler.append(f"{motor}: {h}")
    raise BelgeHatasi(" | ".join(nedenler))
