"""Düşük seviyeli PDF yardımcıları: içerik akışı ayrıştırma, kaynak (resource) çözümleme,
akış düzenleme. PyMuPDF (fitz) üzerine kuruludur."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import pymupdf as fitz

TEXT_SHOW_OPS = {b"Tj", b"TJ", b"'", b'"'}
PATH_PAINT_OPS = {b"S", b"s", b"f", b"F", b"f*", b"B", b"B*", b"b", b"b*"}


# --------------------------------------------------------------------------- açma / şifre

class PasswordRequired(RuntimeError):
    pass


_PASSWORDS: dict[str, str] = {}


def _key(path: str) -> str:
    import os
    return os.path.normcase(os.path.abspath(path))


def set_password(path: str, password: str | None) -> None:
    if password is None:
        _PASSWORDS.pop(_key(path), None)
    else:
        _PASSWORDS[_key(path)] = password


def get_password(path: str) -> str | None:
    return _PASSWORDS.get(_key(path))


def open_pdf(path: str) -> fitz.Document:
    """Belgeyi açar; şifreliyse kayıtlı şifreyle kilidini açar."""
    doc = fitz.open(path)
    if doc.needs_pass:
        pw = get_password(path)
        if not pw or not doc.authenticate(pw):
            doc.close()
            raise PasswordRequired("PDF şifreli: şifre gerekli" + (" (kayıtlı şifre yanlış)" if pw else ""))
    return doc


def try_password(path: str, password: str) -> bool:
    doc = fitz.open(path)
    try:
        return not doc.needs_pass or bool(doc.authenticate(password))
    finally:
        doc.close()


# --------------------------------------------------------------------------- sayfa aralığı

def parse_pages(spec: str, n: int) -> set[int]:
    """'1-5, 8, 10-' biçimini 0 tabanlı sayfa kümesine çevirir (boş = hiçbiri).
    Geçersiz parça ValueError verir."""
    out: set[int] = set()
    for part in re.split(r"[,;\s]+", (spec or "").strip()):
        if not part:
            continue
        m = re.fullmatch(r"(\d*)\s*[-–]\s*(\d*)|(\d+)", part)
        if not m or part in ("-", "–"):
            raise ValueError(f"Geçersiz sayfa ifadesi: '{part}'")
        if m.group(3):
            a = b = int(m.group(3))
        else:
            a = int(m.group(1)) if m.group(1) else 1
            b = int(m.group(2)) if m.group(2) else n
        if a < 1 or b < a:
            raise ValueError(f"Geçersiz sayfa aralığı: '{part}'")
        out.update(range(a - 1, min(b, n)))
    return out


def page_selection(only: str, exclude: str, n: int) -> set[int] | None:
    """Temizlenecek sayfalar; kısıt yoksa None."""
    if not (only or "").strip() and not (exclude or "").strip():
        return None
    pages = parse_pages(only, n) if (only or "").strip() else set(range(n))
    return pages - parse_pages(exclude, n)

_WS = b"\x00\t\n\x0c\r "
_REG = rb"[^\x00\t\n\x0c\r ()<>\[\]{}/%]"
_TOKEN = re.compile(
    rb"(?P<comment>%[^\r\n]*)"
    rb"|(?P<dopen><<)"
    rb"|(?P<dclose>>>)"
    rb"|(?P<hex><[0-9A-Fa-f\x00\t\n\x0c\r ]*>)"
    rb"|(?P<lstr>\((?:[^()\\]|\\.|\((?:[^()\\]|\\.|\((?:[^()\\]|\\.)*\))*\))*\))"
    rb"|(?P<lopen>\()"
    rb"|(?P<arr>[\[\]{}])"
    rb"|(?P<tok>/" + _REG + rb"*|" + _REG + rb"+)",
    re.S,
)
_EI = re.compile(rb"[\x00\t\n\x0c\r ]EI(?=[\x00\t\n\x0c\r ]|$)")
_NUM = re.compile(rb"[+-]?(?:\d+\.?\d*|\.\d+)$")

@dataclass
class Op:
    name: bytes                 # operatör (ör. b"Do", b"TJ"); satır içi resim için b"BI"
    start: int                  # ilk operandın başladığı bayt
    end: int                    # operatörün bittiği bayt
    operands: list = field(default_factory=list)   # üst seviye operand ham baytları


def _skip_literal(data: bytes, i: int) -> int:
    """data[i] == '(' iken, eşleşen ')' sonrasındaki konumu döndürür."""
    depth = 0
    n = len(data)
    while i < n:
        c = data[i]
        if c == 0x5C:          # ters bölü: kaçış karakteri
            i += 2
            continue
        if c == 0x28:
            depth += 1
        elif c == 0x29:
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return n


def tokenize(data: bytes) -> list[Op]:
    """İçerik akışını operatör listesine ayırır. Bozuk akışlarda olabildiğince devam eder."""
    ops: list[Op] = []
    operands: list[bytes] = []
    op_start = None
    depth = 0          # dizi / sözlük iç içeliği
    item_start = 0     # üst seviye dizi/sözlük operandının başlangıcı
    pos, n = 0, len(data)
    while pos < n:
        restart = None
        for m in _TOKEN.finditer(data, pos):
            kind = m.lastgroup
            if kind == "comment":
                continue
            ts, te = m.span()
            if kind == "lopen":            # çok derin iç içe parantezli metin
                te = _skip_literal(data, ts)
                restart = te
            if op_start is None:
                op_start = ts
            if kind == "tok":
                tok = data[ts:te]
                if not tok:
                    continue
                if tok[0] == 0x2F or _NUM.match(tok):   # ad ya da sayı
                    if depth == 0:
                        operands.append(tok)
                    continue
                if depth:
                    continue                            # true/false/null gibi sözlük içi değerler
                if tok == b"ID":
                    em = _EI.search(data, te + 1)
                    end = em.end() if em else n
                    bi_start = ops.pop().start if ops and ops[-1].name == b"BI" else op_start
                    ops.append(Op(b"BI", bi_start, end, []))
                    operands, op_start = [], None
                    restart = end
                    break
                ops.append(Op(tok, op_start, te, operands))
                operands, op_start = [], None
                continue
            if kind == "dopen" or (kind == "arr" and data[ts] in b"[{"):
                if depth == 0:
                    item_start = ts
                depth += 1
                continue
            if kind == "dclose" or kind == "arr":
                depth = max(0, depth - 1)
                if depth == 0:
                    operands.append(data[item_start:te])
                continue
            if depth == 0:
                operands.append(data[ts:te])
            if restart is not None:
                break
        else:
            break
        if restart is None:
            break
        pos = restart
    return ops


_NB = rb"(?<![^\x00\t\n\x0c\r ()<>\[\]{}/%])"     # önünde ad karakteri olmasın
_NA = rb"(?!" + _REG + rb")"                        # arkasında ad karakteri olmasın
_QUICK = re.compile(
    rb"(?P<do>/" + _REG + rb"+)\s*Do" + _NA +
    rb"|(?P<tag>/" + _REG + rb"+)\s*(?P<props><<(?:[^<>]|<<[^<>]*>>|<[^<>]*>)*>>|/" + _REG + rb"+)\s*BDC" + _NA +
    rb"|(?P<btag>/" + _REG + rb"+)\s*BMC" + _NA +
    rb"|" + _NB + rb"(?P<emc>EMC)" + _NA,
    re.S,
)


def quick_ops(data: bytes) -> list[Op]:
    """Hızlı yol: yalnızca Do / BDC / BMC / EMC operatörlerini regex ile çıkarır
    (tam ayrıştırmadan ~50 kat hızlı). Bayt konumları tokenize() ile aynıdır."""
    ops = []
    for m in _QUICK.finditer(data):
        if m.group("do"):
            ops.append(Op(b"Do", m.start(), m.end(), [m.group("do")]))
        elif m.group("tag"):
            ops.append(Op(b"BDC", m.start(), m.end(), [m.group("tag"), m.group("props")]))
        elif m.group("btag"):
            ops.append(Op(b"BMC", m.start(), m.end(), [m.group("btag")]))
        else:
            ops.append(Op(b"EMC", m.start(), m.end(), []))
    return ops


def apply_edits(data: bytes, edits: list[tuple[int, int, bytes]]) -> bytes:
    """(başlangıç, bitiş, yerine) aralıklarını uygular; çakışan aralıklardan ilki geçerlidir."""
    out = []
    pos = 0
    for start, end, repl in sorted(edits, key=lambda e: (e[0], -e[1])):
        if start < pos:
            continue
        out.append(data[pos:start])
        out.append(b" " + repl + b" " if repl else b" ")
        pos = end
    out.append(data[pos:])
    return b"".join(out)


def show_op_replacement(op: Op) -> bytes:
    """Metin gösterme operatörü silinirken satır ilerlemesini korumak için yerine konacak kod."""
    if op.name == b"'":
        return b"T*"
    if op.name == b'"' and len(op.operands) >= 3:
        return op.operands[0] + b" Tw " + op.operands[1] + b" Tc T*"
    return b""


def find_emc(ops: list[Op], i: int) -> int:
    """ops[i] bir BDC/BMC ise eşleşen EMC indeksini döndürür (bulunamazsa son op)."""
    depth = 0
    for j in range(i, len(ops)):
        nm = ops[j].name
        if nm in (b"BDC", b"BMC"):
            depth += 1
        elif nm == b"EMC":
            depth -= 1
            if depth == 0:
                return j
    return len(ops) - 1


class CTMTracker:
    """q / Q / cm operatörlerini izleyerek geçerli dönüşüm matrisini (CTM) tutar.
    Bir sayfanın birden çok içerik akışında aynı nesne kullanılmalıdır."""

    def __init__(self):
        self.ctm = fitz.Matrix(1, 0, 0, 1, 0, 0)
        self.stack = []

    def feed(self, op: Op) -> None:
        if op.name == b"q":
            self.stack.append(fitz.Matrix(self.ctm))
        elif op.name == b"Q":
            if self.stack:
                self.ctm = self.stack.pop()
        elif op.name == b"cm" and len(op.operands) == 6:
            try:
                m = fitz.Matrix(*(float(v) for v in op.operands))
            except ValueError:
                return
            self.ctm = m * self.ctm

    def unit_rect(self, page: fitz.Page) -> fitz.Rect:
        """Birim karenin (resim alanı) sayfa koordinatlarındaki karşılığı."""
        return fitz.Rect(0, 0, 1, 1) * self.ctm * page.transformation_matrix


def rect_close(a, b, tol: float = 2.0) -> bool:
    return all(abs(x - y) <= tol for x, y in zip(a, b))


# --------------------------------------------------------------------------- kaynaklar

_REF = re.compile(r"/([^\s/<>\[\]()]+)\s+(\d+)\s+0\s+R")


def ref_xref(value: str) -> int:
    try:
        return int(value.split()[0])
    except (ValueError, IndexError):
        return 0


def _resources_location(doc: fitz.Document, owner: int):
    """Sahip nesnenin (sayfa ya da form) /Resources konumunu döndürür.
    ('xref', resxref) | ('inline', ownerxref) | None.  Sayfalarda /Parent zinciri izlenir."""
    x = owner
    for _ in range(32):
        t, v = doc.xref_get_key(x, "Resources")
        if t == "xref":
            return "xref", ref_xref(v)
        if t == "dict":
            return "inline", x
        pt, pv = doc.xref_get_key(x, "Parent")
        if pt != "xref":
            return None
        x = ref_xref(pv)
    return None


def _category_location(doc: fitz.Document, owner: int, cat: str):
    """(xref, anahtar_yolu, sözlük_metni) ya da None."""
    loc = _resources_location(doc, owner)
    if loc is None:
        return None
    kind, x = loc
    path = cat if kind == "xref" else "Resources/" + cat
    t, v = doc.xref_get_key(x, path)
    if t == "xref":
        cx = ref_xref(v)
        return cx, None, doc.xref_object(cx, compressed=True)
    if t == "dict":
        return x, path, v
    return None


def resource_map(doc: fitz.Document, owner: int, cat: str, fallback: int = 0) -> dict[str, int]:
    """Kaynak adı -> xref eşlemesi (ör. cat='XObject': {'Fm0': 21217})."""
    loc = _category_location(doc, owner, cat)
    if loc is None and fallback:
        loc = _category_location(doc, fallback, cat)
    if loc is None:
        return {}
    return {name: int(num) for name, num in _REF.findall(loc[2])}


def remove_resource(doc: fitz.Document, owner: int, cat: str, name: str) -> bool:
    loc = _category_location(doc, owner, cat)
    if loc is None:
        return False
    x, path, _ = loc
    key = f"{path}/{name}" if path else name
    doc.xref_set_key(x, key, "null")
    return True


def is_stream(doc: fitz.Document, xref: int) -> bool:
    try:
        return bool(doc.xref_is_stream(xref))
    except Exception:
        return False


@dataclass
class StreamRef:
    xref: int       # akış nesnesi
    owner: int      # kaynakları çözmek için sahip (sayfa ya da form xref)
    fallback: int   # form kaynaksızsa kullanılacak sayfa xref
    is_form: bool


def page_streams(doc: fitz.Document, page: fitz.Page) -> list[StreamRef]:
    """Sayfanın içerik akışları + sayfadan (iç içe dahil) çağrılan tüm Form XObject akışları."""
    refs = [StreamRef(x, page.xref, 0, False) for x in page.get_contents()]
    seen = set()
    try:
        forms = page.get_xobjects()
    except Exception:
        forms = []
    for xref, _name, _invoker, _bbox in forms:
        if xref in seen or not is_stream(doc, xref):
            continue
        seen.add(xref)
        refs.append(StreamRef(xref, xref, page.xref, True))
    return refs


class StreamCache:
    """Akış verisini ve ayrıştırılmış op listesini önbelleğe alır."""

    def __init__(self, doc: fitz.Document):
        self.doc = doc
        self._data: dict[int, bytes] = {}
        self._ops: dict[int, list[Op]] = {}
        self._quick: dict[int, list[Op]] = {}
        self._res: dict[tuple, dict] = {}

    def data(self, xref: int) -> bytes:
        if xref not in self._data:
            try:
                self._data[xref] = self.doc.xref_stream(xref) or b""
            except Exception:
                self._data[xref] = b""
        return self._data[xref]

    def ops(self, xref: int) -> list[Op]:
        if xref not in self._ops:
            self._ops[xref] = tokenize(self.data(xref))
        return self._ops[xref]

    def quick_ops(self, xref: int) -> list[Op]:
        if xref in self._ops:
            return self._ops[xref]
        if xref not in self._quick:
            self._quick[xref] = quick_ops(self.data(xref))
        return self._quick[xref]

    def resource_map(self, owner: int, cat: str, fallback: int = 0) -> dict[str, int]:
        key = (owner, cat, fallback)
        if key not in self._res:
            self._res[key] = resource_map(self.doc, owner, cat, fallback)
        return self._res[key]


# --------------------------------------------------------------------------- isaretli kopya

def color_for_id(i: int) -> bytes:
    r, g, b = (i >> 16) & 255, (i >> 8) & 255, i & 255
    c = b"%.6f %.6f %.6f" % (r / 255, g / 255, b / 255)
    return c + b" rg " + c + b" RG"


def id_from_color(color) -> int:
    if not color or len(color) != 3:
        return 0
    r, g, b = (int(round(c * 255)) for c in color)
    return (r << 16) | (g << 8) | b


def build_marked_doc(path: str, pages: list[int], paths: bool = False):
    """Belgenin bir kopyasını açar; verilen sayfalardaki her metin-gösterme operatörünün
    önüne benzersiz bir renk koyar. Böylece texttrace'teki her span'in hangi akıştaki
    hangi operatörden geldiği renginden okunur. `paths` ile vektör çizimlerin boyama
    operatörleri (f, S, B…) de işaretlenir; get_drawings rengi aynı şekilde eşlenir.
    Döner: (marked_doc, {id: (stream_xref, op_index)})"""
    mdoc = open_pdf(path)
    cache = StreamCache(mdoc)
    mapping: dict[int, tuple[int, int]] = {}
    done = set()
    next_id = 1
    for pno in pages:
        page = mdoc[pno]
        for sref in page_streams(mdoc, page):
            if sref.xref in done:
                continue
            done.add(sref.xref)
            data = cache.data(sref.xref)
            ops = cache.ops(sref.xref)
            edits = []
            for idx, op in enumerate(ops):
                if op.name in TEXT_SHOW_OPS or (paths and op.name in PATH_PAINT_OPS):
                    mapping[next_id] = (sref.xref, idx)
                    edits.append((op.start, op.start, color_for_id(next_id)))
                    next_id += 1
            if edits:
                parts, pos = [], 0
                for start, _e, ins in sorted(edits, key=lambda e: e[0]):
                    parts += [data[pos:start], b" ", ins, b" "]
                    pos = start
                parts.append(data[pos:])
                mdoc.update_stream(sref.xref, b"".join(parts))
    return mdoc, mapping
