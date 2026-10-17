"""Resim dosyalarından (PNG, JPEG, BMP, TIFF, WEBP, GIF) OCR: metin çıkarır ve aranabilir PDF üretir (Qt'siz).

Akış: her resim (çok kareli TIFF/GIF'te her kare) EXIF yönü düzeltilip saydamlığı beyaza düzleştirilerek A4 sayfaya konur →
tek bellek içi PDF → `Belge.aranabilir_yap` (Tesseract) → sayfa sayfa metin + görünmez metin katmanlı PDF baytları.
Bozuk bir resim diğerlerini durdurmaz (hatalar listelenir). Belge/dosya diske yazılmaz; kaydetmeyi çağıran yapar.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

from . import donustur, ocr
from .belge import SAYFA_BOYUTLARI, Belge
from .hatalar import BelgeHatasi

RESIM_UZANTILARI = donustur.GIRDI_RESIM_UZANTILARI   # (.png .jpg .jpeg .bmp .gif .tif .tiff .webp)
EN_COK_KARE = 200   # tek dosyadaki çok kareli TIFF/GIF için üst sınır


def resim_mi(yol) -> bool:
    return Path(str(yol)).suffix.lower() in RESIM_UZANTILARI


def kare_sayisi(yol) -> int:
    """Dosyadaki kare (sayfa) sayısı: tek resimde 1; çok kareli TIFF/GIF'te n (en çok `EN_COK_KARE`)."""
    Image = donustur._pillow()
    try:
        with Image.open(yol) as im:
            if im.width * im.height > donustur.EN_COK_PIKSEL:
                raise BelgeHatasi(f"Resim çok büyük ({Path(yol).name}): {im.width}×{im.height} piksel.")
            return max(1, min(getattr(im, "n_frames", 1), EN_COK_KARE))
    except OSError as h:
        raise BelgeHatasi(f"Resim açılamadı ({Path(yol).name}): {h}") from None


@dataclass
class SayfaMetni:
    kaynak: str   # dosya adı
    kare: int     # çok kareli dosyada 1 tabanlı kare no; tek resimde 0
    metin: str


@dataclass
class ResimOcrSonucu:
    sayfalar: list[SayfaMetni] = field(default_factory=list)
    pdf: bytes = b""                                   # görünür resim + görünmez metin katmanı
    hatalar: list[str] = field(default_factory=list)   # okunamayan dosyalar ("ad: neden")

    def toplu_metin(self) -> str:
        """Tüm sayfaların metni. Birden çok sayfa varsa her biri “— ad (kare n) —” başlığıyla ayrılır."""
        if len(self.sayfalar) == 1:
            return self.sayfalar[0].metin
        parcalar = []
        for s in self.sayfalar:
            baslik = f"— {s.kaynak}" + (f" (kare {s.kare})" if s.kare else "") + " —"
            parcalar.append(f"{baslik}\n\n{s.metin}".rstrip())
        return "\n\n".join(parcalar)

    @property
    def bos_mu(self) -> bool:
        return not any(s.metin.strip() for s in self.sayfalar)


def resimlerden_ocr(yollar: list, dil: str = ocr.VARSAYILAN_DIL, dpi: int = 300, ilerleme=None) -> ResimOcrSonucu:
    """Resimleri OCR'lar. `ilerleme(n, toplam)` True dönerse `OcrIptal` fırlatılır (hiçbir şey döndürülmez).
    Hiçbir resim okunamazsa `BelgeHatasi`; bazıları okunamazsa sonuçta `hatalar` dolu olur."""
    if not yollar:
        raise BelgeHatasi("Resim seçilmedi.")
    ocr._veriyi_zorunlu_kil(dil)   # dil verisi yoksa anlaşılır hata (resimleri hazırlamadan önce)
    if not 100 <= dpi <= 600:
        raise BelgeHatasi("OCR çözünürlüğü 100–600 DPI arasında olmalı.")
    doc = pymupdf.open()
    etiketler: list[tuple[str, int]] = []
    hatalar: list[str] = []
    try:
        for yol in map(Path, yollar):
            try:
                n_kare = kare_sayisi(yol)
                for kare in range(n_kare):
                    veri, _uz, gp, yp = donustur._resmi_hazirla(yol, kare)
                    sg, sy = SAYFA_BOYUTLARI["A4"]
                    if (gp > yp) != (sg > sy):   # resim yataysa sayfa da yatay
                        sg, sy = sy, sg
                    sayfa = doc.new_page(width=sg, height=sy)
                    sayfa.insert_image(sayfa.rect, stream=veri, keep_proportion=True)
                    etiketler.append((yol.name, kare + 1 if n_kare > 1 else 0))
            except BelgeHatasi as h:
                hatalar.append(f"{yol.name}: {h}")
            except (ValueError, EOFError) as h:   # PIL: bozuk kare / seek hatası
                hatalar.append(f"{yol.name}: okunamadı ({h})")
        if doc.page_count == 0:
            raise BelgeHatasi("Okunabilir resim bulunamadı.\n" + "\n".join(hatalar))
        belge = Belge(doc, None)
        belge.aranabilir_yap(None, dil, dpi=dpi, ilerleme=ilerleme)   # OcrIptal buradan çıkar
        belge._gecmis.temizle()   # geçici belge: geri al görüntüsü (bellek) tutulmasın
        sonuc = ResimOcrSonucu(hatalar=hatalar)
        for i, (ad, kare) in enumerate(etiketler):
            sonuc.sayfalar.append(SayfaMetni(ad, kare, doc[i].get_text("text", sort=True).replace("\xa0", " ").strip()))
        sonuc.pdf = doc.tobytes(garbage=3, deflate=True)
        return sonuc
    finally:
        doc.close()
