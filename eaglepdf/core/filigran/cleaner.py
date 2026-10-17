"""Seçili bulguları PDF'ten gerçekten siler (gizleme ya da örtme yok).

- ocg / artifact : içerik akışından ilgili `/FmX Do` çağrıları ve `BDC … EMC` bölümleri silinir,
                   XObject kaynak girdisi ve katalogdaki OCG kaydı kaldırılır.
- image          : resmi çizen `/ImX Do` çağrıları ve kaynak girdisi silinir.
- text           : yalnızca filigranı çizen metin operatörleri (Tj/TJ/'/") silinir.
- vector         : çizimin boyama operatörü (f/S/B…) `n` ile değiştirilir (yol çizilmez).
- annot / link   : annotation'lar silinir.
- raster         : taranmış sayfa resmi filigransız haliyle yeniden yazılır.
- meta           : belge bilgileri (Info) alanları ve XMP metadata silinir.
Kayıtta çöp toplama yapılır, artık nesneler dosyadan atılır.
"""
from __future__ import annotations

import os
import re
from collections import defaultdict
from dataclasses import dataclass, field

import pymupdf as fitz

from . import pdfops


@dataclass
class CleanStats:
    output: str = ""
    removed_ops: int = 0
    removed_sections: int = 0
    removed_annots: int = 0
    removed_resources: int = 0
    removed_ocgs: int = 0
    cleaned_images: int = 0
    removed_meta: int = 0
    encrypted: bool = False
    pages_touched: int = 0
    size_before: int = 0
    size_after: int = 0
    warnings: list = field(default_factory=list)
    remaining: list = field(default_factory=list)   # doğrulamada hâlâ bulunan filigranlar

    def summary(self) -> str:
        s = (f"{self.pages_touched} sayfa işlendi · {self.removed_ops} operatör, "
             f"{self.removed_sections} içerik bölümü, {self.removed_annots} annotation, "
             f"{self.removed_resources} kaynak girdisi, {self.removed_ocgs} OCG katmanı silindi")
        if self.cleaned_images:
            s += f", {self.cleaned_images} taranmış sayfa resmi temizlendi"
        if self.removed_meta:
            s += f", {self.removed_meta} belge bilgisi alanı silindi"
        if self.encrypted:
            s += " · çıktı aynı şifreyle korunuyor"
        if self.size_before:
            s += f" · {self.size_before / 1e6:.1f} MB → {self.size_after / 1e6:.1f} MB"
        return s


def output_path_for(path: str) -> str:
    base, ext = os.path.splitext(path)
    return f"{base}_temiz{ext or '.pdf'}"


def _center_in(inner, outer, tol=2.0) -> bool:
    cx = (inner[0] + inner[2]) / 2
    cy = (inner[1] + inner[3]) / 2
    return outer[0] - tol <= cx <= outer[2] + tol and outer[1] - tol <= cy <= outer[3] + tol


def clean_document(doc: fitz.Document, src_path: str, findings, pages=None,
                   finalize: bool = True, progress=None) -> CleanStats:
    """`doc`, `src_path`'ten açılmış ve henüz değiştirilmemiş belge olmalıdır
    (metin eşlemesi için xref numaraları aynı olmalı). `pages` verilirse yalnızca o sayfalar."""
    progress = progress or (lambda *a: None)
    stats = CleanStats()
    page_filter = set(pages) if pages is not None else None

    def wanted(p):
        return page_filter is None or p in page_filter

    wm_xobjs: set[int] = set()
    wm_ocgs: set[int] = set()
    artifact_pages: set[int] = set()
    img_pages: dict[int, set] = defaultdict(set)      # img xref -> sayfalar
    img_rects: dict[tuple, list] = defaultdict(list)  # (img xref, sayfa) -> filigran yerleşimleri
    stream_pages: set[int] = set()
    text_targets: dict[int, list] = defaultdict(list)  # sayfa -> span listesi
    path_targets: dict[int, list] = defaultdict(list)  # sayfa -> çizim listesi
    annot_targets: dict[int, set] = defaultdict(set)
    link_targets: dict[int, set] = defaultdict(set)
    raster_targets: list = []                          # (sayfa, resim xref, model)

    for f in findings:
        for o in f.occurrences:
            p = o.page
            if not wanted(p):
                continue
            if f.kind == "ocg":
                stream_pages.add(p)
            elif f.kind == "artifact":
                stream_pages.add(p)
                artifact_pages.add(p)
            elif f.kind == "image":
                stream_pages.add(p)
                img_pages[o.data["xref"]].add(p)
                img_rects[(o.data["xref"], p)].extend(o.data.get("rects", []))
            elif f.kind == "text":
                text_targets[p].extend(o.data.get("spans", []))
            elif f.kind == "vector":
                path_targets[p].extend(o.data.get("paths", []))
            elif f.kind == "annot":
                annot_targets[p].add(o.data["xref"])
            elif f.kind == "link":
                link_targets[p].add(o.data["uri"])
            elif f.kind == "raster":
                raster_targets.append((p, o.data["xref"], f.data["model"]))
        if f.kind == "ocg":
            wm_xobjs.update(f.data.get("xobjs", []))
            wm_ocgs.update(f.data.get("ocgs", []))

    cache = pdfops.StreamCache(doc)
    edits: dict[int, list] = defaultdict(list)
    touched_pages: set[int] = set()
    processed_streams: set[int] = set()
    resource_drops: set[tuple[int, str]] = set()    # (owner, name)
    resource_kept: set[tuple[int, str]] = set()     # hâlâ çağrılan, silinmemesi gereken
    targets_all = set(wm_xobjs) | set(img_pages)

    # ------------------------------------------------ 1) XObject / bölüm silme
    order = sorted(stream_pages)
    for k, p in enumerate(order):
        progress(k, len(order) + len(text_targets), f"Sayfa {p + 1}: nesneler siliniyor")
        page = doc[p]
        ctm = pdfops.CTMTracker()       # yalnızca sayfa içerik akışlarında (sırayla) izlenir
        for sref in pdfops.page_streams(doc, page):
            xmap = pdfops.resource_map(doc, sref.owner, "XObject", sref.fallback)
            res_owner = (sref.owner if (sref.is_form and _has_own_res(doc, sref.owner))
                         else (sref.fallback or sref.owner))
            for name, x in xmap.items():
                if x in wm_xobjs or (x in img_pages and p in img_pages[x]):
                    resource_drops.add((res_owner, name))
            if sref.xref in processed_streams:
                continue
            processed_streams.add(sref.xref)
            # resim yerleşimi için CTM gerekiyorsa tam ayrıştırma, yoksa hızlı yol
            need_full = any(p in pg for pg in img_pages.values())
            ops = cache.ops(sref.xref) if need_full else cache.quick_ops(sref.xref)
            pmap = None
            i = 0
            while i < len(ops):
                op = ops[i]
                if not sref.is_form:
                    ctm.feed(op)
                if op.name == b"BDC" and len(op.operands) >= 2:
                    tag, props = op.operands[0], op.operands[1]
                    kill = False
                    if tag == b"/OC" and props.startswith(b"/") and wm_ocgs:
                        if pmap is None:
                            pmap = pdfops.resource_map(doc, sref.owner, "Properties", sref.fallback)
                        g = pmap.get(props.decode("latin-1").lstrip("/"))
                        kill = g in wm_ocgs or _ocmd_hits(doc, g, wm_ocgs)
                    elif tag == b"/Artifact" and b"Watermark" in props:
                        j = pdfops.find_emc(ops, i)
                        inner = {xmap.get(o.operands[-1].decode("latin-1").lstrip("/"))
                                 for o in ops[i:j] if o.name == b"Do" and o.operands}
                        kill = p in artifact_pages or bool(inner & targets_all)
                    if kill:
                        j = pdfops.find_emc(ops, i)
                        edits[sref.xref].append((op.start, ops[j].end, b""))
                        stats.removed_sections += 1
                        touched_pages.add(p)
                        i = j + 1
                        continue
                elif op.name == b"Do" and op.operands:
                    x = xmap.get(op.operands[-1].decode("latin-1").lstrip("/"))
                    hit = x in wm_xobjs
                    if not hit and x in img_pages and p in img_pages[x]:
                        rs = img_rects.get((x, p))
                        # sayfa akışında yerleşimi bilinen resimde yalnızca filigran konumunu sil
                        hit = sref.is_form or not rs or any(
                            pdfops.rect_close(ctm.unit_rect(page), r, 3) for r in rs)
                    if not hit and x in img_pages:
                        resource_kept.add((res_owner, op.operands[-1].decode("latin-1").lstrip("/")))
                    if hit:
                        edits[sref.xref].append((op.start, op.end, b""))
                        stats.removed_ops += 1
                        touched_pages.add(p)
                i += 1

    # ------------------------------------------------ 2) metin operatörleri ve vektör çizimler
    if text_targets or path_targets:
        tpages = sorted(set(text_targets) | set(path_targets))
        progress(len(order), len(order) + len(tpages), "Metin / çizim filigranları eşleniyor")
        mdoc, mapping = pdfops.build_marked_doc(src_path, tpages, paths=bool(path_targets))
        try:
            for k, p in enumerate(tpages):
                progress(len(order) + k, len(order) + len(tpages), f"Sayfa {p + 1}: metin / çizim siliniyor")
                trace = mdoc[p].get_texttrace() if text_targets.get(p) else []
                hit_ids = set()
                if path_targets.get(p):
                    drawings = mdoc[p].get_drawings()
                    for tgt in path_targets[p]:
                        found = False
                        for d in drawings:
                            if not pdfops.rect_close(d["rect"], tgt["rect"], 1.5):
                                continue
                            mid = pdfops.id_from_color(d.get("fill") or d.get("color"))
                            if mid in mapping:
                                hit_ids.add(mid)
                                found = True
                        if not found:
                            stats.warnings.append(f"Sayfa {p + 1}: bir çizim akışta bulunamadı")
                for tgt in text_targets[p]:
                    found = False
                    for s in trace:
                        if s["font"] != tgt["font"] or abs(s["size"] - tgt["size"]) > 0.5:
                            continue
                        if not _center_in(s["bbox"], tgt["bbox"]):
                            continue
                        mid = pdfops.id_from_color(s["color"])
                        if mid in mapping:
                            hit_ids.add(mid)
                            found = True
                    if not found:
                        stats.warnings.append(f"Sayfa {p + 1}: '{tgt['text'][:30]}' metni akışta bulunamadı")
                for mid in hit_ids:
                    sx, idx = mapping[mid]
                    op = cache.ops(sx)[idx]
                    if any(e[0] == op.start for e in edits[sx]):
                        continue          # ortak form akışındaki operatör zaten silindi
                    new = b"n" if op.name in pdfops.PATH_PAINT_OPS else pdfops.show_op_replacement(op)
                    edits[sx].append((op.start, op.end, new))
                    stats.removed_ops += 1
                    touched_pages.add(p)
        finally:
            mdoc.close()

    for sx, ed in edits.items():
        doc.update_stream(sx, pdfops.apply_edits(cache.data(sx), ed))

    # ------------------------------------------------ 3) annotation / link
    for p, xrefs in annot_targets.items():
        page = doc[p]
        for a in [a for a in page.annots() if a.xref in xrefs]:
            page.delete_annot(a)
            stats.removed_annots += 1
            touched_pages.add(p)
    for p, uris in link_targets.items():
        page = doc[p]
        for ln in [ln for ln in page.get_links() if ln.get("uri") in uris]:
            page.delete_link(ln)
            stats.removed_annots += 1
            touched_pages.add(p)

    # ------------------------------------------------ 3b) taranmış sayfa resimleri
    if raster_targets:
        from . import raster
        for k, (p, xref, model) in enumerate(raster_targets):
            progress(k, len(raster_targets), f"Sayfa {p + 1}: taranmış resim temizleniyor")
            if raster.clean_page(doc, doc[p], xref, model):
                stats.cleaned_images += 1
                touched_pages.add(p)

    stats.pages_touched = len(touched_pages)
    if not finalize:
        return stats

    # ------------------------------------------------ 3c) belge bilgileri (sayfadan bağımsız)
    for f in findings:
        if f.kind == "meta":
            stats.removed_meta += clean_metadata(doc, f)

    # ------------------------------------------------ 4) kaynak ve katalog temizliği
    for owner, name in resource_drops - resource_kept:
        if pdfops.remove_resource(doc, owner, "XObject", name):
            stats.removed_resources += 1
    if wm_ocgs:
        stats.removed_ocgs = _drop_ocgs(doc, wm_ocgs)
    return stats


def _has_own_res(doc, xref) -> bool:
    return doc.xref_get_key(xref, "Resources")[0] != "null"


def _ocmd_hits(doc, xref, ocgs) -> bool:
    if not xref:
        return False
    if doc.xref_get_key(xref, "Type")[1] != "/OCMD":
        return False
    v = doc.xref_get_key(xref, "OCGs")[1]
    return any(int(x) in ocgs for x in re.findall(r"(\d+)\s+0\s+R", v))


def _drop_ocgs(doc: fitz.Document, ocgs: set[int]) -> int:
    cat = doc.pdf_catalog()
    t, v = doc.xref_get_key(cat, "OCProperties")
    if t == "null":
        return 0
    target_x, key = (cat, "OCProperties")
    if t == "xref":
        target_x, key = pdfops.ref_xref(v), None
        v = doc.xref_object(target_x, compressed=True)
    all_ocgs = {int(x) for x in re.findall(r"(\d+)\s+0\s+R",
                                           doc.xref_get_key(target_x, "OCGs" if key is None else "OCProperties/OCGs")[1])}
    if all_ocgs and all_ocgs <= ocgs:
        doc.xref_set_key(cat, "OCProperties", "null")
        return len(all_ocgs)
    new = v
    for g in ocgs:
        new = re.sub(rf"\b{g}\s+0\s+R\b", "", new)
    if key is None:
        doc.update_object(target_x, new)
    else:
        doc.xref_set_key(cat, key, new)
    return len(ocgs & all_ocgs)


def clean_metadata(doc: fitz.Document, finding) -> int:
    from . import detector
    n = 0
    ix = detector.info_xref(doc)
    if ix:
        for key in doc.xref_get_keys(ix):
            if key in ("CreationDate", "ModDate", "Trapped"):
                continue
            if doc.xref_get_key(ix, key)[0] == "string":
                doc.xref_set_key(ix, key, "null")
                n += 1
    if finding.data.get("xmp") and (doc.get_xml_metadata() or "").strip():
        doc.del_xml_metadata()
        n += 1
    return n


def clean_file(path: str, findings, out_path: str | None = None, progress=None,
               verify: bool = False, pages=None, keep_encryption: bool = True) -> CleanStats:
    """pages: yalnızca bu sayfalar (0 tabanlı) temizlenir; None = hepsi.
    Şifreli belgede keep_encryption=True ise çıktı aynı şifre ve izinlerle korunur."""
    out_path = out_path or output_path_for(path)
    doc = pdfops.open_pdf(path)
    try:
        stats = clean_document(doc, path, findings, pages=pages, progress=progress)
        if progress:
            progress(1, 1, "Kaydediliyor (çöp toplama)…")
        save_kw = {"garbage": 2, "deflate": True}
        if doc.is_encrypted or pdfops.get_password(path):
            if keep_encryption:
                save_kw["encryption"] = fitz.PDF_ENCRYPT_KEEP
                stats.encrypted = True
            else:
                save_kw["encryption"] = fitz.PDF_ENCRYPT_NONE
        doc.save(out_path, **save_kw)
    finally:
        doc.close()
    stats.output = out_path
    stats.size_before = os.path.getsize(path)
    stats.size_after = os.path.getsize(out_path)
    if verify:
        from . import detector
        from . import rules
        if stats.encrypted:
            pdfops.set_password(out_path, pdfops.get_password(path))
        res = detector.scan(out_path, progress=progress, ocr=False)
        sigs = [f.signature for f in findings if f.kind != "meta"]
        scope = set(pages) if pages is not None else None   # aralık dışında kalanlar beklenir
        stats.remaining = [f for f in res.findings
                           if f.kind != "meta"
                           and (scope is None or scope & set(f.pages))
                           and any(rules.signature_matches(f.signature, s) for s in sigs)]
    return stats


def preview_page(path: str, findings, pno: int) -> fitz.Document:
    """Yalnızca `pno` sayfası temizlenmiş, bellekte bir belge döndürür (önizleme için)."""
    doc = pdfops.open_pdf(path)
    clean_document(doc, path, findings, pages=[pno], finalize=False)
    return doc
