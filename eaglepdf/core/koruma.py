"""Belge koruma: parola ekle / kaldır, izinler (Qt'siz).

Şifreli çıktı her zaman yeni bir dosyaya (geçici dosya → yerine koy) yazılır; açık belge değişmez.
"""
from __future__ import annotations

from pathlib import Path

import pymupdf

from .belge import Belge, _gecici_yaz
from .hatalar import BelgeHatasi

# Kullanıcıya görünen izin adı → PyMuPDF izin biti
IZINLER = {
    "yazdir": pymupdf.PDF_PERM_PRINT,
    "duzenle": pymupdf.PDF_PERM_MODIFY,
    "kopyala": pymupdf.PDF_PERM_COPY,
    "aciklama": pymupdf.PDF_PERM_ANNOTATE,
    "form": pymupdf.PDF_PERM_FORM,
    "erisilebilirlik": pymupdf.PDF_PERM_ACCESSIBILITY,
    "sayfa_duzenle": pymupdf.PDF_PERM_ASSEMBLE,
    "yuksek_kalite_yazdir": pymupdf.PDF_PERM_PRINT_HQ,
}
TUM_IZINLER = {ad: True for ad in IZINLER}


def _izin_degeri(izinler: dict[str, bool] | None) -> int:
    izinler = {**TUM_IZINLER, **(izinler or {})}
    bilinmeyen = set(izinler) - set(IZINLER)
    if bilinmeyen:
        raise BelgeHatasi(f"Bilinmeyen izin: {', '.join(sorted(bilinmeyen))}")
    deger = 0
    for ad, acik in izinler.items():
        if acik:
            deger |= IZINLER[ad]
    return deger


def sifreli_mi(belge: Belge) -> bool:
    """Belge (açılmış hâliyle) şifreli bir dosyadan mı geldi?"""
    # `is_encrypted` açma parolası boşsa False kalır; şifreleme bilgisi üst veride durur
    return bool(belge._doc.is_encrypted or belge._doc.metadata.get("encryption"))


def mevcut_izinler(belge: Belge) -> dict[str, bool]:
    """Belgenin izin durumu (sahip olarak açılmışsa hepsi açık görünür). Şifresiz belgede hepsi açıktır."""
    izin = belge._doc.permissions
    return {ad: bool(izin & bit) for ad, bit in IZINLER.items()}


def parola_ekle(belge: Belge, hedef, acma_parolasi: str = "", sahip_parolasi: str = "",
                izinler: dict[str, bool] | None = None) -> Path:
    """AES-256 ile korumalı bir kopya yazar.

    `acma_parolasi`: belgeyi açmak için sorulur (boşsa herkes açar, yalnızca izinler uygulanır).
    `sahip_parolasi`: izinleri aşmak/kaldırmak için (boşsa açma parolasıyla aynı yapılır).
    En az biri verilmelidir. Kaynak dosyanın üzerine yazılmaz."""
    hedef = Path(hedef)
    if not acma_parolasi and not sahip_parolasi:
        raise BelgeHatasi("En az bir parola girin.")
    if belge.yol and hedef.resolve() == belge.yol.resolve():
        raise BelgeHatasi("Korumalı kopya, açık dosyanın üzerine yazılamaz; “Farklı Kaydet” gibi yeni bir ad seçin.")
    sahip = sahip_parolasi or acma_parolasi
    izin = _izin_degeri(izinler)

    def yaz(gecici: str):
        kopya = pymupdf.open("pdf", belge._doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_NONE))
        try:
            kopya.save(gecici, garbage=3, deflate=True, encryption=pymupdf.PDF_ENCRYPT_AES_256,
                       user_pw=acma_parolasi, owner_pw=sahip, permissions=izin)
        finally:
            kopya.close()

    _gecici_yaz(yaz, hedef)
    return hedef


def parola_kaldir(belge: Belge, hedef) -> Path:
    """Parolasız (şifresiz) bir kopya yazar. Belge zaten parolayla açılmış olmalıdır."""
    hedef = Path(hedef)
    if belge.yol and hedef.resolve() == belge.yol.resolve():
        raise BelgeHatasi("Parolasız kopya, açık dosyanın üzerine yazılamaz; yeni bir ad seçin.")

    def yaz(gecici: str):
        kopya = pymupdf.open("pdf", belge._doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_NONE))
        try:
            kopya.save(gecici, garbage=3, deflate=True, encryption=pymupdf.PDF_ENCRYPT_NONE)
        finally:
            kopya.close()

    _gecici_yaz(yaz, hedef)
    return hedef


def sahip_parolasi_dogru_mu(yol, parola: str) -> bool:
    """Dosya `parola` ile *sahip* olarak açılabiliyor mu? (PyMuPDF `authenticate` 4/6 = sahip)"""
    doc = pymupdf.open(yol)
    try:
        # açma parolası boş olsa da sahip parolası authenticate ile denenebilir (4 = sahip, 6 = ikisi de)
        return doc.authenticate(parola) in (4, 6)
    finally:
        doc.close()
