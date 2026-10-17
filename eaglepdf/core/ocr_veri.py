"""OCR dil verisi (`*.traineddata`) yönetimi: indir, dosyadan ekle, doğrula, listele, sil (Qt'siz).

Ağ erişimi **yalnızca** kullanıcı açıkça istediğinde ve **yalnızca** Tesseract projesinin dil deposundan dosya istemek içindir
(belge ya da kişisel veri gönderilmez). İndirilen dosya kullanılmadan önce Tesseract ile gerçekten yüklenip yüklenmediği
denenir; geçersizse atılır, mevcut dosya korunur. İnternetsiz kullanım için `dosyadan_ekle` vardır.
Dil verisi lisansı: Apache-2.0 (tessdata_fast / tessdata_best).
"""
from __future__ import annotations

import os
import re
import shutil
import struct
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import pymupdf

from .. import APP_NAME
from . import ocr
from .hatalar import BelgeHatasi

DEPO_URL = "https://github.com/tesseract-ocr/{depo}/raw/main/{kod}.traineddata"
KALITELER = {"fast": ("Hızlı (önerilen)", "tessdata_fast"), "best": ("En iyi (daha büyük, daha yavaş)", "tessdata_best")}
IZINLI_SUNUCULAR = {"github.com", "raw.githubusercontent.com", "media.githubusercontent.com"}
EN_AZ_BAYT = 50 * 1024            # bundan küçük dosya dil verisi olamaz
EN_COK_BAYT = 200 * 1024 * 1024   # bundan büyük indirme reddedilir
BLOK = 64 * 1024

# İndirilebilen diller (kod → Türkçe ad). Dosyadan eklemede her geçerli kod kabul edilir.
KATALOG = {"tur": "Türkçe", "eng": "İngilizce", "deu": "Almanca", "fra": "Fransızca", "spa": "İspanyolca",
           "ita": "İtalyanca", "rus": "Rusça", "ara": "Arapça"}
_KOD = re.compile(r"^[A-Za-z][A-Za-z0-9_]{1,30}$")


class IndirmeIptal(BelgeHatasi):
    """Kullanıcı indirmeyi iptal etti."""


def dil_adi(kod: str) -> str:
    return KATALOG.get(kod, kod)


def kod_gecerli_mi(kod: str) -> bool:
    return bool(_KOD.match(kod or ""))


def _yapiyi_denetle(yol: Path):
    """`traineddata` başlığı: int32 bileşen sayısı n, ardından n adet int64 ofset (-1 = bileşen yok; diğerleri artan ve
    dosya boyutu içinde). Tamamı sıfır / HTML hata sayfası / yarım kalmış dosya burada elenir (Tesseract bunların bir kısmını
    hata vermeden yükleyip eski motora düşebiliyor, yalnızca yükleme denemesi yetmez)."""
    boyut = yol.stat().st_size
    with open(yol, "rb") as f:
        bas = f.read(4)
        n = struct.unpack("<i", bas)[0] if len(bas) == 4 else 0
        if not 1 <= n <= 64 or 4 + 8 * n > boyut:
            raise BelgeHatasi("Dil dosyası geçersiz: biçimi tanınmadı (bozuk ya da bir dil verisi değil).")
        tablo = f.read(8 * n)
    ofsetler = [o for o in struct.unpack(f"<{n}q", tablo) if o != -1]
    if not ofsetler or any(o < 4 + 8 * n or o >= boyut for o in ofsetler) or ofsetler != sorted(ofsetler):
        raise BelgeHatasi("Dil dosyası geçersiz: eksik indirilmiş ya da bozuk.")


def dogrula(yol, kod: str):
    """Dosya geçerli bir dil verisi mi (yapı) ve Tesseract o dil için yükleyebiliyor mu? Değilse `BelgeHatasi`."""
    yol = Path(yol)
    if not yol.is_file() or yol.stat().st_size < EN_AZ_BAYT:
        raise BelgeHatasi("Dil dosyası geçersiz: dosya çok küçük ya da boş.")
    _yapiyi_denetle(yol)
    gecici = Path(tempfile.mkdtemp(prefix="eaglepdf_ocrdogrula_"))
    try:
        shutil.copyfile(yol, gecici / f"{kod}.traineddata")
        doc = pymupdf.open()
        try:
            doc.new_page(width=200, height=100).get_textpage_ocr(language=kod, tessdata=str(gecici), full=True, dpi=72)
        except Exception:
            raise BelgeHatasi("Dil dosyası yüklenemedi: bozuk ya da eksik indirilmiş olabilir.") from None
        finally:
            doc.close()
    finally:
        shutil.rmtree(gecici, ignore_errors=True)


def _yerine_koy(gecici: Path, hedef: Path):
    os.replace(gecici, hedef)


def indir(kod: str, kalite: str = "fast", hedef_klasor=None, ilerleme=None, acici=None) -> Path:
    """`kod` dilinin verisini indirip doğrular ve `hedef_klasor`e (varsayılan: kullanıcı tessdata klasörü) koyar.
    `ilerleme(okunan, toplam)` True dönerse iptal edilir. `acici(url)`: ağ açıcısı (testler için); varsayılan urllib."""
    if kod not in KATALOG:
        raise BelgeHatasi(f"“{kod}” indirilebilen diller arasında yok.")
    if kalite not in KALITELER:
        raise BelgeHatasi(f"Bilinmeyen kalite: {kalite}")
    klasor = Path(hedef_klasor) if hedef_klasor else ocr.kullanici_tessdata()
    klasor.mkdir(parents=True, exist_ok=True)
    url = DEPO_URL.format(depo=KALITELER[kalite][1], kod=kod)
    gecici = klasor / f".{kod}.indirme"
    try:
        try:
            cevap = (acici or _varsayilan_acici)(url)
        except (urllib.error.URLError, TimeoutError, OSError) as h:
            raise BelgeHatasi(f"İndirilemedi: {getattr(h, 'reason', h)}. İnternet bağlantınızı denetleyin ya da "
                              "dil dosyasını elle ekleyin (“Dosyadan Ekle”).") from None
        with cevap:
            sunucu = urlparse(cevap.geturl()).hostname or ""
            if sunucu not in IZINLI_SUNUCULAR:
                raise BelgeHatasi(f"Beklenmeyen sunucuya yönlendirildi ({sunucu}); indirme iptal edildi.")
            toplam = int(cevap.headers.get("Content-Length") or 0)
            if toplam > EN_COK_BAYT:
                raise BelgeHatasi("İndirilecek dosya beklenenden çok büyük; iptal edildi.")
            okunan = 0
            with open(gecici, "wb") as f:
                while True:
                    try:
                        parca = cevap.read(BLOK)
                    except (urllib.error.URLError, TimeoutError, OSError) as h:
                        raise BelgeHatasi(f"İndirme kesildi: {getattr(h, 'reason', h)}") from None
                    if not parca:
                        break
                    okunan += len(parca)
                    if okunan > EN_COK_BAYT:
                        raise BelgeHatasi("İndirilen dosya beklenenden çok büyük; iptal edildi.")
                    f.write(parca)
                    if ilerleme and ilerleme(okunan, toplam):
                        raise IndirmeIptal("İndirme iptal edildi.")
        if toplam and okunan != toplam:
            raise BelgeHatasi("İndirme eksik kaldı (dosya tam gelmedi); yeniden deneyin.")
        dogrula(gecici, kod)   # geçersizse mevcut dosyaya dokunulmaz
        hedef = klasor / f"{kod}.traineddata"
        _yerine_koy(gecici, hedef)
        return hedef
    finally:
        gecici.unlink(missing_ok=True)


def _varsayilan_acici(url: str):
    istek = urllib.request.Request(url, headers={"User-Agent": APP_NAME})
    return urllib.request.urlopen(istek, timeout=30)


def dosyadan_ekle(kaynak, hedef_klasor=None) -> Path:
    """Elinizdeki bir `*.traineddata` dosyasını doğrulayıp kullanıcı klasörüne kopyalar (internetsiz kurulum)."""
    kaynak = Path(kaynak)
    if kaynak.suffix.lower() != ".traineddata":
        raise BelgeHatasi("Dil dosyası “…traineddata” uzantılı olmalı (örn. tur.traineddata).")
    kod = kaynak.name[: -len(".traineddata")]
    if not kod_gecerli_mi(kod):
        raise BelgeHatasi(f"Dil kodu geçersiz: “{kod}”. Dosya adı tur.traineddata gibi olmalı.")
    if not kaynak.is_file():
        raise BelgeHatasi(f"Dosya bulunamadı: {kaynak}")
    dogrula(kaynak, kod)
    klasor = Path(hedef_klasor) if hedef_klasor else ocr.kullanici_tessdata()
    klasor.mkdir(parents=True, exist_ok=True)
    gecici = klasor / f".{kod}.kopya"
    try:
        shutil.copyfile(kaynak, gecici)
        hedef = klasor / f"{kod}.traineddata"
        _yerine_koy(gecici, hedef)
        return hedef
    except OSError as h:
        raise BelgeHatasi(f"Dil dosyası kopyalanamadı: {h}") from None
    finally:
        gecici.unlink(missing_ok=True)


@dataclass
class KuruluDil:
    kod: str
    yol: Path
    boyut: int
    kullanici_klasorunde: bool   # silinebilir (Program Files / TESSDATA_PREFIX klasörlerine dokunulmaz)

    @property
    def ad(self) -> str:
        return dil_adi(self.kod)


def kurulu(klasorler: list[Path] | None = None) -> list[KuruluDil]:
    """Bulunan dil dosyaları; aynı kod birden çok yerdeyse OCR'ın kullanacağı ilk bulunan listelenir (`osd` hariç)."""
    aranacak = klasorler if klasorler is not None else ocr.tessdata_adaylari()
    kullanici = ocr.kullanici_tessdata().resolve() if klasorler is None else None
    gorulen: dict[str, KuruluDil] = {}
    for k in aranacak:
        if not Path(k).is_dir():
            continue
        for f in sorted(Path(k).glob("*.traineddata")):
            kod = f.name[: -len(".traineddata")]
            if kod == "osd" or kod in gorulen or not kod_gecerli_mi(kod):
                continue
            ozel = kullanici is not None and Path(k).resolve() == kullanici
            gorulen[kod] = KuruluDil(kod, f, f.stat().st_size, ozel if kullanici is not None else True)
    oncelik = {"tur": 0, "eng": 1}   # Türkçe ve İngilizce başta, gerisi alfabetik
    return sorted(gorulen.values(), key=lambda d: (oncelik.get(d.kod, 2), d.kod))


def sil(kod: str, klasor=None) -> bool:
    """Kullanıcı klasöründeki dil dosyasını siler. Başka klasördekilere (sistem kurulumu) dokunulmaz → BelgeHatasi."""
    klasor = Path(klasor) if klasor else ocr.kullanici_tessdata()
    if not kod_gecerli_mi(kod):
        raise BelgeHatasi(f"Dil kodu geçersiz: {kod}")
    yol = klasor / f"{kod}.traineddata"
    if not yol.is_file():
        raise BelgeHatasi(f"“{dil_adi(kod)}” dil verisi kullanıcı klasöründe yok; sistem klasöründeki dosyalar buradan silinmez.")
    yol.unlink()
    return True
