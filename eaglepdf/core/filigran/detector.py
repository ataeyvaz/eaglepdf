"""Filigran tespit motoru.

Bulunan her filigran bir `Finding`'dir; her sayfadaki örneği bir `Occurrence`'dır.
Tespit katmanları (güvenden aza):
  1. Acrobat / standart filigran: 'Watermark' gibi OCG katmanları, /OC bağlı XObject'ler,
     /PieceInfo /ADBE_CompoundType /Private /Watermark imzası, /Artifact /Watermark içerik bölümleri
  2. Watermark türündeki annotation'lar
  3. Sayfalar arası tekrar eden metin (saydamlık, döndürme, büyük punto, açık renk puanı artırır)
  4. Sayfalar arası tekrar eden resim
  5. Sayfalar arası tekrar eden bağlantılar (URL)
"""
from __future__ import annotations

import collections
import hashlib
import math
import re
from collections import defaultdict
from dataclasses import dataclass, field, asdict

import logging

import pymupdf as fitz

from . import pdfops

log = logging.getLogger(__name__)

AUTO_SELECT_SCORE = 0.6

WM_NAME_RE = re.compile(r"water\s*mark|filigran|wasserzeichen|filigrane|background|arka\s*plan|"
                        r"header|footer|ba[sş]l[iı]k|alt\s*bilgi|stamp|damga", re.I)
WM_STRONG_RE = re.compile(r"water\s*mark|filigran|wasserzeichen|filigrane", re.I)
PRIVATE_RE = re.compile(r"/Private\s*/(\w+)")
URL_RE = re.compile(
    r"(?:https?://|www\.)[^\s<>\"'()]+"
    r"|[\w.+-]+@[\w-]+(?:\.[\w-]+)+"
    r"|\b[\w-]+(?:\.[\w-]+)*\.(?:com|net|org|edu|gov|info|io|co|biz|me|tv|tr)(?:\.tr)?\b(?:/[^\s]*)?",
    re.I)
PHONE_RE = re.compile(r"(?:\+?\d{1,3}[\s.-]?)?\(?0?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{2}[\s.-]?\d{2}\b")


@dataclass
class Occurrence:
    page: int                       # 0 tabanlı
    bbox: tuple                     # sayfa koordinatları (x0, y0, x1, y1)
    address: str                    # insan okunur PDF iç adresi
    data: dict = field(default_factory=dict)   # temizleyici için


@dataclass
class Finding:
    id: str
    kind: str                       # ocg | artifact | annot | text | image | link | raster | vector | meta
    title: str
    text: str
    score: float
    reasons: list
    occurrences: list
    urls: list
    signature: dict                 # kural eşleştirmesi için
    data: dict = field(default_factory=dict)
    selected: bool = False

    @property
    def pages(self) -> list[int]:
        return sorted({o.page for o in self.occurrences})

    def to_dict(self) -> dict:
        d = {k: getattr(self, k) for k in ("id", "kind", "title", "text", "score", "reasons", "urls",
                                            "signature", "selected")}
        d["pages"] = [p + 1 for p in self.pages]
        d["occurrences"] = [{"page": o.page + 1, "bbox": list(o.bbox), "address": o.address}
                            for o in self.occurrences]
        return d


@dataclass
class ScanResult:
    path: str
    page_count: int
    findings: list
    metadata: dict = field(default_factory=dict)
    scanned_pages: list = field(default_factory=list)   # taranmış (tek resim) sayfalar
    bilevel_pages: list = field(default_factory=list)   # 1-bit (siyah-beyaz) taramalar: yalnızca ortak piksel deseniyle aranır (deneysel)


KIND_LABELS = {
    "ocg": "Acrobat/OCG filigranı",
    "artifact": "Artifact filigranı",
    "annot": "Annotation filigranı",
    "text": "Tekrar eden metin",
    "image": "Tekrar eden resim",
    "link": "Tekrar eden bağlantı",
    "raster": "Taranmış sayfa filigranı",
    "vector": "Vektör çizim",
    "meta": "Belge bilgileri",
}
META_KEYS = ("title", "author", "subject", "keywords", "creator", "producer")
META_LABELS = {"title": "Başlık", "author": "Yazar", "subject": "Konu", "keywords": "Anahtar kelimeler",
               "creator": "Oluşturan uygulama", "producer": "PDF üreticisi"}


def find_urls(text: str, phones: bool = True) -> list[str]:
    found = [m.group(0).rstrip(".,;:") for m in URL_RE.finditer(text or "")]
    if phones:
        found += [m.group(0).strip() for m in PHONE_RE.finditer(text or "")]
    out = []
    for u in found:
        if u not in out:
            out.append(u)
    return out


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _union(a, b):
    if a is None:
        return tuple(b)
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def _r(b) -> tuple:
    return tuple(round(float(v), 2) for v in b)


def _luminance(color) -> float:
    if not color:
        return 0.0
    if len(color) == 1:
        return color[0]
    if len(color) == 3:
        r, g, b = color
        return 0.299 * r + 0.587 * g + 0.114 * b
    if len(color) == 4:  # CMYK
        c, m, y, k = color
        return 1 - min(1, 0.3 * c + 0.59 * m + 0.11 * y + k)
    return 0.0


class _XObjInfo:
    __slots__ = ("ocgs", "private")

    def __init__(self, ocgs, private):
        self.ocgs = ocgs
        self.private = private


def _ocgs_of(doc: fitz.Document, oc_xref: int) -> list[int]:
    """OC girdisi bir OCG ya da OCMD olabilir; ilgili OCG xref'lerini döndürür."""
    if not oc_xref:
        return []
    t, v = doc.xref_get_key(oc_xref, "Type")
    if v == "/OCMD":
        t, v = doc.xref_get_key(oc_xref, "OCGs")
        return [int(x) for x in re.findall(r"(\d+)\s+0\s+R", v)]
    return [oc_xref]


class Detector:
    def __init__(self, path: str, progress=None, cancel=None, ocr: bool = True):
        self.path = path
        self.progress = progress or (lambda *a: None)
        self.cancel = cancel or (lambda: False)
        self.use_ocr = ocr

    # ------------------------------------------------------------------ yardımcılar
    def _xobj_info(self, xref: int) -> _XObjInfo:
        if xref not in self._xcache:
            obj = self.doc.xref_object(xref, compressed=True) or ""
            ocgs = []
            t, v = self.doc.xref_get_key(xref, "OC")
            if t == "xref":
                ocgs = _ocgs_of(self.doc, pdfops.ref_xref(v))
            m = PRIVATE_RE.search(obj) if "ADBE_CompoundType" in obj else None
            self._xcache[xref] = _XObjInfo(ocgs, m.group(1) if m else None)
        return self._xcache[xref]

    # ------------------------------------------------------------------ ana akış
    def run(self) -> ScanResult:
        doc = self.doc = pdfops.open_pdf(self.path)
        self._xcache: dict[int, _XObjInfo] = {}
        n = len(doc)
        ocg_names = {x: info.get("name", "") for x, info in (doc.get_ocgs() or {}).items()}

        # katman 1 adayları
        wm_ocgs = {x for x, nm in ocg_names.items() if WM_NAME_RE.search(nm or "")}
        ocg_occ = defaultdict(list)          # anahtar -> [Occurrence]
        ocg_text = defaultdict(list)         # anahtar -> metinler
        ocg_xobjs = defaultdict(set)         # anahtar -> silinecek XObject xref'leri
        artifact_occ = []
        cache = pdfops.StreamCache(doc)

        text_runs = defaultdict(list)        # grup anahtarı -> [(page, run)]
        image_pages = defaultdict(dict)      # resim içerik özeti -> {page: (xref, name, referencer)}
        digests: dict[int, str] = {}
        link_occ = defaultdict(list)         # uri -> [Occurrence]
        annot_occ = defaultdict(list)        # (tip, içerik) -> [Occurrence]
        all_text_for_page = {}
        scanned, bilevel = {}, {}                 # sayfa -> (resim xref, kutu, bpc)

        for pno in range(n):
            if self.cancel():
                raise InterruptedError
            self.progress(pno, n, f"Sayfa {pno + 1}/{n} taranıyor")
            page = doc[pno]
            prect = page.rect
            streams = pdfops.page_streams(doc, page)

            # --- 1a: OC/Private işaretli XObject'ler
            page_wm_layers = set()
            page_wm_xobjs = set()
            for sref in streams:
                xmap = cache.resource_map(sref.owner, "XObject", sref.fallback)
                rev = {}
                ops = cache.quick_ops(sref.xref)
                for oi, op in enumerate(ops):
                    if op.name == b"Do" and op.operands:
                        name = op.operands[-1].decode("latin-1").lstrip("/")
                        x = xmap.get(name)
                        if not x:
                            continue
                        info = self._xobj_info(x)
                        keys = []
                        for g in info.ocgs:
                            if g in wm_ocgs or info.private:
                                keys.append(("ocg", g))
                                wm_ocgs.add(g)
                        if not keys and info.private:
                            keys.append(("private", info.private))
                        for k in keys:
                            ocg_xobjs[k].add(x)
                            page_wm_xobjs.add(x)
                            rev.setdefault(k, []).append(f"/{name} Do → XObject xref {x}")
                    elif op.name == b"BDC" and len(op.operands) >= 2:
                        tag = op.operands[0]
                        props = op.operands[1]
                        if tag == b"/OC" and props.startswith(b"/"):
                            pmap = cache.resource_map(sref.owner, "Properties", sref.fallback)
                            g = pmap.get(props.decode("latin-1").lstrip("/"))
                            for gg in _ocgs_of(doc, g):
                                if gg in wm_ocgs:
                                    rev.setdefault(("ocg", gg), []).append(
                                        f"BDC /OC {props.decode('latin-1')} → OCG xref {gg}")
                        elif tag == b"/Artifact" and b"Watermark" in props:
                            # içinde zaten tanınan bir filigran XObject'i varsa ayrı bulgu sayma
                            j = pdfops.find_emc(ops, oi)
                            inner = [o for o in ops[oi:j] if o.name == b"Do" and o.operands]
                            if any(self._xobj_info(xmap[nm]).ocgs or self._xobj_info(xmap[nm]).private
                                   for nm in (o.operands[-1].decode("latin-1").lstrip("/") for o in inner)
                                   if nm in xmap):
                                continue
                            artifact_occ.append(Occurrence(
                                pno, _r(prect), f"içerik akışı xref {sref.xref}: /Artifact <</Subtype /Watermark>> BDC",
                                {"stream": sref.xref}))
                for k, addrs in rev.items():
                    if k[0] == "ocg":
                        page_wm_layers.add(ocg_names.get(k[1], ""))
                    kind = "form" if sref.is_form else "sayfa içeriği"
                    ocg_occ[k].append(Occurrence(
                        pno, None, f"{kind} xref {sref.xref}: " + "; ".join(sorted(set(addrs))),
                        {"stream": sref.xref}))

            # --- metin izi
            try:
                trace = page.get_texttrace()
            except Exception:
                trace = []
            runs = {}
            for s in trace:
                if s.get("type") not in (0, 1):
                    continue
                txt = "".join(chr(c[0]) for c in s["chars"] if c[0] > 0)
                if not txt.strip():
                    continue
                key = s["seqno"]
                r = runs.get(key)
                if r is None:
                    runs[key] = r = {"text": "", "bbox": None, "font": s["font"], "size": s["size"],
                                     "dir": s["dir"], "color": s["color"], "opacity": s["opacity"],
                                     "layer": s.get("layer"), "seqno": key, "spans": []}
                r["text"] += txt
                r["bbox"] = _union(r["bbox"], s["bbox"])
                r["spans"].append({"bbox": _r(s["bbox"]), "text": txt, "font": s["font"],
                                   "size": round(s["size"], 2)})
            visible = sum(len(s["chars"]) for s in trace if s.get("type") != 3)
            try:
                from . import raster
                sc = raster.scanned_image(doc, page, visible)
            except ImportError:
                sc = None
            if sc:
                (scanned if sc[2] > 1 else bilevel)[pno] = sc
            page_text = []
            for r in runs.values():
                page_text.append(r["text"])
                layer = r["layer"]
                if layer and layer in page_wm_layers:
                    for k in ocg_occ:
                        if k[0] == "ocg" and ocg_names.get(k[1]) == layer:
                            ocg_text[k].append(_norm(r["text"]))
                            for o in ocg_occ[k]:
                                if o.page == pno:
                                    o.bbox = _union(o.bbox, r["bbox"])
                    continue
                t = _norm(r["text"])
                if len(t) < 3 or not re.search(r"[^\W\d_]{2}", t):
                    continue
                d = r["dir"]
                gkey = (t, round(r["size"]), round(d[0], 2), round(d[1], 2))
                text_runs[gkey].append((pno, r))
            all_text_for_page[pno] = page_text

            # OCG kutuları: metin izinden bulunamadıysa katman çizim kaydından (resim filigranları)
            layer_has_box = all(o.bbox for k in ocg_occ for o in ocg_occ[k] if o.page == pno)
            if page_wm_layers and not layer_has_box:
                try:
                    for _t, bb, layer in page.get_bboxlog(layers=True):
                        if layer in page_wm_layers:
                            for k in ocg_occ:
                                if ocg_names.get(k[1]) == layer:
                                    for o in ocg_occ[k]:
                                        if o.page == pno:
                                            o.bbox = _union(o.bbox, bb)
                except Exception:
                    pass
            for k in ocg_occ:
                for o in ocg_occ[k]:
                    if o.page == pno and o.bbox is None:
                        o.bbox = _r(prect)
                    elif o.page == pno:
                        o.bbox = _r(o.bbox)

            # --- resimler
            try:
                imgs = page.get_images(full=True)
            except Exception:
                imgs = []
            for im in imgs:
                x, name, referencer = im[0], im[7], im[9]
                if referencer in page_wm_xobjs:
                    continue
                if not x or (pno in scanned and scanned[pno][0] == x):
                    continue
                # aynı resim her sayfaya ayrı nesne olarak da gömülmüş olabilir: içeriğe göre grupla
                dg = digests.get(x)
                if dg is None:
                    dg = digests[x] = image_digest(doc, x)
                if pno not in image_pages[dg]:
                    image_pages[dg][pno] = (x, name, referencer)

            # --- annotation'lar
            for a in page.annots() or []:
                tname = a.type[1]
                if tname not in ("Watermark", "Stamp", "FreeText"):
                    continue
                content = _norm(a.info.get("content", ""))
                annot_occ[(tname, content)].append(Occurrence(
                    pno, _r(a.rect), f"annotation xref {a.xref} (/Subtype /{tname})", {"xref": a.xref}))

            # --- bağlantılar
            for ln in page.get_links():
                uri = ln.get("uri")
                if uri:
                    link_occ[uri].append(Occurrence(
                        pno, _r(ln["from"]), f"link annotation xref {ln.get('xref', 0)} → {uri}",
                        {"uri": uri, "xref": ln.get("xref", 0)}))

        self.progress(n, n, "Sonuçlar derleniyor")
        findings = []
        fid = 0

        def new_id(prefix):
            nonlocal fid
            fid += 1
            return f"{prefix}{fid}"

        # --- 1: OCG / Private
        for k, occs in ocg_occ.items():
            if not occs:
                continue
            texts = []
            for t in ocg_text.get(k, []):
                if t not in texts:
                    texts.append(t)
            text = " | ".join(texts[:5])
            if k[0] == "ocg":
                name = ocg_names.get(k[1], "?")
                title = f'Katman "{name}"' + (f": {texts[0]}" if texts else "")
                reasons = [f'OCG katmanı "{name}" (xref {k[1]})']
                score = 0.95 if WM_STRONG_RE.search(name) else 0.75
                sig = {"kind": "ocg", "ocg_name": name}
            else:
                title = f"Acrobat /{k[1]} nesnesi" + (f": {texts[0]}" if texts else "")
                reasons = []
                score = 0.9 if k[1] == "Watermark" else 0.6
                sig = {"kind": "ocg", "private": k[1]}
            privs = {self._xcache[x].private for x in ocg_xobjs[k] if self._xcache[x].private}
            for p in sorted(privs):
                reasons.append(f"/PieceInfo /ADBE_CompoundType /Private /{p} imzası")
                if p == "Watermark":
                    score = max(score, 0.97)
            xs = sorted(ocg_xobjs[k])
            reasons.append(f"{len({o.page for o in occs})}/{n} sayfada; XObject xref: " +
                           ", ".join(map(str, xs[:10])) + (" …" if len(xs) > 10 else ""))
            findings.append(Finding(
                new_id("O"), "ocg", title, text, score, reasons, occs, find_urls(text), sig,
                {"ocgs": [k[1]] if k[0] == "ocg" else [], "xobjs": sorted(ocg_xobjs[k])}))

        if artifact_occ:
            findings.append(Finding(
                new_id("A"), "artifact", "İşaretli içerik /Artifact /Watermark", "", 0.9,
                ["İçerik akışında /Artifact <</Subtype /Watermark>> bölümü",
                 f"{len({o.page for o in artifact_occ})} sayfada"],
                artifact_occ, [], {"kind": "artifact"}))

        # --- 2: annotation
        for (tname, content), occs in annot_occ.items():
            pages = {o.page for o in occs}
            if tname == "Watermark":
                score = 0.95
            elif len(pages) >= max(2, 0.3 * n):
                score = 0.55
            else:
                continue
            findings.append(Finding(
                new_id("N"), "annot", f"/{tname} annotation" + (f": {content[:60]}" if content else ""),
                content, score, [f"/Subtype /{tname} annotation", f"{len(pages)} sayfada"],
                occs, find_urls(content), {"kind": "annot", "annot_type": tname, "content": content}))

        # --- 3: tekrar eden metin
        min_pages = max(2, int(0.3 * n + 0.999)) if n >= 3 else 1
        for gkey, items in text_runs.items():
            pages = {p for p, _ in items}
            r0 = items[0][1]
            frac = len(pages) / n
            score, reasons = 0.0, []
            if len(pages) >= min_pages and n >= 2:
                if frac >= 0.5:
                    score += 0.3
                else:
                    score += 0.15
                reasons.append(f"{len(pages)}/{n} sayfada tekrar ediyor")
            elif n >= 3:
                continue
            if r0["opacity"] < 0.95:
                score += 0.3
                reasons.append(f"yarı saydam (opaklık {r0['opacity']:.2f})")
            dx, dy = r0["dir"]
            if abs(dy) > 0.05:
                score += 0.25
                reasons.append(f"döndürülmüş ({abs(round(math.degrees(math.atan2(-dy, dx))))}°)")
            if r0["size"] >= 30:
                score += 0.2
                reasons.append(f"büyük punto ({r0['size']:.0f}pt)")
            if _luminance(r0["color"]) > 0.6:
                score += 0.15
                reasons.append("açık renk")
            if r0["layer"] and WM_NAME_RE.search(r0["layer"]):
                score += 0.5
                reasons.append(f'"{r0["layer"]}" katmanında')
            urls = find_urls(gkey[0])
            if urls:
                score += 0.1
                reasons.append("adres/iletişim bilgisi içeriyor")
            if score < 0.3:
                continue
            occs = [Occurrence(p, _r(r["bbox"]),
                               f"metin nesnesi: font '{r['font']}', {r['size']:.1f}pt, çizim sırası #{r['seqno']}",
                               {"spans": r["spans"]})
                    for p, r in items]
            findings.append(Finding(
                new_id("T"), "text", f'Metin: "{gkey[0][:60]}"', gkey[0], round(min(score, 1.0), 2),
                reasons, occs, urls, {"kind": "text", "text": gkey[0]}))

        # --- 4: tekrar eden resim
        for digest, pmap in image_pages.items():
            if len(pmap) < min_pages or n < 2:
                continue
            frac = len(pmap) / n
            xrefs = sorted({v[0] for v in pmap.values()})
            x = xrefs[0]
            score, reasons = 0.3 if frac >= 0.5 else 0.15, [f"{len(pmap)}/{n} sayfada aynı resim"]
            if len(xrefs) > 1:
                reasons.append(f"her sayfada ayrı kopya olarak gömülü ({len(xrefs)} nesne)")
            occs = []
            rects = []
            page_rects = {}
            for p in pmap:
                try:
                    page_rects[p] = [_r(rr) for rr in doc[p].get_image_rects(pmap[p][0])]
                except Exception:
                    page_rects[p] = []
            # filigran konumu = sayfaların çoğunda tekrar eden yerleşim
            common = collections.Counter(tuple(round(v) for v in rr)
                                         for rs in page_rects.values() for rr in set(rs))
            mode = common.most_common(1)[0][0] if common else None
            for p, (px, name, referencer) in sorted(pmap.items()):
                rs = page_rects[p]
                wm = [rr for rr in rs if mode and pdfops.rect_close(rr, mode, 3)] or rs
                bb = wm[0] if wm else _r(doc[p].rect)
                rects.append(bb)
                where = f"form xref {referencer}" if referencer else "sayfa kaynakları"
                extra = f", sayfada {len(rs)} yerleşim, {len(wm)} tanesi filigran" if len(rs) > 1 else ""
                occs.append(Occurrence(p, bb, f"resim xref {px}, /{name} ({where}){extra}",
                                       {"xref": px, "name": name, "rects": wm}))
            prect = doc[occs[0].page].rect
            area = abs((rects[0][2] - rects[0][0]) * (rects[0][3] - rects[0][1]))
            if len({tuple(round(v) for v in r) for r in rects}) == 1:
                score += 0.15
                reasons.append("her sayfada aynı konumda")
            if area >= 0.15 * prect.width * prect.height:
                score += 0.2
                reasons.append("sayfanın büyük kısmını kaplıyor")
            obj = doc.xref_object(x, compressed=True)
            if "/SMask" in obj or "/Mask" in obj:
                score += 0.15
                reasons.append("saydamlık maskesi var")
            w = doc.xref_get_key(x, "Width")[1]
            h = doc.xref_get_key(x, "Height")[1]
            findings.append(Finding(
                new_id("I"), "image", f"Resim {w}×{h} (xref {x})", "", round(min(score, 1.0), 2),
                reasons, occs, [], {"kind": "image", "digest": digest}, {"xref": x, "xrefs": xrefs}))

        # --- 4b: taranmış sayfalarda piksel filigranı
        if scanned:
            from . import raster
            ra = raster.analyze(doc, scanned, self.progress, self.cancel)
            if ra:
                model, occ = ra
                scanned_frac = len(scanned) / n
                present_frac = len(occ) / len(scanned)
                c = model.color
                reasons = [f"{len(scanned)}/{n} sayfa taranmış (tek resim)",
                           f"{len(occ)}/{len(scanned)} taranmış sayfada aynı yerde yarı ton desen"
                           if model.consistent
                           else "tek/az sayfa: sayfalar arası doğrulama yapılamadı, önizlemede kontrol et"]
                if model.consistent and scanned_frac >= 0.5 and present_frac >= 0.3:
                    score = 0.8
                else:
                    score = 0.4
                    if scanned_frac < 0.5:
                        reasons.append("belge çoğunlukla dijital: bu sayfalar tasarım görseli olabilir, "
                                       "otomatik seçilmedi")
                    elif present_frac < 0.3:
                        reasons.append("desen az sayfada tekrar ediyor: filigran olmayabilir, otomatik seçilmedi")
                reasons += [
                           f"filigran rengi ≈ RGB({c[0]:.0f}, {c[1]:.0f}, {c[2]:.0f})",
                           "piksel temizliği: filigranın kattığı koyuluk geri alınır (un-blend)"]
                occs = [Occurrence(p, bb, f"sayfa resmi xref {scanned[p][0]}, kapsama %{cov * 100:.0f}",
                                   {"xref": scanned[p][0]}) for p, bb, cov in occ]
                rf = Finding(new_id("R"), "raster", "Taranmış sayfalarda filigran (piksel)", "", score,
                             reasons, occs, [], {"kind": "raster"}, {"model": model})
                self._ocr_raster(doc, rf)
                findings.append(rf)

        # --- 4c: 1-bit (siyah-beyaz) sayfalar: sayfalar arası ortak piksel deseni (deneysel; otomatik seçilmez)
        if bilevel:
            from . import bilevel as bilevel_modulu
            rb = bilevel_modulu.analyze(doc, bilevel, self.progress, self.cancel)
            if rb:
                model, occ = rb
                occs = [Occurrence(p, bb, f"1-bit sayfa resmi xref {bilevel[p][0]}, ortak desen kapsaması %{cov * 100:.0f}",
                                   {"xref": bilevel[p][0]}) for p, bb, cov in occ]
                findings.append(Finding(
                    new_id("B"), "raster", "1-bit taranmış sayfalarda filigran (ortak piksel deseni, deneysel)", "", 0.5,
                    [f"{len(bilevel)} sayfa 1-bit (siyah-beyaz) tarama; {len(occs)} sayfada aynı pikseller siyah",
                     "yöntem: sayfalar arası ortak piksel deseni; tarayıcıdan kayarak gelen sayfalarda çalışmaz",
                     "deneysel: otomatik seçilmedi, önizlemede ('Temizlenmiş halini göster') kontrol edin",
                     "silme: ortak desen pikselleri beyaza çevrilir; filigranla çakışan yazı pikselleri küçük kayba uğrayabilir"],
                    occs, [], {"kind": "raster", "bilevel": True}, {"model": model}))

        # --- 4d: yalnızca vektör çizimden oluşan filigranlar
        from . import vector
        findings += vector.detect(doc, findings, new_id, self.progress, self.cancel)

        self._ocr_images(doc, [f for f in findings if f.kind == "image"])

        # --- 5: bağlantılar
        wm_boxes = defaultdict(list)
        for f in findings:
            if f.score >= AUTO_SELECT_SCORE:
                for o in f.occurrences:
                    wm_boxes[o.page].append(fitz.Rect(o.bbox))
        for uri, occs in link_occ.items():
            pages = {o.page for o in occs}
            inside = any(fitz.Rect(o.bbox).intersects(b) for o in occs for b in wm_boxes[o.page])
            if len(pages) < min_pages and not inside:
                continue
            score = 0.45 + (0.3 if inside else 0) + (0.1 if len(pages) / n >= 0.5 else 0)
            reasons = [f"{len(pages)} sayfada bağlantı"]
            if inside:
                reasons.append("filigran alanının içinde")
            findings.append(Finding(
                new_id("L"), "link", f"Bağlantı: {uri[:70]}", uri, round(score, 2), reasons, occs,
                [uri], {"kind": "link", "uri": uri}))

        mf = meta_finding(doc, findings)
        if mf:
            mf.id = new_id("D")
            findings.append(mf)

        for f in findings:
            f.selected = f.score >= AUTO_SELECT_SCORE
        findings.sort(key=lambda f: -f.score)
        meta = {k: v for k, v in (doc.metadata or {}).items() if v}
        doc.close()
        return ScanResult(self.path, n, findings, meta, sorted(scanned), sorted(bilevel))


    # ------------------------------------------------------------------ OCR
    def _ocr_raster(self, doc, f: Finding) -> None:
        if not self.use_ocr:
            return
        if f.score < AUTO_SELECT_SCORE:
            f.reasons.append("düşük güven: filigran yazısı okunmadı (OCR atlandı)")
            return
        from . import ocr
        self.progress(0, 1, "Filigran yazısı okunuyor (OCR)")
        if not ocr.available():
            f.reasons.append("filigran yazısı okunamadı: OCR motoru yüklenemedi")
            return
        try:
            text = ocr.read_raster(doc, f)
        except Exception as exc:  # noqa: BLE001
            log.exception("OCR (taranmış sayfa) başarısız")
            f.reasons.append(f"OCR hatası: {exc}")
            return
        if text:
            f.text = text
            f.title = f'Taranmış sayfa filigranı: "{text[:50]}"'
            f.urls = find_urls(text)
            f.reasons.append(f'filigran yazısı (OCR): "{text}"')
        else:
            f.reasons.append("filigranda okunabilir yazı bulunamadı (OCR)")

    def _ocr_images(self, doc, image_findings) -> None:
        if not self.use_ocr or not image_findings:
            return
        from . import ocr
        if not ocr.available():
            return
        targets = sorted(image_findings, key=lambda f: -f.score)[:ocr.MAX_IMAGES]
        for k, f in enumerate(targets):
            if self.cancel():
                raise InterruptedError
            self.progress(k, len(targets), "Resim filigranlarındaki yazı okunuyor (OCR)")
            try:
                text = ocr.read_image(doc, f.data["xref"])
            except Exception:  # noqa: BLE001
                log.exception("OCR (resim) başarısız")
                continue
            if not text:
                continue
            f.text = text
            f.title += f': "{text[:40]}"'
            f.reasons.append(f'resimdeki yazı (OCR): "{text}"')
            f.urls = find_urls(text)
            if f.urls:
                f.score = round(min(1.0, f.score + 0.1), 2)
                f.reasons.append("adres/iletişim bilgisi içeriyor")


def image_digest(doc: fitz.Document, xref: int) -> str:
    try:
        raw = doc.xref_stream_raw(xref) or b""
    except Exception:  # noqa: BLE001
        raw = b""
    return hashlib.md5(raw).hexdigest()


def info_xref(doc: fitz.Document) -> int:
    t, v = doc.xref_get_key(-1, "Info")
    return pdfops.ref_xref(v) if t == "xref" else 0


def meta_finding(doc: fitz.Document, findings) -> Finding | None:
    """Belge bilgileri (Info sözlüğü + XMP): yayıncı adı, adres vb. burada da durabilir."""
    md = doc.metadata or {}
    fields = {k: md[k] for k in META_KEYS if md.get(k)}
    custom = {}                                       # standart dışı Info anahtarları
    ix = info_xref(doc)
    if ix:
        for key in doc.xref_get_keys(ix):
            if key.lower() in META_KEYS or key in ("CreationDate", "ModDate", "Trapped"):
                continue
            t, v = doc.xref_get_key(ix, key)
            if t == "string" and v.strip():
                custom[key] = v
    xmp = (doc.get_xml_metadata() or "").strip()
    if not fields and not custom and not xmp:
        return None
    xmp_text = re.sub(r"<[^>]+>", " ", xmp)
    all_text = " ".join([*fields.values(), *custom.values(), xmp_text])
    urls = find_urls(all_text, phones=False)
    hay = _norm(all_text).casefold()
    wm_texts = {_norm(f.text).casefold() for f in findings if f.text and f.score >= AUTO_SELECT_SCORE}
    hits = sorted(t for t in wm_texts if len(t) >= 4 and t in hay)
    lines = [f"{META_LABELS[k]}: {v}" for k, v in fields.items()] + [f"{k}: {v}" for k, v in custom.items()]
    if xmp:
        lines.append(f"XMP metadata ({len(xmp)} karakter)")
    reasons = ["alanlar: " + "; ".join(lines)[:400]]
    score = 0.35
    if urls:
        score = 0.7
        reasons.append("belge bilgilerinde adres var: " + ", ".join(urls[:5]))
    if hits:
        score = 0.75
        reasons.append("filigran yazısı belge bilgilerinde de geçiyor: " + ", ".join(hits)[:200])
    if score < AUTO_SELECT_SCORE:
        reasons.append("yayıncı/adres izi bulunmadı, otomatik seçilmedi")
    who = fields.get("author") or fields.get("title")
    title = "Belge bilgileri (metadata)" + (f": {who}" if who else "")
    return Finding("D", "meta", title[:90], "\n".join(lines), score, reasons, [], urls,
                   {"kind": "meta"}, {"keys": list(fields), "custom": list(custom), "xmp": bool(xmp)})


def scan(path: str, progress=None, cancel=None, ocr: bool = True) -> ScanResult:
    return Detector(path, progress, cancel, ocr).run()
