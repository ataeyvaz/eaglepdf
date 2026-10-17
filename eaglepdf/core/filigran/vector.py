"""Yalnızca çizimden (yol/şekil) oluşan filigranların otomatik tespiti.

Metin ve resim filigranları `detector.py`'de bulunur; burada, içerik akışında metin/resim değil vektör yollar (harfleri çizgi
olarak çizilmiş logo, damga, şekil) olarak duran filigranlar aranır. Aynı renk ve aynı yerde, belgenin çoğu sayfasında tekrar eden
yollar bir grup oluşturur; grubun saydamlığı, rengi, kapladığı alan ve çizgi/çerçeve olup olmadığı puanı belirler.
Silme: yolun boyama operatörü `n` ile değiştirilir (`cleaner.py`, kind="vector").

Sıradan sayfa çerçevesi/üst çizgisi gibi opak ve ince çizgiler düşük puan alır ve otomatik seçilmez (kullanıcı isterse işaretler).
"""
from __future__ import annotations

import math
from collections import defaultdict

import pymupdf as fitz

from . import manual
from .detector import Finding, Occurrence, _luminance, _union

MAX_PATHS_PER_PAGE = 2500      # çok yoğun çizimli sayfalar (harita, CAD) atlanır: yavaş ve filigran olma ihtimali düşük
THIN = 1.5                     # pt: bundan ince şerit = çizgi/çerçeve


def _grup_anahtari(p: dict) -> tuple:
    return (p["sig"], round(p["opacity"], 1))


def _yer_anahtari(p: dict) -> tuple:
    return (p["sig"], round(p["opacity"], 1), *(round(v) for v in p["rect"]))


def detect(doc, findings: list, new_id, progress=None, cancel=None) -> list[Finding]:
    """Tekrar eden vektör çizim gruplarını Finding olarak döndürür (seçili olup olmadığı puana göre `Detector` tarafından verilir)."""
    n = len(doc)
    if n < 2:
        return []
    progress = progress or (lambda *a: None)
    # katman/Artifact filigranı olarak zaten bulunmuş yerleri tekrar bulma
    kapali: dict[int, list] = defaultdict(list)
    for f in findings:
        if f.kind in ("ocg", "artifact") and f.score >= 0.6:
            for o in f.occurrences:
                kapali[o.page].append(fitz.Rect(o.bbox))

    sayfa_yollari: dict[int, list] = {}
    sayac: dict[tuple, set] = defaultdict(set)      # yer anahtarı -> sayfalar
    for pno in range(n):
        if cancel and cancel():
            raise InterruptedError
        progress(pno, n, f"Vektör çizimler taranıyor: sayfa {pno + 1}/{n}")
        page = doc[pno]
        yollar = manual._paths_in(page, page.rect)
        if not yollar or len(yollar) > MAX_PATHS_PER_PAGE:
            continue
        yollar = [y for y in yollar if not any(fitz.Rect(y["rect"]).intersects(b) and
                                               manual._inside(y["rect"], b, 0.6) for b in kapali.get(pno, ()))]
        sayfa_yollari[pno] = yollar
        for y in yollar:
            sayac[_yer_anahtari(y)].add(pno)

    en_az = 2 if n == 2 else max(2, math.ceil(0.5 * n))
    tekrar = {k for k, sayfalar in sayac.items() if len(sayfalar) >= en_az}
    if not tekrar:
        return []

    gruplar: dict[tuple, dict[int, list]] = defaultdict(lambda: defaultdict(list))   # grup -> sayfa -> yollar
    for pno, yollar in sayfa_yollari.items():
        for y in yollar:
            if _yer_anahtari(y) in tekrar:
                gruplar[_grup_anahtari(y)][pno].append(y)

    sonuc = []
    for (sig, opaklik), sayfalar in gruplar.items():
        tum = [y for yollar in sayfalar.values() for y in yollar]
        bbox = None
        for y in tum:
            bbox = _union(bbox, y["rect"])
        sayfa_rect = doc[next(iter(sayfalar))].rect
        sayfa_alani = abs(sayfa_rect) or 1.0
        alan = abs(fitz.Rect(bbox)) / sayfa_alani
        ince = sum(min(fitz.Rect(y["rect"]).width, fitz.Rect(y["rect"]).height) < THIN for y in tum) / len(tum)
        acik = sum(_luminance(y["color"]) > 0.6 for y in tum) / len(tum)
        kapsam = len(sayfalar) / n
        yol_sayisi = max(len(v) for v in sayfalar.values())

        def bant(y):
            r = fitz.Rect(y["rect"])
            return ((r.width >= 0.7 * sayfa_rect.width and r.height <= 0.15 * sayfa_rect.height) or
                    (r.height >= 0.7 * sayfa_rect.height and r.width <= 0.15 * sayfa_rect.width))
        bantli = sum(bant(y) for y in tum) / len(tum)

        puan, nedenler = 0.35, [f"{len(sayfalar)}/{n} sayfada aynı yerde {yol_sayisi} vektör yol"]
        if opaklik < 0.95:
            puan += 0.25
            nedenler.append("yarı saydam")
        if acik >= 0.5:
            puan += 0.15
            nedenler.append("açık renk")
        if alan >= 0.10:
            puan += 0.15
            nedenler.append(f"geniş alan (sayfanın %{alan * 100:.0f}'i)")
        if kapsam >= 0.8:
            puan += 0.1
        if bantli >= 0.6 and ince < 0.6:
            puan -= 0.25
            nedenler.append("sayfa genişliğinde bant/şerit: başlık bandı gibi sayfa tasarımı olabilir, otomatik seçilmedi")
        if ince >= 0.6:
            puan -= 0.2
            nedenler.append("çoğu ince çizgi/çerçeve: sayfa düzeni olabilir, otomatik seçilmedi")
        if puan < 0.6 and "otomatik seçilmedi" not in " ".join(nedenler) and bantli < 0.6:
            nedenler.append("filigran olduğu kesin değil, önizlemede kontrol edin")
        nedenler.append("silme: yolun boyama operatörü 'n' ile değiştirilir")

        occs = [Occurrence(p, tuple(round(v, 2) for v in bbox), f"{len(yollar)} vektör yol (boyama operatörleri)",
                           {"paths": [{"rect": y["rect"]} for y in yollar]})
                for p, yollar in sorted(sayfalar.items())]
        renk = "x".join(f"{c:.2f}" for c in sig) if sig else "yok"
        sonuc.append(Finding(new_id("V"), "vector", f"Tekrar eden vektör çizim ({yol_sayisi} yol)", "", round(max(0.0, min(puan, 1.0)), 2),
                             nedenler, occs, [], {"kind": "vector", "bbox": [round(v) for v in bbox], "renk": renk,
                                                   "opaklik": opaklik}, {"_area": alan}))
    return sonuc
