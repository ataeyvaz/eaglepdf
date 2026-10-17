"""Taranmış (her sayfası tek resim olan) PDF'lerde piksel tabanlı filigran tespiti ve temizliği.

Tespit: Filigran her sayfada aynı yerdedir, içerik ise değişir. Sayfa resimleri küçültülüp üst üste
konur; çoğu sayfada aynı yerde bulunan yarı ton (ne beyaz ne siyah) pikseller aday olur. İnce çizgiler,
küçük yazılar (morfolojik açma ile) ve dolu dikdörtgenler (başlık bantları; doluluk oranı ile) elenir.

Temizlik ("un-blend"): Yarı saydam filigran alttaki pikseli çarpma (multiply) ile koyulaştırır:
    görünen = zemin × k      (k = filigran rengi / 255)
Maske içinde  zemin = görünen / k  hesaplanır. Böylece filigranın altındaki yazı ve renkler korunur;
siyah yazı siyah kalır, yalnızca filigranın kattığı koyuluk geri alınır.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import pymupdf as fitz
import numpy as np

WORK_SIDE = 900          # tespitte kullanılan çalışma çözünürlüğü (uzun kenar, piksel)
SCAN_COVER = 0.80        # sayfanın bu kadarını kaplayan resim varsa sayfa "taranmış" sayılır
MAX_VISIBLE_CHARS = 30   # taranmış sayfada görünür (OCR olmayan) metin üst sınırı


@dataclass
class RasterParams:
    tol: int = 45            # filigran rengine benzerlik toleransı (0-255) – "alan hassasiyeti"
    strength: float = 1.0    # silme gücü (1.0 = tam un-blend)


@dataclass
class RasterModel:
    region: np.ndarray       # çalışma çözünürlüğünde filigran bölgesi (bool)
    color: np.ndarray        # filigranın beyaz zemin üzerindeki rengi (RGB, float)
    work_size: tuple         # (genişlik, yükseklik)
    params: RasterParams = field(default_factory=RasterParams)
    consistent: bool = True  # sayfalar arası tutarlılıkla mı bulundu (≥3 sayfa)


# --------------------------------------------------------------------------- yardımcılar

def scanned_image(doc: fitz.Document, page: fitz.Page, visible_chars: int):
    """Sayfa taranmışsa (xref, sayfadaki resim kutusu, bpc) döndürür, değilse None."""
    if visible_chars > MAX_VISIBLE_CHARS:
        return None
    parea = abs(page.rect)
    best = None
    for im in page.get_images(full=True):
        x, bpc = im[0], im[4]
        try:
            rects = page.get_image_rects(x)
        except Exception:
            continue
        for r in rects:
            cover = abs(r & page.rect) / parea if parea else 0
            if cover >= SCAN_COVER and (best is None or cover > best[3]):
                best = (x, fitz.Rect(r), bpc, cover)
    return best[:3] if best else None


def is_jpeg(doc: fitz.Document, xref: int) -> bool:
    return "DCTDecode" in doc.xref_get_key(xref, "Filter")[1]


def load_rgb(doc: fitz.Document, xref: int):
    """Resmi RGB uint8 numpy dizisi olarak döndürür; (dizi, gri_mi)."""
    pix = fitz.Pixmap(doc, xref)
    if pix.alpha:
        pix = fitz.Pixmap(pix, 0)
    gray = pix.n == 1
    if pix.n not in (1, 3):
        pix = fitz.Pixmap(fitz.csRGB, pix)
    arr = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w, pix.n)
    if arr.shape[2] == 1:
        arr = np.repeat(arr, 3, axis=2)
    return np.ascontiguousarray(arr), gray


def _work(img: np.ndarray, size) -> np.ndarray:
    return cv2.resize(img, size, interpolation=cv2.INTER_AREA)


def _work_size(shape) -> tuple:
    h, w = shape[:2]
    s = WORK_SIDE / max(h, w)
    return max(1, int(w * s)), max(1, int(h * s))


def _kernel(n: int) -> np.ndarray:
    n = max(1, int(n))
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (n, n))


def _midtone(img: np.ndarray) -> np.ndarray:
    g = img.mean(axis=2)
    return (g > 110) & (g < 243)


def _filter_components(mask: np.ndarray) -> np.ndarray:
    """Küçük lekeleri ve dolu dikdörtgenleri (bant, kutu) atar; harf benzeri şekilleri bırakır."""
    n, lab, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
    total = mask.shape[0] * mask.shape[1]
    keep = np.zeros(n, bool)
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        fill = area / max(1, w * h)
        if area < 0.0002 * total or area > 0.4 * total:
            continue
        if fill > 0.85 and min(w, h) > 4:      # dolu dikdörtgen: başlık bandı, renkli kutu
            continue
        keep[i] = True
    return keep[lab]


def near_color(img: np.ndarray, color: np.ndarray, tol: int) -> np.ndarray:
    """Pikseller filigran rengine yakın mı? Beyaz zeminin yanlışlıkla eşleşmemesi için piksel,
    filigranın beyaza göre koyuluğunun en az yarısı kadar koyu olmalı."""
    diff = np.abs(img.astype(np.int16) - color.astype(np.int16)).max(axis=2)
    wm_dark = 255.0 - float(np.mean(color))
    dark = 255.0 - img.mean(axis=2)
    return (diff <= tol) & (dark >= 0.5 * wm_dark)


def page_mask(img: np.ndarray, model: RasterModel) -> np.ndarray:
    """Verilen resim (tam çözünürlük) için filigran ağırlık maskesi (0..1, float32)."""
    h, w = img.shape[:2]
    scale = max(h, w) / WORK_SIDE
    region = cv2.resize(model.region.astype(np.uint8), (w, h), interpolation=cv2.INTER_NEAREST)
    # tarama kaymalarına pay: bölgeyi biraz genişlet
    region = cv2.dilate(region, _kernel(4 * scale)) > 0
    near = near_color(img, model.color, model.params.tol) & region
    # filigranın üstünden geçen yazının açtığı delikleri kapat, kenar yumuşatması için genişlet
    near = cv2.morphologyEx(near.astype(np.uint8), cv2.MORPH_CLOSE, _kernel(5 * scale))
    near = cv2.dilate(near, _kernel(1.5 * scale)) & region.astype(np.uint8)
    weight = cv2.GaussianBlur(near.astype(np.float32), (0, 0), max(0.6, 0.8 * scale))
    return np.clip(weight * 1.3, 0, 1)


def unblend(img: np.ndarray, weight: np.ndarray, model: RasterModel) -> np.ndarray:
    k = np.clip(model.color / 255.0, 0.08, 1.0)
    k_eff = 1.0 - (1.0 - k) * model.params.strength
    f = img.astype(np.float32)
    restored = np.clip(f / k_eff, 0, 255)
    out = f * (1 - weight[..., None]) + restored * weight[..., None]
    return out.round().astype(np.uint8)


# --------------------------------------------------------------------------- tespit

def _box_mask(size, img_rect, box) -> np.ndarray:
    """Sayfa koordinatındaki kutuyu çalışma çözünürlüğünde maskeye çevirir."""
    w, h = size
    m = np.zeros((h, w), bool)
    sx, sy = w / img_rect.width, h / img_rect.height
    x0 = int(max(0, (box[0] - img_rect.x0) * sx))
    y0 = int(max(0, (box[1] - img_rect.y0) * sy))
    x1 = int(min(w, np.ceil((box[2] - img_rect.x0) * sx)))
    y1 = int(min(h, np.ceil((box[3] - img_rect.y0) * sy)))
    m[y0:y1, x0:x1] = True
    return m


def analyze(doc: fitz.Document, scanned: dict, progress=None, cancel=None, box=None):
    """scanned: {sayfa: (xref, kutu, bpc)}.  Döner: (RasterModel, [(sayfa, kutu, kapsama)]) ya da None.
    box=(sayfa, (x0, y0, x1, y1)): kullanıcının elle işaretlediği alan; arama bu alanla sınırlanır."""
    progress = progress or (lambda *a: None)
    pages = sorted(p for p, v in scanned.items() if v[2] and v[2] > 1)
    if not pages:
        return None
    size = None
    works = {}
    for k, p in enumerate(pages):
        if cancel and cancel():
            raise InterruptedError
        progress(k, len(pages), f"Taranmış sayfa {p + 1} inceleniyor")
        try:
            img, _ = load_rgb(doc, scanned[p][0])
        except Exception:
            continue
        ws = _work_size(img.shape)
        if size is None:
            size = ws
        elif abs(ws[0] / ws[1] - size[0] / size[1]) > 0.1:
            continue                                   # farklı yönlü sayfa: tutarlılığa katma
        works[p] = _work(img, size)
    if not works:
        return None

    bands = np.stack([_midtone(w) for w in works.values()])
    n = len(works)
    if n >= 3:
        cand = bands.mean(axis=0) >= 0.45
        consistent = True
    else:
        cand = bands[0]
        consistent = False
    min_area = 0.002 * cand.size
    if box is not None:
        bp, brect = box
        if bp not in works:
            return None
        bm = _box_mask(size, scanned[bp][1], brect)
        min_area = max(20, 0.01 * bm.sum())
        if (cand & bm).sum() < min_area:
            # desen sayfaların çoğunda yok: yalnızca işaretlenen sayfaya güven
            cand, consistent = bands[list(works).index(bp)], False
        cand = cand & bm
    cand = cv2.morphologyEx(cand.astype(np.uint8), cv2.MORPH_OPEN, _kernel(3)) > 0
    cand = _filter_components(cand)
    if cand.sum() < min_area:
        return None

    # her pikselin, yarı ton olduğu sayfalardaki ortalama rengi
    stack = np.stack(list(works.values())).astype(np.float32)
    cnt = np.maximum(bands.sum(axis=0), 1)[..., None]
    mean_col = (stack * bands[..., None]).sum(axis=0) / cnt
    # filigran rengi: bileşenleri rengine göre grupla, toplam alanı en büyük grup filigrandır
    # (filigran harfleri ayrı ayrı küçük ama hepsi aynı renktedir; tek bir bant/çizgi ise tek parçadır)
    n_lab, lab, stats, _ = cv2.connectedComponentsWithStats(cand.astype(np.uint8), connectivity=8)
    comps = [(np.median(mean_col[lab == i], axis=0), stats[i, cv2.CC_STAT_AREA]) for i in range(1, n_lab)]
    groups = []                                        # [renk, toplam alan]
    for col, area in comps:
        for g in groups:
            if np.abs(g[0] - col).max() <= RasterParams().tol / 2:
                g[1] += area
                break
        else:
            groups.append([col, area])
    color = max(groups, key=lambda g: g[1])[0]
    # bölgeyi filigran rengiyle tutarlı piksellere daralt (sarı köşe, mavi bant vb. elenir)
    tol0 = RasterParams().tol
    same = np.abs(mean_col - color).max(axis=2) <= tol0
    cand = cv2.morphologyEx((cand & same).astype(np.uint8), cv2.MORPH_OPEN, _kernel(3)) > 0
    cand = _filter_components(cand)
    # filigran harflerine göre çok küçük kalan kırıntıları at
    n_lab, lab, stats, _ = cv2.connectedComponentsWithStats(cand.astype(np.uint8), connectivity=8)
    if n_lab > 1:
        areas = stats[1:, cv2.CC_STAT_AREA]
        keep = np.concatenate([[False], areas >= 0.03 * areas.sum()])
        cand = keep[lab]
    if cand.sum() < min_area:
        return None
    model = RasterModel(cand, color.astype(np.float32), size, consistent=consistent)

    occ = []
    for p, w in works.items():
        coverage = float((near_color(w, model.color, model.params.tol) & cand).sum() / cand.sum())
        if coverage < 0.3:
            continue
        ys, xs = np.nonzero(cand)
        r = scanned[p][1]
        sx, sy = r.width / size[0], r.height / size[1]
        bbox = (r.x0 + xs.min() * sx, r.y0 + ys.min() * sy, r.x0 + (xs.max() + 1) * sx, r.y0 + (ys.max() + 1) * sy)
        occ.append((p, tuple(round(v, 2) for v in bbox), coverage))
    if not occ:
        return None
    return model, occ


# --------------------------------------------------------------------------- temizlik

def clean_page(doc: fitz.Document, page: fitz.Page, xref: int, model: RasterModel) -> bool:  # noqa: ARG001
    """Sayfa resmini filigransız haliyle değiştirir."""
    img, gray = load_rgb(doc, xref)
    weight = page_mask(img, model)
    if weight.max() <= 0:
        return False
    out = unblend(img, weight, model)
    if gray:
        out = cv2.cvtColor(out, cv2.COLOR_RGB2GRAY)
    cs = "/DeviceGray" if gray else "/DeviceRGB"
    # yeni veriyi aynı resim nesnesine yaz (replace_image eski resmi dosyada bırakıyor)
    if is_jpeg(doc, xref):
        enc = out if gray else cv2.cvtColor(out, cv2.COLOR_RGB2BGR)
        ok, buf = cv2.imencode(".jpg", enc, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ok:
            return False
        doc.update_stream(xref, buf.tobytes(), compress=False)
        doc.xref_set_key(xref, "Filter", "/DCTDecode")
    else:
        doc.update_stream(xref, np.ascontiguousarray(out).tobytes(), compress=True)
        doc.xref_set_key(xref, "Filter", "/FlateDecode")
    for key, val in (("DecodeParms", "null"), ("Decode", "null"), ("SMask", "null"),
                     ("BitsPerComponent", "8"), ("ColorSpace", cs),
                     ("Width", str(out.shape[1])), ("Height", str(out.shape[0]))):
        doc.xref_set_key(xref, key, val)
    return True
