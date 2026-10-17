"""Filigran yazısını okuma (OCR): taranmış sayfa filigranları ve resim/logo filigranları için.

Motor: Tesseract (PyMuPDF'in içinde; EaglePDF'in OCR dil verisiyle — `core/ocr.py`). pdfedit'te kullanılan RapidOCR (ONNX)
yerine geçer: Türkçe İ, Ö, Ş gibi harfler artık doğru okunur, ağır `onnxruntime` bağımlılığı gerekmez.
Dil verisi kurulu değilse okuma yapılmaz (`available()` False) ve bulguya açıklayıcı bir neden eklenir; temizleme yine çalışır.

Taranmış sayfalarda filigran tek bir sayfadan değil, sayfaların ortak deseninden okunur: filigran rengine yakın pikseller
sayfalar arasında oylanır, böylece alttaki yazılar silinir ve yalnızca filigranın kendisi kalır. Çapraz filigran döndürülüp
yataya getirilir (180° belirsizliği iki yön denenip daha makul okuma seçilerek çözülür).
"""
from __future__ import annotations

import collections
import logging
import math
import unicodedata

import cv2
import numpy as np
import pymupdf as fitz

from ... import resource_dir
from .. import ocr as ana_ocr

log = logging.getLogger(__name__)

MAX_PAGES = 12           # ortak desen için en fazla bu kadar sayfa kullanılır
MAX_IMAGES = 6           # resim filigranlarından en fazla bu kadarı okunur
HARF_HEDEF = 55          # tek satırlık yazıda Tesseract'ın en iyi okuduğu yaklaşık harf yüksekliği (piksel)
EN_COK_KENAR = 3000      # ölçeklenmiş resmin uzun kenarı için üst sınır (bellek/süre)
DIL_TERCIHI = ("tur+eng", "eng", "tur")


def dil_sec() -> str | None:
    """Kurulu dil verisine göre kullanılacak OCR dili; hiçbiri yoksa None."""
    for d in DIL_TERCIHI:
        if ana_ocr.hazir_mi(d):
            return d
    kurulu = ana_ocr.kullanilabilir_diller()
    return kurulu[0] if kurulu else None


def available() -> bool:
    return dil_sec() is not None


def unavailable_reason() -> str:
    return "" if available() else "OCR dil verisi kurulu değil (OCR → Dil Verisi…)"


def _clean_text(s: str) -> str:
    return " ".join(s.split()).strip(" .,;:-_|")


def _plausible(text: str) -> bool:
    """Rastgele karakter yığınını eler: en az 3 harf ve harflerin payı yeterince yüksek olmalı."""
    harf = sum(c.isalpha() for c in text)
    toplam = len(text.replace(" ", ""))
    return harf >= 3 and toplam > 0 and harf / toplam >= 0.6


def _score(text: str) -> float:
    """Okumanın güvenilirlik puanı (iki yön arasında seçmek için): alfasayısal karakter sayısı × alfasayısal oranı."""
    nz = text.replace(" ", "")
    if not nz:
        return 0.0
    a = sum(c.isalnum() for c in nz)
    return a * a / len(nz)


def _tesseract(gray: np.ndarray, dil: str | None = None, olcek: float = 1.0) -> str:
    """Siyah yazı / beyaz zemin 8-bit gri resmi `olcek` katına getirip Tesseract ile okur (satırlar yukarıdan aşağı).
    Tesseract harf boyuna duyarlıdır (~30–70 px iyi; çok büyük harfte boş döner): ölçeği çağıran seçer."""
    dil = dil or dil_sec()
    if not dil or gray is None or gray.size == 0:
        return ""
    gray = np.ascontiguousarray(gray, dtype=np.uint8)
    if abs(olcek - 1.0) > 1e-3:
        h0, w0 = gray.shape
        yeni = (max(8, int(w0 * olcek)), max(8, int(h0 * olcek)))
        gray = cv2.resize(gray, yeni, interpolation=cv2.INTER_CUBIC if olcek > 1 else cv2.INTER_AREA)
    h, w = gray.shape
    tessdata = ana_ocr.tessdata_bul(dil)
    if tessdata is None:
        return ""
    doc = fitz.open()
    try:
        page = doc.new_page(width=w, height=h)   # 1 piksel = 1 pt: dpi=72 resmi olduğu gibi okutur
        page.insert_image(page.rect, pixmap=fitz.Pixmap(fitz.csGRAY, w, h, gray.tobytes(), False))
        tp = page.get_textpage_ocr(language=dil, dpi=72, full=True, tessdata=str(tessdata))
        return _clean_text(page.get_text("text", textpage=tp, sort=True))
    except Exception:  # noqa: BLE001
        log.exception("Tesseract okuması başarısız")
        return ""
    finally:
        doc.close()


def _en_iyi_okuma(gray: np.ndarray, tek_satir: bool) -> str:
    """Birkaç ölçekte okuyup en makul sonucu seçer. `tek_satir`: yazı tek satırsa harf yüksekliği ~HARF_HEDEF olacak ölçekler
    denenir (satır yüksekliği ≈ 2 × harf); değilse resmin kendi ölçeği ile 2× ve 0.5× denenir. Makul bir okuma bulununca durur."""
    h, w = gray.shape
    if tek_satir:
        olcekler = [2 * HARF_HEDEF / h, HARF_HEDEF / h, 4 * HARF_HEDEF / h]
    else:
        olcekler = [1.0, 2.0, 0.5]
    en_iyi = ""
    for o in olcekler:
        if int(h * o) < 8 or int(max(h, w) * o) > EN_COK_KENAR:
            continue
        t = _tesseract(gray, olcek=o)
        if _score(t) > _score(en_iyi):
            en_iyi = t
        if _plausible(t) and sum(c.isalnum() for c in t) >= 4:
            return t
    return en_iyi


def _deskew(mask: np.ndarray) -> np.ndarray | None:
    """Yazı maskesini (bool) yatay hale getirip kırpar; siyah yazı / beyaz zemin döndürür."""
    ys, xs = np.nonzero(mask)
    if len(xs) < 30:
        return None
    pts = np.column_stack([xs, ys]).astype(np.float32)
    (cx, cy), (rw, rh), ang = cv2.minAreaRect(pts)
    if rw < rh:
        ang += 90
    h, w = mask.shape
    m = cv2.getRotationMatrix2D((cx, cy), ang, 1.0)
    cos, sin = abs(m[0, 0]), abs(m[0, 1])
    nw, nh = int(h * sin + w * cos) + 2, int(h * cos + w * sin) + 2
    m[0, 2] += nw / 2 - cx
    m[1, 2] += nh / 2 - cy
    rot = cv2.warpAffine(mask.astype(np.uint8) * 255, m, (nw, nh))
    ys, xs = np.nonzero(rot > 127)
    if len(xs) == 0:
        return None
    rot = rot[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    return cv2.copyMakeBorder(255 - rot, 24, 24, 24, 24, cv2.BORDER_CONSTANT, value=255)


def _ikili(gray: np.ndarray) -> np.ndarray:
    """Yumuşatılmış/gürültülü maske kenarlarını temizler: medyan süzgeç + eşik (siyah yazı / beyaz zemin kalır)."""
    return cv2.threshold(cv2.medianBlur(gray, 5), 160, 255, cv2.THRESH_BINARY)[1]


_INGILIZCE = ("the quick brown fox jumps over the lazy dog confidential draft copy original document company publisher editor "
              "editions press books international limited university school education mathematics science history report summary "
              "manual guide license software program permission warranty copyright reserved rights")
_bigramlar: tuple | None = None


def _sade(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", t.lower()) if "a" <= c <= "z")


def _bigram_tablosu() -> tuple[collections.Counter, int]:
    """Türkçe (uygulamanın kendi yardım metni) ve İngilizce örnek metinden harf çifti sıklıkları (ilk kullanımda kurulur)."""
    global _bigramlar
    if _bigramlar is None:
        try:
            metin = (resource_dir() / "yardim.md").read_text(encoding="utf-8")
        except OSError:
            metin = ""
        sayac: collections.Counter = collections.Counter()
        for kelime in f"{metin} {_INGILIZCE}".split():
            k = "^" + _sade(kelime) + "$"
            for i in range(len(k) - 1):
                sayac[k[i:i + 2]] += 1
        _bigramlar = (sayac, sum(sayac.values()))
    return _bigramlar


def _dil_puani(t: str) -> float:
    """Metnin Türkçe/İngilizce'ye benzerliği: harf çiftlerinin ortalama log-olasılığı (yüksek = daha dil benzeri).
    Tesseract güven puanı vermediğinden, ters (180°) okumanın ürettiği makul görünen çöpü doğru okumadan ayırır."""
    sayac, toplam = _bigram_tablosu()
    puan, n = 0.0, 0
    for kelime in t.split():
        k = "^" + _sade(kelime) + "$"
        if len(k) < 4:
            continue
        for i in range(len(k) - 1):
            puan += math.log((sayac[k[i:i + 2]] + 1) / (toplam + 28 * 28))
            n += 1
    return puan / n if n else -99.0


def _anahtar(t: str) -> str:
    """Okumaları karşılaştırmak için: aksan/İ-I farkı, büyük-küçük harf ve boşluklar yok sayılır."""
    ayrik = unicodedata.normalize("NFKD", t)
    return "".join(c.lower() for c in ayrik if c.isalnum())


def read_text_image(gray: np.ndarray) -> str:
    """Siyah yazı / beyaz zemin bir resimden en iyi okumayı döndürür.

    Düz ve 180° dönük, ham ve eşiklenmiş varyantlar okunur; aralarından **dile en çok benzeyeni** seçilir (`_dil_puani`):
    yanlış yönde Tesseract makul görünen ama anlamsız bir harf yığını üretir ve uzunluk/harf oranı bunu ayırt etmez.
    Beraberlikte düz yön tercih edilir."""
    if not available() or gray is None or gray.size == 0:
        return ""
    adaylar = []   # (dil puanı, yön tercihi: düz=0 > ters=-1, metin)
    for sira, yon in enumerate((gray, cv2.rotate(gray, cv2.ROTATE_180))):
        for im in (yon, _ikili(yon)):
            h, w = im.shape
            t = _en_iyi_okuma(im, tek_satir=w / max(1, h) >= 2.5)
            if _plausible(t):
                adaylar.append((_dil_puani(t), -sira, t))
    return max(adaylar)[2] if adaylar else ""


# --------------------------------------------------------------------------- taranmış sayfa

def raster_watermark_mask(doc: fitz.Document, finding) -> np.ndarray | None:
    """Sayfaların ortak filigran deseni (çalışma çözünürlüğünde bool maske)."""
    from . import raster
    model = finding.data["model"]
    occs = finding.occurrences[:MAX_PAGES]
    if not occs:
        return None
    acc = np.zeros(model.region.shape, np.float32)
    n = 0
    for o in occs:
        try:
            img, _ = raster.load_rgb(doc, o.data["xref"])
        except Exception:  # noqa: BLE001
            continue
        w = raster._work(img, model.work_size)
        acc += raster.near_color(w, model.color, model.params.tol)
        n += 1
    if not n:
        return None
    acc /= n
    region = cv2.dilate(model.region.astype(np.uint8), raster._kernel(7)) > 0
    return (acc >= (0.5 if n >= 3 else 0.99)) & region


def read_raster(doc: fitz.Document, finding) -> str:
    if not available():
        return ""
    mask = raster_watermark_mask(doc, finding)
    if mask is None:
        return ""
    img = _deskew(mask)
    text = read_text_image(img) if img is not None else ""
    if not text:                                  # döşeme (çok kopyalı) filigran: döndürmeden dene
        t = _en_iyi_okuma(255 - mask.astype(np.uint8) * 255, tek_satir=False)
        text = t if _plausible(t) else ""
    return text


# --------------------------------------------------------------------------- resim filigranı

def read_image(doc: fitz.Document, xref: int) -> str:
    """Resim (logo) içindeki yazıyı okur. Saydam alanlar beyaz zemin kabul edilir."""
    if not available():
        return ""
    try:
        pix = fitz.Pixmap(doc, xref)
        if pix.n - pix.alpha not in (1, 3):
            pix = fitz.Pixmap(fitz.csRGB, pix)
        arr = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w, pix.n).astype(np.float32)
        if pix.alpha:
            a = arr[..., -1:] / 255.0
            arr = arr[..., :-1] * a + 255 * (1 - a)
        gray = arr.mean(axis=2).astype(np.uint8) if arr.shape[2] > 1 else arr[..., 0].astype(np.uint8)
    except Exception:  # noqa: BLE001
        return ""
    h, w = gray.shape
    if min(h, w) < 12:
        return ""
    s = min(1.0, 1600 / max(h, w))
    if s < 1:
        gray = cv2.resize(gray, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
    # açık renkli (soluk) logolarda kontrastı aç
    lo, hi = np.percentile(gray, [1, 99])
    if hi - lo > 10:
        gray = np.clip((gray.astype(np.float32) - lo) * 255 / (hi - lo), 0, 255).astype(np.uint8)
    if gray.mean() < 110:                         # koyu zemin üstünde açık yazı
        gray = 255 - gray
    gray = cv2.copyMakeBorder(gray, 16, 16, 16, 16, cv2.BORDER_CONSTANT, value=255)
    hh, ww = gray.shape
    text = _en_iyi_okuma(gray, tek_satir=ww / max(1, hh) >= 3)
    return text if _plausible(text) else ""
