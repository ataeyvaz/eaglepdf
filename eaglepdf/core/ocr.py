"""OCR: taranmış sayfaları aranabilir yapma ve bölgeden metin çıkarma (Qt'siz).

Motor: PyMuPDF'in içindeki Tesseract (Apache-2.0); yalnızca dil verisi (`*.traineddata`) gerekir, `tesseract.exe` gerekmez.
Dil verisi sırayla şurada aranır: `%APPDATA%\\<APP_NAME>\\tessdata`, `TESSDATA_PREFIX`, `C:\\Program Files\\Tesseract-OCR\\tessdata`.
Türkçe (`tur`) varsayılandır.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from .. import APP_NAME
from . import yazitipi
from .gecmis import geri_alinabilir
from .hatalar import BelgeHatasi

VARSAYILAN_DIL = "tur+eng"
DILLER = {"tur": "Türkçe", "eng": "İngilizce"}
VARSAYILAN_DPI = 200


class OcrIptal(BelgeHatasi):
    """Kullanıcı OCR işlemini iptal etti."""


def kullanici_tessdata() -> Path:
    return Path(os.environ.get("APPDATA", Path.home())) / APP_NAME / "tessdata"


def tessdata_adaylari() -> list[Path]:
    adaylar = [kullanici_tessdata()]
    if os.environ.get("TESSDATA_PREFIX"):
        adaylar.append(Path(os.environ["TESSDATA_PREFIX"]))
    adaylar.append(Path(r"C:\Program Files\Tesseract-OCR\tessdata"))
    return adaylar


def tessdata_bul(dil: str = VARSAYILAN_DIL) -> Path | None:
    """`dil` ("tur+eng") içindeki tüm dillerin verisini barındıran ilk klasör; yoksa None."""
    gerekli = [d for d in dil.split("+") if d]
    for k in tessdata_adaylari():
        if k.is_dir() and all((k / f"{d}.traineddata").is_file() for d in gerekli):
            return k
    return None


def kullanilabilir_diller() -> list[str]:
    """Hiçbir yerde bulunan dil kodları (ilk bulunan klasöre öncelik verilir)."""
    bulunan: list[str] = []
    for k in tessdata_adaylari():
        if k.is_dir():
            for f in sorted(k.glob("*.traineddata")):
                if f.stem != "osd" and f.stem not in bulunan:
                    bulunan.append(f.stem)
    return bulunan


def hazir_mi(dil: str = VARSAYILAN_DIL) -> bool:
    return tessdata_bul(dil) is not None


def _veriyi_zorunlu_kil(dil: str) -> Path:
    k = tessdata_bul(dil)
    if k is None:
        raise BelgeHatasi(
            f"OCR için “{dil}” dil verisi bulunamadı. `tur.traineddata` dosyasını şu klasöre koyun:\n{kullanici_tessdata()}")
    return k


@dataclass
class OcrSonucu:
    islenen: int = 0
    atlanan_metinli: int = 0
    atlanan_dondurulmus: int = 0
    kelime: int = 0


def sayfa_kelimeleri(sayfa: pymupdf.Page, dil: str, dpi: int = VARSAYILAN_DPI,
                     tessdata: Path | None = None) -> list[tuple[pymupdf.Rect, str]]:
    tessdata = tessdata or _veriyi_zorunlu_kil(dil)
    tp = sayfa.get_textpage_ocr(language=dil, dpi=dpi, full=True, tessdata=str(tessdata))
    sonuc = []
    for x0, y0, x1, y1, kelime, *_ in sayfa.get_text("words", textpage=tp):
        if kelime.strip():
            sonuc.append((pymupdf.Rect(x0, y0, x1, y1), kelime))
    return sonuc


class OcrIslemleri:
    """`Belge`ye karışım olarak eklenir (`_doc`, `_gecmis`, `degisti` üyelerini kullanır)."""

    def metinsiz_sayfalar(self, sayfalar: list[int] | None = None) -> list[int]:
        liste = range(self._doc.page_count) if sayfalar is None else sayfalar
        return [i for i in liste if not self._doc[i].get_text().strip()]

    def aranabilir_yap(self, sayfalar: list[int] | None = None, dil: str = VARSAYILAN_DIL,
                       dpi: int = VARSAYILAN_DPI, metinli_sayfalari_da: bool = False, ilerleme=None) -> OcrSonucu:
        """Sayfalara görünmez bir metin katmanı ekler (görüntü aynı kalır). Metni olan sayfalar atlanır.
        `ilerleme(n, toplam)` True dönerse iptal edilir; iptalde belge değişmez."""
        tessdata = _veriyi_zorunlu_kil(dil)
        liste = list(range(self._doc.page_count)) if sayfalar is None else list(sayfalar)
        sonuc = OcrSonucu()
        bulunan: dict[int, list] = {}
        for n, i in enumerate(liste):
            if ilerleme and ilerleme(n, len(liste)):
                raise OcrIptal("İşlem iptal edildi.")
            sayfa = self._doc[i]
            if not metinli_sayfalari_da and sayfa.get_text().strip():
                sonuc.atlanan_metinli += 1
                continue
            if sayfa.rotation:
                sonuc.atlanan_dondurulmus += 1
                continue
            kelimeler = sayfa_kelimeleri(sayfa, dil, dpi, tessdata)
            bulunan[i] = kelimeler
            sonuc.islenen += 1
            sonuc.kelime += len(kelimeler)
        if ilerleme and ilerleme(len(liste), len(liste)):
            raise OcrIptal("İşlem iptal edildi.")
        if bulunan:
            self._ocr_katmani_yaz(bulunan)
        return sonuc

    @geri_alinabilir
    def _ocr_katmani_yaz(self, bulunan: dict[int, list]):
        font = yazitipi.font()
        for i, kelimeler in bulunan.items():
            sayfa = self._doc[i]
            tw = pymupdf.TextWriter(sayfa.rect)
            for r, kelime in kelimeler:
                boyut = max(r.height * 0.9, 1.0)
                uzunluk = font.text_length(kelime, fontsize=boyut)
                if uzunluk > r.width > 0:
                    boyut *= r.width / uzunluk  # kutudan taşmasın (seçim/arama için yeterli)
                tw.append((r.x0, r.y1 - r.height * 0.2), kelime, font=font, fontsize=max(boyut, 1.0))
            tw.write_text(sayfa, render_mode=3)  # 3 = görünmez

    def bolgeden_metin(self, sayfa: int, bolge: tuple[float, float, float, float], dil: str = VARSAYILAN_DIL,
                       dpi: int = 300) -> str:
        """Sayfadaki dikdörtgenin (sayfa noktası cinsinden) görüntüsünü OCR'layıp metni döndürür; belge değişmez."""
        tessdata = _veriyi_zorunlu_kil(dil)
        kes = pymupdf.Rect(bolge) & self._doc[sayfa].rect
        if kes.is_empty:
            return ""
        pix = self._doc[sayfa].get_pixmap(dpi=dpi, clip=kes)
        gecici = pymupdf.open()
        try:
            s = gecici.new_page(width=kes.width, height=kes.height)
            s.insert_image(s.rect, pixmap=pix)
            tp = s.get_textpage_ocr(language=dil, dpi=dpi, full=True, tessdata=str(tessdata))
            return s.get_text("text", textpage=tp).replace("\xa0", " ").strip()
        finally:
            gecici.close()
