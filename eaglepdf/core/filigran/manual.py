"""Elle işaretleme: kullanıcının sayfada çizdiği kutudaki nesneleri bulur ve aynı nesneyi
diğer sayfalarda arar. Otomatik tespitin kaçırdığı filigranlar için.

Kutudaki nesne türüne göre:
  metin    : aynı metin, aynı punto/yön, yaklaşık aynı konumda
  resim    : aynı resim içeriği (ayrı kopya olsa da), aynı konumda
  çizim    : aynı vektör yollar (konum + renk), sayfadaki yolların çoğu eşleşiyorsa
  taranmış : işaretlenen alanla sınırlı piksel filigranı modeli (raster.analyze box=)
"""
from __future__ import annotations

import pymupdf as fitz

from . import detector
from . import pdfops
from .detector import Finding, Occurrence, _norm, _r, find_urls

POS_TOL = 25.0      # metin konumu toleransı (pt)
IMG_TOL = 5.0       # resim yerleşimi toleransı (pt)
PATH_TOL = 2.0      # çizim konumu toleransı (pt)
PATH_MATCH = 0.7    # bir sayfada sayılması için eşleşmesi gereken yol oranı


def _center(b):
    return (b[0] + b[2]) / 2, (b[1] + b[3]) / 2


def _inside(inner, outer, frac=0.6) -> bool:
    """inner kutusunun en az `frac` kadarı outer içinde mi (çizgiler için merkez yeterli)?"""
    r = fitz.Rect(inner)
    o = fitz.Rect(outer)
    if r.is_empty or abs(r) < 1:
        cx, cy = _center(inner)
        return o.contains(fitz.Point(cx, cy))
    return abs(r & o) / abs(r) >= frac


def _runs(page) -> list[dict]:
    runs = {}
    try:
        trace = page.get_texttrace()
    except Exception:  # noqa: BLE001
        return []
    for s in trace:
        if s.get("type") not in (0, 1):
            continue
        txt = "".join(chr(c[0]) for c in s["chars"] if c[0] > 0)
        if not txt.strip():
            continue
        r = runs.get(s["seqno"])
        if r is None:
            runs[s["seqno"]] = r = {"text": "", "bbox": None, "size": s["size"], "dir": s["dir"],
                                    "font": s["font"], "opacity": s.get("opacity", 1),
                                    "color": s.get("color"), "spans": []}
        r["text"] += txt
        r["bbox"] = detector._union(r["bbox"], s["bbox"])
        r["spans"].append({"bbox": _r(s["bbox"]), "text": txt, "font": s["font"], "size": round(s["size"], 2)})
    return list(runs.values())


def _run_key(r):
    return _norm(r["text"]), round(r["size"]), round(r["dir"][0], 2), round(r["dir"][1], 2)


def _path_sig(d):
    col = d.get("fill") or d.get("color") or ()
    return tuple(round(c, 2) for c in col)


def _paths_in(page, sel) -> list[dict]:
    try:
        drawings = page.get_drawings()
    except Exception:  # noqa: BLE001
        return []
    prect = page.rect
    out = []
    for d in drawings:
        r = d["rect"]
        if abs(r & prect) >= 0.9 * abs(prect):
            continue                       # sayfa zemini / çerçeve
        if _inside(r, sel, 0.8):
            op = min(d.get("fill_opacity") or 1, d.get("stroke_opacity") or 1)
            out.append({"rect": _r(r), "sig": _path_sig(d), "opacity": op,
                        "color": d.get("fill") or d.get("color")})
    return out


class ManualSearch:
    def __init__(self, path: str, result, progress=None, cancel=None):
        self.path = path
        self.result = result
        self.progress = progress or (lambda *a: None)
        self.cancel = cancel or (lambda: False)

    def _check(self):
        if self.cancel():
            raise InterruptedError

    def run(self, pno: int, rect) -> list[Finding]:
        sel = fitz.Rect(rect)
        doc = pdfops.open_pdf(self.path)
        try:
            if pno in (self.result.scanned_pages or []):
                f = self._raster(doc, pno, sel)
                return [f] if f else []
            page = doc[pno]
            out = []
            runs = [r for r in _runs(page) if _inside(r["bbox"], sel)]
            imgs = []
            for info in page.get_image_info(xrefs=True):
                if info.get("xref") and _inside(info["bbox"], sel):
                    imgs.append(info)
            paths = _paths_in(page, sel)
            n = len(doc)
            if runs:
                out += self._text(doc, pno, runs)
            if imgs:
                out += self._images(doc, pno, imgs)
            if paths:
                out.append(self._vector(doc, pno, paths))
            self.progress(n, n, "Bitti")
            return _choose([f for f in out if f and f.occurrences])
        finally:
            doc.close()

    # ------------------------------------------------------------------ metin
    def _text(self, doc, pno, runs) -> list[Finding]:
        keys = {}
        for r in runs:
            keys.setdefault(_run_key(r), []).append(_center(r["bbox"]))
        per_page = {}                       # sayfa -> [(anahtar, run)]
        n = len(doc)
        for p in range(n):
            self._check()
            self.progress(p, n, f"Elle işaretlenen metin aranıyor: sayfa {p + 1}/{n}")
            page_runs = runs if p == pno else _runs(doc[p])
            for r in page_runs:
                k = _run_key(r)
                cs = keys.get(k)
                if not cs:
                    continue
                cx, cy = _center(r["bbox"])
                if any(abs(cx - x) <= POS_TOL and abs(cy - y) <= POS_TOL for x, y in cs):
                    per_page.setdefault(p, []).append((k, r))
        kept = _repeating({k for k, _ in per_page.get(pno, [])},
                          lambda k: sum(any(kk == k for kk, _ in v) for v in per_page.values()))
        # aynı sayfa kümesinde bulunan metinler tek nesnedir (ör. filigranın kelimeleri)
        groups: dict[frozenset, list] = {}
        for k in kept:
            pset = frozenset(p for p, items in per_page.items() if any(kk == k for kk, _ in items))
            groups.setdefault(pset, []).append(k)
        dropped = len(keys) - len(kept)
        out = []
        for pset, ks in groups.items():
            ks = set(ks)
            occs = []
            for p in sorted(pset):
                hit, bbox = [], None
                for k, r in per_page[p]:
                    if k in ks:
                        hit += r["spans"]
                        bbox = detector._union(bbox, r["bbox"])
                occs.append(Occurrence(p, _r(bbox), f"metin nesnesi ({len(hit)} parça), font '{hit[0]['font']}'",
                                       {"spans": hit}))
            mine = [r for r in runs if _run_key(r) in ks]
            text = " ".join(k[0] for k in keys if k in ks)
            look, why = max((_text_look(r) for r in mine), key=lambda x: x[0])
            reasons = [f"elle işaretlendi (s.{pno + 1})", f"{len(occs)} sayfada aynı metin aynı yerde"] + why
            if dropped:
                reasons.append(f"kutudaki {dropped} metin yalnızca bu sayfada olduğu için alınmadı")
            f = Finding("M", "text", f'Elle işaretlenen metin: "{text[:50]}"', text, look, reasons,
                        occs, find_urls(text), {"kind": "text", "text": text})
            f.data["_area"] = _area(mine)
            out.append(f)
        return out

    # ------------------------------------------------------------------ resim
    def _images(self, doc, pno, imgs) -> list[Finding]:
        out = []
        n = len(doc)
        digests: dict[int, str] = {}

        def dg(x):
            if x not in digests:
                digests[x] = detector.image_digest(doc, x)
            return digests[x]

        seen = set()
        for info in imgs:
            target = dg(info["xref"])
            if target in seen:
                continue
            seen.add(target)
            ref = _r(info["bbox"])
            occs = []
            for p in range(n):
                self._check()
                self.progress(p, n, f"Elle işaretlenen resim aranıyor: sayfa {p + 1}/{n}")
                page = doc[p]
                for im in page.get_images(full=True):
                    x = im[0]
                    if dg(x) != target:
                        continue
                    try:
                        rects = [_r(r) for r in page.get_image_rects(x)]
                    except Exception:  # noqa: BLE001
                        rects = []
                    wm = [r for r in rects if pdfops.rect_close(r, ref, IMG_TOL)]
                    if wm:
                        occs.append(Occurrence(p, wm[0], f"resim xref {x}, /{im[7]}",
                                               {"xref": x, "name": im[7], "rects": wm}))
                        break
            w, h = info.get("width"), info.get("height")
            reasons = [f"elle işaretlendi (s.{pno + 1})", f"{len(occs)} sayfada aynı resim aynı yerde"]
            look = 0.6
            obj = doc.xref_object(info["xref"], compressed=True)
            if "/SMask" in obj or "/Mask" in obj:
                look += 0.15
                reasons.append("saydamlık maskesi var")
            out.append(Finding("M", "image", f"Elle işaretlenen resim {w}×{h}", "", look, reasons,
                               occs, [], {"kind": "image", "digest": target},
                               {"xref": info["xref"], "_area": abs(fitz.Rect(info["bbox"]))}))
        if any(len(f.pages) > 1 for f in out):
            out = [f for f in out if len(f.pages) > 1]       # yalnızca bu sayfadaki resimler içeriktir
        return out

    # ------------------------------------------------------------------ vektör
    def _vector(self, doc, pno, paths) -> Finding:
        n = len(doc)
        bbox = None
        for d in paths:
            bbox = detector._union(bbox, d["rect"])
        sel = fitz.Rect(bbox) + (-PATH_TOL, -PATH_TOL, PATH_TOL, PATH_TOL)
        per_page = {}                       # sayfa -> {yol indeksi: eşleşen yol}
        for p in range(n):
            self._check()
            self.progress(p, n, f"Elle işaretlenen çizim aranıyor: sayfa {p + 1}/{n}")
            cand = paths if p == pno else _paths_in(doc[p], sel)
            used, matched = set(), {}
            for j, d in enumerate(paths):
                for i, c in enumerate(cand):
                    if i not in used and c["sig"] == d["sig"] and pdfops.rect_close(c["rect"], d["rect"], PATH_TOL):
                        used.add(i)
                        matched[j] = c
                        break
            if matched:
                per_page[p] = matched
        kept = _repeating(set(range(len(paths))), lambda j: sum(j in m for m in per_page.values()))
        bbox = None
        for j in kept:
            bbox = detector._union(bbox, paths[j]["rect"])
        occs = []
        for p, matched in sorted(per_page.items()):
            mine = [matched[j] for j in kept if j in matched]
            if mine and len(mine) >= PATH_MATCH * len(kept):
                occs.append(Occurrence(p, _r(bbox), f"{len(mine)} vektör yol (boyama operatörleri)",
                                       {"paths": [{"rect": m["rect"]} for m in mine]}))
        paths = [paths[j] for j in sorted(kept)]
        look, reasons = 0.5, [f"elle işaretlendi (s.{pno + 1})", f"{len(occs)} sayfada aynı çizim aynı yerde"]
        if any(d["opacity"] < 0.95 for d in paths):
            look += 0.2
            reasons.append("yarı saydam")
        if sum(detector._luminance(d["color"]) > 0.6 for d in paths) >= len(paths) / 2:
            look += 0.1
            reasons.append("açık renk")
        reasons.append("silme: yolun boyama operatörü 'n' ile değiştirilir")
        return Finding("M", "vector", f"Elle işaretlenen çizim ({len(paths)} yol)", "", round(look, 2), reasons,
                       occs, [], {"kind": "vector", "bbox": [round(v) for v in bbox]},
                       {"_area": abs(fitz.Rect(bbox))})

    # ------------------------------------------------------------------ taranmış
    def _raster(self, doc, pno, sel) -> Finding | None:
        from . import raster
        scanned = {}
        for p in self.result.scanned_pages:
            sc = raster.scanned_image(doc, doc[p], 0)
            if sc and sc[2] > 1:
                scanned[p] = sc
        if pno not in scanned:
            return None
        ra = raster.analyze(doc, scanned, self.progress, self.cancel,
                            box=(pno, tuple(sel)))
        if not ra:
            return None
        model, occ = ra
        c = model.color
        occs = [Occurrence(p, bb, f"sayfa resmi xref {scanned[p][0]}, kapsama %{cov * 100:.0f}",
                           {"xref": scanned[p][0]}) for p, bb, cov in occ]
        f = Finding("M", "raster", "Elle işaretlenen taranmış alan", "", 1.0,
                    [f"elle işaretlendi (s.{pno + 1})", f"{len(occs)} sayfada aynı desen",
                     f"filigran rengi ≈ RGB({c[0]:.0f}, {c[1]:.0f}, {c[2]:.0f})"],
                    occs, [], {"kind": "raster"}, {"model": model}, selected=True)
        detector.Detector(self.path, self.progress, self.cancel)._ocr_raster(doc, f)
        return f


def _text_look(r) -> tuple[float, list]:
    """Metnin filigrana benzerliği (0.5 = sıradan metin)."""
    s, why = 0.5, []
    if abs(r["dir"][1]) > 0.05:
        s += 0.15
        why.append("döndürülmüş")
    if r.get("opacity", 1) < 0.95:
        s += 0.15
        why.append("yarı saydam")
    if r["size"] >= 30:
        s += 0.1
        why.append(f"büyük punto ({r['size']:.0f}pt)")
    if detector._luminance(r.get("color")) > 0.6:
        s += 0.1
        why.append("açık renk")
    return round(min(s, 1.0), 2), why


def _area(items) -> float:
    return sum(abs(fitz.Rect(i["bbox"] if "bbox" in i else i["rect"])) for i in items)


def _choose(found: list[Finding]) -> list[Finding]:
    """Kutuda birden çok nesne grubu varsa yalnızca en filigran benzerlerini seçili yapar;
    hiçbiri belirgin değilse kutuda en çok yer kaplayanı seçer. Diğerleri listede seçilmemiş durur."""
    if not found:
        return found
    best = max(f.score for f in found)
    if best > 0.5:
        chosen = [f for f in found if f.score >= best - 0.05]
    else:
        chosen = [max(found, key=lambda f: f.data.get("_area", 0))]
    for f in found:
        f.selected = f in chosen
        if len(found) > 1:
            f.reasons.append("kutudaki en filigran benzeri nesne: seçildi" if f.selected else
                             "kutuda bulunan başka bir nesne: gerekiyorsa elle seç")
    found.sort(key=lambda f: (not f.selected, -f.score))
    return found


def _repeating(keys: set, count) -> set:
    """Başka sayfalarda da bulunan anahtarlar; hiçbiri tekrar etmiyorsa hepsi (tek sayfalık filigran)."""
    rep = {k for k in keys if count(k) >= 2}
    return rep or set(keys)


def search(path: str, result, pno: int, rect, progress=None, cancel=None) -> list[Finding]:
    """Bulunan her nesne grubu için bir Finding (id'ler çağıran tarafından verilir)."""
    return ManualSearch(path, result, progress, cancel).run(pno, rect)
