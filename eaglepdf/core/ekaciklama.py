"""Ek açıklamalar, bağlantılar, yer imleri, form alanları ve görsel imza (Belge'ye karışım olarak eklenir).

Koordinatlar sayfa noktası (pt), sol üst köşe başlangıçlı (PyMuPDF'in sayfa uzayı). Her değiştirici yöntem
geri alınabilir. Renkler "#rrggbb" ya da (r, g, b) 0–1 üçlüsüdür.
"""

import re
from dataclasses import dataclass

import pymupdf

from . import yazitipi
from .gecmis import geri_alinabilir
from .hatalar import BelgeHatasi

TUR_ETIKETLERI = {
    "Highlight": "Vurgu", "Underline": "Altı çizili", "StrikeOut": "Üstü çizili", "Squiggly": "Dalgalı çizgi",
    "Ink": "Çizim", "Text": "Not", "FreeText": "Metin kutusu", "Line": "Çizgi / ok", "Square": "Dikdörtgen",
    "Circle": "Elips", "FileAttachment": "Dosya eki", "Stamp": "Mühür", "Polygon": "Çokgen", "PolyLine": "Çoklu çizgi",
    "Caret": "Ekleme işareti",
}
ISARET_TURLERI = ("vurgu", "alti", "ustu", "dalga")
SEKIL_TURLERI = ("cizgi", "ok", "dikdortgen", "elips")
TASINABILIR = {"Text", "FreeText", "Square", "Circle"}
STIL_ANAHTARI = "EaglePDFStil"  # metin kutusunun kalın/italik bilgisi ("B", "I", "BI")
KENAR_ANAHTARI = "EaglePDFKenar"  # metin kutusu kenarlık rengi ("r g b", 0–1)


def renk_rgb(renk) -> tuple[float, float, float]:
    if isinstance(renk, str):
        r = renk.lstrip("#")
        if len(r) != 6:
            raise BelgeHatasi(f"Geçersiz renk: {renk}")
        return tuple(int(r[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return tuple(renk)


def renk_hex(rgb) -> str:
    if not rgb:
        return ""
    return "#" + "".join(f"{round(c * 255):02x}" for c in rgb[:3])


@dataclass
class EkAciklama:
    sayfa: int
    xref: int
    tur: str          # PDF alt türü: Highlight, Ink, Text, FreeText …
    etiket: str       # Türkçe ad
    rect: tuple[float, float, float, float]
    metin: str
    yazar: str
    tarih: str
    renk: str         # "#rrggbb" ya da ""


@dataclass
class FormAlani:
    sayfa: int
    ad: str
    tur: str          # metin, onay, secenek, acilir, liste, dugme, imza
    deger: object
    secenekler: list[str]
    rect: tuple[float, float, float, float]
    salt_okunur: bool
    xref: int


_FORM_TURLERI = {
    pymupdf.PDF_WIDGET_TYPE_TEXT: "metin", pymupdf.PDF_WIDGET_TYPE_CHECKBOX: "onay",
    pymupdf.PDF_WIDGET_TYPE_RADIOBUTTON: "secenek", pymupdf.PDF_WIDGET_TYPE_COMBOBOX: "acilir",
    pymupdf.PDF_WIDGET_TYPE_LISTBOX: "liste", pymupdf.PDF_WIDGET_TYPE_BUTTON: "dugme",
    pymupdf.PDF_WIDGET_TYPE_SIGNATURE: "imza",
}


def kelimelerden_satirlar(kelimeler: list[tuple]) -> list[tuple[float, float, float, float]]:
    """Seçili kelime kutularını satır satır birleştirir (blok+satır aynı olanlar tek dikdörtgen)."""
    gruplar: dict[tuple, list[float]] = {}
    for x0, y0, x1, y1, _m, blok, satir, *_r in kelimeler:
        g = gruplar.setdefault((blok, satir), [x0, y0, x1, y1])
        g[0], g[1], g[2], g[3] = min(g[0], x0), min(g[1], y0), max(g[2], x1), max(g[3], y1)
    return [tuple(g) for g in gruplar.values()]


class EkAciklamaIslemleri:
    """`Belge` ile birlikte kullanılır: `self._doc` motor belgesi, `self._gecmis` geri alma geçmişi."""

    # --- yardımcılar ---
    def _sayfa(self, i: int) -> pymupdf.Page:
        if not 0 <= i < self._doc.page_count:
            raise BelgeHatasi(f"Sayfa yok: {i + 1}")
        return self._doc[i]

    def _annot(self, sayfa: int, xref: int):
        sayfa_nesnesi = self._sayfa(sayfa)
        a = sayfa_nesnesi.load_annot(xref)
        if a is None:
            raise BelgeHatasi("Ek açıklama bulunamadı.")
        a._sayfa_tutucu = sayfa_nesnesi  # PyMuPDF sayfaya zayıf bağ tutar; sayfa çöpe gitmesin
        return a

    def _bilgi(self, a: pymupdf.Annot, sayfa: int) -> EkAciklama:
        tur = a.type[1]
        if tur == "FreeText":  # kullanıcıya görünen renk yazı rengidir (dolgu /C'de tutulur)
            renk = self._metin_stili(a)[1]
        else:
            renk = a.colors.get("stroke") or a.colors.get("fill") or ()
        info = a.info
        r = a.rect
        return EkAciklama(sayfa, a.xref, tur, TUR_ETIKETLERI.get(tur, tur), (r.x0, r.y0, r.x1, r.y1),
                          info.get("content", ""), info.get("title", ""), info.get("modDate", "") or info.get("creationDate", ""),
                          renk_hex(renk))

    # --- listeleme ve bulma ---
    def ek_listele(self, sayfalar: list[int] | None = None) -> list[EkAciklama]:
        sonuc = []
        for i in (sayfalar if sayfalar is not None else range(self._doc.page_count)):
            for a in self._doc[i].annots() or []:
                if a.type[1] in TUR_ETIKETLERI:
                    sonuc.append(self._bilgi(a, i))
        return sonuc

    def ek_bul(self, sayfa: int, nokta: tuple[float, float], pay: float = 3.0) -> EkAciklama | None:
        """Noktanın altındaki en üstteki ek açıklama (yoksa None)."""
        p = pymupdf.Point(nokta)
        adaylar = [e for e in self.ek_listele([sayfa])
                   if (pymupdf.Rect(e.rect) + (-pay, -pay, pay, pay)).contains(p)]
        return adaylar[-1] if adaylar else None

    # --- ekleme ---
    @geri_alinabilir
    def ek_isaret(self, sayfa: int, tur: str, dikdortgenler: list, renk="#ffeb3b", yazar: str = "") -> int:
        """Metin işareti: vurgu / alti / ustu / dalga. `dikdortgenler`: satır başına bir (x0,y0,x1,y1)."""
        if tur not in ISARET_TURLERI:
            raise BelgeHatasi(f"Bilinmeyen işaret türü: {tur}")
        if not dikdortgenler:
            raise BelgeHatasi("İşaretlenecek metin seçilmedi.")
        p = self._sayfa(sayfa)
        quadlar = [pymupdf.Rect(r).quad for r in dikdortgenler]
        fn = {"vurgu": p.add_highlight_annot, "alti": p.add_underline_annot,
              "ustu": p.add_strikeout_annot, "dalga": p.add_squiggly_annot}[tur]
        a = fn(quads=quadlar)
        a.set_colors(stroke=renk_rgb(renk))
        a.set_info(title=yazar)
        a.update()
        return a.xref

    @geri_alinabilir
    def ek_cizim(self, sayfa: int, cizgiler: list[list[tuple[float, float]]], renk="#c62828", kalinlik: float = 2.0,
                 yazar: str = "") -> int:
        cizgiler = [c for c in cizgiler if len(c) >= 2]
        if not cizgiler:
            raise BelgeHatasi("Çizim boş.")
        a = self._sayfa(sayfa).add_ink_annot(cizgiler)
        a.set_colors(stroke=renk_rgb(renk))
        a.set_border(width=kalinlik)
        a.set_info(title=yazar)
        a.update()
        return a.xref

    @geri_alinabilir
    def ek_not(self, sayfa: int, nokta: tuple[float, float], metin: str, renk="#ffc107", yazar: str = "") -> int:
        a = self._sayfa(sayfa).add_text_annot(pymupdf.Point(nokta), metin, icon="Note")
        a.set_colors(stroke=renk_rgb(renk))
        a.set_info(title=yazar, content=metin)
        a.update()
        return a.xref

    @geri_alinabilir
    def ek_sekil(self, sayfa: int, tur: str, p1: tuple[float, float], p2: tuple[float, float], renk="#c62828",
                 kalinlik: float = 2.0, dolgu=None, yazar: str = "") -> int:
        """tur: cizgi / ok (p1→p2) ya da dikdortgen / elips (p1, p2 karşılıklı köşeler)."""
        if tur not in SEKIL_TURLERI:
            raise BelgeHatasi(f"Bilinmeyen şekil: {tur}")
        p = self._sayfa(sayfa)
        if tur in ("cizgi", "ok"):
            a = p.add_line_annot(pymupdf.Point(p1), pymupdf.Point(p2))
            if tur == "ok":
                a.set_line_ends(pymupdf.PDF_ANNOT_LE_NONE, pymupdf.PDF_ANNOT_LE_CLOSED_ARROW)
        else:
            r = pymupdf.Rect(p1, p2).normalize()
            a = p.add_rect_annot(r) if tur == "dikdortgen" else p.add_circle_annot(r)
        a.set_colors(stroke=renk_rgb(renk), fill=renk_rgb(dolgu) if dolgu else None)
        a.set_border(width=kalinlik)
        a.set_info(title=yazar)
        a.update()
        return a.xref

    @geri_alinabilir
    def ek_metin_kutusu(self, sayfa: int, rect: tuple, metin: str, boyut: float = 14, renk="#000000",
                        kalin: bool = False, italik: bool = False, dolgu=None, kenarlik=None, yazar: str = "") -> int:
        if not metin.strip():
            raise BelgeHatasi("Metin boş.")
        p = self._sayfa(sayfa)
        r = pymupdf.Rect(rect).normalize()
        r = pymupdf.Rect(r.x0, r.y0, max(r.x1, r.x0 + 40), max(r.y1, r.y0 + boyut * 1.6))
        a = p.add_freetext_annot(r, "x", fontsize=boyut, fontname="helv", text_color=renk_rgb(renk),
                                 fill_color=renk_rgb(dolgu) if dolgu else None)
        if kenarlik:  # PyMuPDF kenarlık rengini yalnızca zengin metinde alır; kendi görünümümüzde çiziyoruz
            self._doc.xref_set_key(a.xref, KENAR_ANAHTARI, "(%.3f %.3f %.3f)" % renk_rgb(kenarlik))
        a.set_info(title=yazar, content=metin)
        self._doc.xref_set_key(a.xref, STIL_ANAHTARI, f"({'B' if kalin else ''}{'I' if italik else ''})")
        self._metin_gorunumu(p, a, metin)
        return a.xref

    def _metin_stili(self, a: pymupdf.Annot) -> tuple[float, tuple, bool, bool]:
        da = self._doc.xref_get_key(a.xref, "DA")[1]
        boyut = 14.0
        m = re.search(r"([\d.]+)\s+Tf", da)
        if m:
            boyut = float(m.group(1))
        renk = (0, 0, 0)
        m = re.search(r"([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+rg", da)
        if m:
            renk = tuple(float(x) for x in m.groups())
        stil = self._doc.xref_get_key(a.xref, STIL_ANAHTARI)[1]
        return boyut, renk, "B" in stil, "I" in stil

    def _metin_gorunumu(self, p: pymupdf.Page, a: pymupdf.Annot, metin: str):
        """Serbest metin kutusunun görünümünü (AP) Noto Sans ile üretir; Türkçe harfler doğru çıkar."""
        boyut, renk, kalin, italik = self._metin_stili(a)
        kaynak = yazitipi.kaynak_adi(kalin, italik)
        tampon = yazitipi.tampon(kalin, italik)
        dolgu = tuple(a.colors.get("stroke") or ()) or None  # PyMuPDF serbest metinde dolguyu /C içinde tutar
        kenar_deger = self._doc.xref_get_key(a.xref, KENAR_ANAHTARI)[1]
        kenar = tuple(float(x) for x in kenar_deger.split()) if kenar_deger and kenar_deger != "null" else None
        kenar_kalinlik = 1 if kenar else 0
        r = a.rect
        w, h = r.width, r.height
        pay = 3.0
        for _ in range(60):  # sığmıyorsa kutuyu aşağı doğru büyüt
            tmp = pymupdf.open()
            try:
                tp = tmp.new_page(width=w, height=h)
                tp.insert_font(fontname=kaynak, fontbuffer=tampon)
                if dolgu or kenar:
                    tp.draw_rect(pymupdf.Rect(0, 0, w, h), color=kenar if kenar else None, fill=dolgu if dolgu else None,
                                 width=kenar_kalinlik or 0)
                kalan = tp.insert_textbox(pymupdf.Rect(pay, pay, w - pay, h - pay), metin, fontname=kaynak,
                                          fontsize=boyut, color=renk)
                icerik = tp.read_contents()
            finally:
                tmp.close()
            if kalan >= 0:
                break
            h += boyut * 1.5
        if h != r.height:
            a.set_rect(pymupdf.Rect(r.x0, r.y0, r.x1, r.y0 + h))
        font_xref = p.insert_font(fontname=kaynak, fontbuffer=tampon)
        ap = self._doc.xref_get_key(a.xref, "AP/N")
        if ap[0] != "xref":
            raise BelgeHatasi("Metin kutusunun görünümü oluşturulamadı.")
        ap_xref = int(ap[1].split()[0])
        self._doc.xref_set_key(ap_xref, "BBox", f"[0 0 {w:.3f} {h:.3f}]")
        self._doc.xref_set_key(ap_xref, "Resources", f"<</Font<</{kaynak} {font_xref} 0 R>>>>")
        self._doc.update_stream(ap_xref, icerik)

    # --- değiştirme ve silme ---
    @geri_alinabilir
    def ek_sil(self, sayfa: int, xrefler: list[int]):
        p = self._sayfa(sayfa)
        for x in xrefler:
            a = p.load_annot(x)
            if a is not None:
                p.delete_annot(a)

    @geri_alinabilir
    def ek_metin_degistir(self, sayfa: int, xref: int, metin: str):
        p = self._sayfa(sayfa)
        a = self._annot(sayfa, xref)
        if a.type[1] == "FreeText":
            if not metin.strip():
                raise BelgeHatasi("Metin boş.")
            a.set_info(content=metin)
            self._metin_gorunumu(p, a, metin)
        else:
            a.set_info(content=metin)
            a.update()

    @geri_alinabilir
    def ek_renk_degistir(self, sayfa: int, xref: int, renk):
        p = self._sayfa(sayfa)
        a = self._annot(sayfa, xref)
        rgb = renk_rgb(renk)
        if a.type[1] == "FreeText":  # yazı rengi: DA satırı + yeni görünüm
            da = self._doc.xref_get_key(xref, "DA")[1]
            yeni = re.sub(r"[\d.]+\s+[\d.]+\s+[\d.]+\s+rg", "{:.3f} {:.3f} {:.3f} rg".format(*rgb), da)
            self._doc.xref_set_key(xref, "DA", pymupdf.get_pdf_str(yeni))
            self._metin_gorunumu(p, a, a.info.get("content", ""))
        else:
            a.set_colors(stroke=rgb)
            a.update()

    @geri_alinabilir
    def ek_tasi(self, sayfa: int, xref: int, dx: float, dy: float) -> int:
        """Ek açıklamayı kaydırır; yeni xref'i döndürür (not simgesi silinip yeniden oluşturulduğu için değişir)."""
        p = self._sayfa(sayfa)
        a = self._annot(sayfa, xref)
        tur = a.type[1]
        if tur not in TASINABILIR:
            raise BelgeHatasi("Bu ek açıklama türü taşınamaz; silip yeniden ekleyin.")
        r = a.rect
        if tur == "Text":
            bilgi, renk = a.info, a.colors.get("stroke")
            p.delete_annot(a)
            yeni = p.add_text_annot(pymupdf.Point(r.x0 + dx, r.y0 + dy), bilgi.get("content", ""), icon="Note")
            if renk:
                yeni.set_colors(stroke=renk)
            yeni.set_info(title=bilgi.get("title", ""), content=bilgi.get("content", ""))
            yeni.update()
            return yeni.xref
        a.set_rect(pymupdf.Rect(r.x0 + dx, r.y0 + dy, r.x1 + dx, r.y1 + dy))
        if tur != "FreeText":
            a.update()
        return xref

    # --- bağlantılar ---
    def baglantilar(self, sayfa: int) -> list[dict]:
        """[{xref, rect, tur: 'uri'|'sayfa'|'diger', uri, hedef_sayfa}]"""
        sonuc = []
        for l in self._sayfa(sayfa).get_links():
            kind = l.get("kind")
            r = l["from"]
            sonuc.append({
                "xref": l.get("xref", 0), "rect": (r.x0, r.y0, r.x1, r.y1),
                "tur": "uri" if kind == pymupdf.LINK_URI else "sayfa" if kind == pymupdf.LINK_GOTO else "diger",
                "uri": l.get("uri", ""), "hedef_sayfa": l.get("page", -1),
            })
        return sonuc

    @geri_alinabilir
    def baglanti_ekle(self, sayfa: int, rect: tuple, uri: str | None = None, hedef_sayfa: int | None = None):
        if (uri is None) == (hedef_sayfa is None):
            raise BelgeHatasi("Bağlantı için ya bir adres ya da bir hedef sayfa verin.")
        if uri is not None and not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", uri):
            uri = "https://" + uri.strip()
        if hedef_sayfa is not None and not 0 <= hedef_sayfa < self._doc.page_count:
            raise BelgeHatasi("Hedef sayfa belgede yok.")
        yeni = {"from": pymupdf.Rect(rect).normalize()}
        if uri is not None:
            yeni.update(kind=pymupdf.LINK_URI, uri=uri)
        else:
            yeni.update(kind=pymupdf.LINK_GOTO, page=hedef_sayfa, to=pymupdf.Point(0, 0))
        self._sayfa(sayfa).insert_link(yeni)

    @geri_alinabilir
    def baglanti_sil(self, sayfa: int, xref: int):
        p = self._sayfa(sayfa)
        for l in p.get_links():
            if l.get("xref") == xref:
                p.delete_link(l)
                return
        raise BelgeHatasi("Bağlantı bulunamadı.")

    # --- yer imleri ---
    @geri_alinabilir
    def yer_imleri_ayarla(self, liste: list[tuple[int, str, int]]):
        """liste: (düzey 1'den, başlık, 0 tabanlı sayfa). Düzey atlamaları düzeltilir."""
        toc, onceki = [], 0
        for duzey, baslik, sayfa in liste:
            if not baslik.strip():
                raise BelgeHatasi("Yer imi başlığı boş olamaz.")
            if not 0 <= sayfa < self._doc.page_count:
                raise BelgeHatasi("Yer iminin sayfası belgede yok.")
            duzey = max(1, min(duzey, onceki + 1))
            toc.append([duzey, baslik.strip(), sayfa + 1])
            onceki = duzey
        self._doc.set_toc(toc)

    # --- form alanları ---
    def form_var_mi(self) -> bool:
        return self._doc.is_form_pdf

    def form_alanlari(self, sayfalar: list[int] | None = None) -> list[FormAlani]:
        sonuc = []
        for i in (sayfalar if sayfalar is not None else range(self._doc.page_count)):
            for w in self._doc[i].widgets() or []:
                tur = _FORM_TURLERI.get(w.field_type, "dugme")
                deger = w.field_value
                if tur in ("onay", "secenek"):
                    deger = deger not in (False, "Off", "", None)
                r = w.rect
                sonuc.append(FormAlani(i, w.field_name or "", tur, deger, list(w.choice_values or []),
                                       (r.x0, r.y0, r.x1, r.y1), bool(w.field_flags & 1), w.xref))
        return sonuc

    @geri_alinabilir
    def form_degeri_yaz(self, sayfa: int, xref: int, deger):
        for w in self._sayfa(sayfa).widgets() or []:
            if w.xref == xref:
                tur = _FORM_TURLERI.get(w.field_type, "dugme")
                if tur in ("onay", "secenek"):
                    w.field_value = w.on_state() if deger else "Off"
                else:
                    w.field_value = str(deger)
                w.update()
                try:
                    self._doc.need_appearances(True)  # başka okuyucular alan görünümünü Türkçe harflerle yeniden üretsin
                except Exception:
                    pass
                return
        raise BelgeHatasi("Form alanı bulunamadı.")

    # --- görsel imza ---
    @geri_alinabilir
    def resim_yerlestir(self, sayfa: int, rect: tuple, png: bytes):
        """Sayfaya (saydam) resim koyar; imza için. En/boy oranı korunur."""
        r = pymupdf.Rect(rect).normalize()
        if r.is_empty:
            raise BelgeHatasi("Yerleştirme alanı boş.")
        self._sayfa(sayfa).insert_image(r, stream=png, keep_proportion=True, overlay=True)
