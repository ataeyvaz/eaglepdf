"""1-bit (siyah-beyaz) taranmış sayfalarda filigran: sayfalar arası AYNI PİKSEL deseni.

Gri/renkli taramalarda filigran yarı ton pikseldir (`raster.py`); 1-bit sayfada yalnızca siyah ve beyaz vardır. Burada filigran,
aynı boyuttaki sayfaların çoğunda AYNI piksellerin siyah olmasıyla bulunur (içerik sayfadan sayfaya değişir, filigran değişmez).
Bu yöntem; dijital olarak üretilmiş 1-bit PDF'lerde (yazıcıya/PDF'e siyah-beyaz çıktı, dönüştürülmüş kitap/ders notu) çalışır.
Sayfalar tarayıcıdan tek tek, birkaç piksel kaymayla geldiyse pikseller hizalı olmaz ve filigran bulunamaz (kayma düzeltmesi yok).

Temizlik: yalnızca ortak desen piksellerinden siyah olanlar beyaza çevrilir; filigranın dışındaki yazıya dokunulmaz, filigranla
çakışan yazı pikselleri küçük bir kayba uğrayabilir. Sonuç 1-bit olarak yeniden yazılır.
Güvenlik: sonuç deneyseldir; bulgu otomatik seçilmez, önizlemede kontrol edilmelidir.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import cv2
import numpy as np
import pymupdf as fitz

PRESENT_FRAC = 0.6       # piksel sayfaların bu oranında siyahsa ortak desene girer
MIN_PAGES = 3            # güvenilir "sayfalar arası ortak" sonucu için en az sayfa
MIN_SIDE_FRAC = 0.025    # bileşenin kısa kenarı sayfa kısa kenarının en az bu kadarı (ince çizgi, tekrar eden başlık/gövde yazısı elenir; filigran harfi iri olur)
MIN_AREA_FRAC = 0.0004   # bileşen alanı sayfa alanının en az bu kadarı
MAX_AREA_FRAC = 0.5


@dataclass
class BilevelModel:
    mask: np.ndarray          # tam çözünürlükte ortak filigran pikselleri (bool, True = filigran)
    size: tuple               # (genişlik, yükseklik) piksel
    bilevel: bool = True


def kara_piksel(doc: fitz.Document, xref: int) -> np.ndarray | None:
    """Resmi tam çözünürlükte bool dizi (True = siyah) olarak okur; stencil maskeleri desteklenmez (None)."""
    if doc.xref_get_key(xref, "ImageMask")[1] == "true":
        return None
    pix = fitz.Pixmap(doc, xref)
    if pix.alpha:
        pix = fitz.Pixmap(pix, 0)
    if pix.n != 1:
        pix = fitz.Pixmap(fitz.csGRAY, pix)
    arr = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w)
    return arr < 128


def _buyuk_bilesenler(mask: np.ndarray) -> np.ndarray:
    """Ortak desenden: ince çizgi, tekrar eden küçük başlık yazısı ve dev kutuları eler; filigran harfi/logosu büyük şekillerdir."""
    h, w = mask.shape
    kapali = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(kapali, connectivity=8)
    keep = np.zeros(n, bool)
    for i in range(1, n):
        x, y, bw, bh, area = stats[i]
        if min(bw, bh) < MIN_SIDE_FRAC * min(h, w):
            continue
        if not (MIN_AREA_FRAC * h * w <= area <= MAX_AREA_FRAC * h * w):
            continue
        keep[i] = True
    return keep[lab] & mask      # yalnızca gerçekten ortak olan pikseller (kapama dolgusu değil)


def analyze(doc: fitz.Document, bilevel: dict, progress=None, cancel=None):
    """bilevel: {sayfa: (xref, kutu, bpc)}. Döner: (BilevelModel, [(sayfa, bbox, kapsama)]) ya da None."""
    progress = progress or (lambda *a: None)
    sayfalar = sorted(bilevel)
    if len(sayfalar) < MIN_PAGES:
        return None
    boyutlar = Counter()
    for p in sayfalar:
        xref = bilevel[p][0]
        boyutlar[(int(doc.xref_get_key(xref, "Width")[1] or 0), int(doc.xref_get_key(xref, "Height")[1] or 0))] += 1
    (w, h), adet = boyutlar.most_common(1)[0]
    if not w or not h or adet < MIN_PAGES:
        return None
    sayac = np.zeros((h, w), np.uint16)
    kullanilan = []
    for k, p in enumerate(sayfalar):
        if cancel and cancel():
            raise InterruptedError
        progress(k, len(sayfalar), f"1-bit sayfa {p + 1} inceleniyor")
        try:
            kara = kara_piksel(doc, bilevel[p][0])
        except Exception:  # noqa: BLE001 - okunamayan resim: bu sayfa katılmaz
            continue
        if kara is None or kara.shape != (h, w):
            continue
        sayac += kara
        kullanilan.append(p)
    if len(kullanilan) < MIN_PAGES:
        return None
    ortak = sayac >= PRESENT_FRAC * len(kullanilan)
    ortak = _buyuk_bilesenler(ortak)
    if not ortak.any():
        return None
    model = BilevelModel(ortak, (w, h))
    ys, xs = np.nonzero(ortak)
    toplam = int(ortak.sum())
    occ = []
    for p in kullanilan:
        kara = kara_piksel(doc, bilevel[p][0])
        kapsama = float((kara & ortak).sum() / toplam)
        if kapsama < 0.5:
            continue
        r = bilevel[p][1]
        sx, sy = r.width / w, r.height / h
        bbox = (r.x0 + xs.min() * sx, r.y0 + ys.min() * sy, r.x0 + (xs.max() + 1) * sx, r.y0 + (ys.max() + 1) * sy)
        occ.append((p, tuple(round(v, 2) for v in bbox), kapsama))
    return (model, occ) if occ else None


def clean_page(doc: fitz.Document, page: fitz.Page, xref: int, model: BilevelModel) -> bool:  # noqa: ARG001
    """Sayfa resminde ortak desen piksellerini beyaza çevirir; resmi 1-bit olarak aynı nesneye yazar."""
    kara = kara_piksel(doc, xref)
    if kara is None or kara.shape != (model.size[1], model.size[0]):
        return False
    silinecek = kara & model.mask
    if not silinecek.any():
        return False
    kara = kara & ~model.mask
    beyaz_bitleri = np.packbits((~kara).astype(np.uint8), axis=1)     # PDF DeviceGray 1 bit: 1 = beyaz, satırlar bayta tamamlanır
    doc.update_stream(xref, beyaz_bitleri.tobytes(), compress=True)
    doc.xref_set_key(xref, "Filter", "/FlateDecode")
    for key, val in (("DecodeParms", "null"), ("Decode", "null"), ("SMask", "null"), ("Mask", "null"),
                     ("BitsPerComponent", "1"), ("ColorSpace", "/DeviceGray"),
                     ("Width", str(kara.shape[1])), ("Height", str(kara.shape[0]))):
        doc.xref_set_key(xref, key, val)
    return True
