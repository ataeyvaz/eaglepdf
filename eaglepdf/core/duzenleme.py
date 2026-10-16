"""Sayfa ve içerik düzenleme: kırp, boyut, filigran, üstbilgi/altbilgi, sayfa numarası, arka plan, kalıcı silme
(redaction), düzleştirme, mühür/resim ve metin düzenleme (Belge'ye karışım olarak eklenir).

Sayfa numaraları 0 tabanlıdır. Koordinatlar, aksi söylenmedikçe, sayfanın görünen (döndürülmüş) uzayında,
nokta (pt) cinsinden ve sol üst köşe başlangıçlıdır. Her değiştirici yöntem geri alınabilir.
"""

import datetime
import re

import pymupdf

from . import yazitipi
from .ekaciklama import renk_rgb
from .gecmis import geri_alinabilir
from .hatalar import BelgeHatasi

EN_AZ_SAYFA_BOYUTU = 20.0
EN_COK_SAYFA_BOYUTU = 14400.0
KONUMLAR = ("ust-sol", "ust-orta", "ust-sag", "alt-sol", "alt-orta", "alt-sag")
SAYFA_NO_BICIMLERI = ("{n}", "Sayfa {n}", "{n} / {toplam}", "Sayfa {n} / {toplam}", "- {n} -")
MUHUR_METINLERI = ("ONAYLANDI", "REDDEDİLDİ", "TASLAK", "GİZLİ", "ACİL", "KOPYA", "FİNAL", "İNCELENDİ", "İMZALANDI")


def _bos_degil(sayfalar):
    if not sayfalar:
        raise BelgeHatasi("Sayfa seçilmedi.")
    return sorted(set(sayfalar))


def sayfa_numarasi_metni(bicim: str, n: int, toplam: int) -> str:
    return bicim.replace("{n}", str(n)).replace("{toplam}", str(toplam))


def bilgi_metni(sablon: str, sayfa_no: int, toplam: int, dosya: str = "", tarih: datetime.date | None = None) -> str:
    """Üstbilgi/altbilgi yer tutucuları: {sayfa}, {toplam}, {tarih}, {dosya}."""
    tarih = tarih or datetime.date.today()
    return (sablon.replace("{sayfa}", str(sayfa_no)).replace("{toplam}", str(toplam))
            .replace("{tarih}", tarih.strftime("%d.%m.%Y")).replace("{dosya}", dosya))


class DuzenlemeIslemleri:
    """`Belge` ile birlikte kullanılır: `self._doc` motor belgesi, `self.yol` dosya yolu."""

    # --- yardımcılar ---
    def _sayfa_nesnesi(self, i: int) -> pymupdf.Page:
        if not 0 <= i < self._doc.page_count:
            raise BelgeHatasi(f"Sayfa yok: {i + 1}")
        return self._doc[i]

    @staticmethod
    def _yazi_tipi_ekle(p: pymupdf.Page, kalin=False, italik=False) -> str:
        ad = yazitipi.kaynak_adi(kalin, italik)
        p.insert_font(fontname=ad, fontbuffer=yazitipi.tampon(kalin, italik))
        return ad

    def _yaz(self, p: pymupdf.Page, x: float, taban_y: float, metin: str, boyut: float, renk, kalin=False,
             italik=False, opaklik: float = 1.0):
        """Görünen uzayda (x, taban_y) noktasına, sayfa döndürülmüş olsa da dik okunacak biçimde metin yazar."""
        ad = self._yazi_tipi_ekle(p, kalin, italik)
        nokta = pymupdf.Point(x, taban_y) * p.derotation_matrix
        p.insert_text(nokta, metin, fontname=ad, fontsize=boyut, color=renk_rgb(renk),
                      rotate=p.rotation, fill_opacity=opaklik, stroke_opacity=opaklik)

    @staticmethod
    def _metin_genisligi(metin: str, boyut: float, kalin=False, italik=False) -> float:
        return yazitipi.font(kalin, italik).text_length(metin, fontsize=boyut)

    # --- kırpma ---
    @geri_alinabilir
    def kirp(self, sayfalar: list[int], sol: float, ust: float, sag: float, alt: float):
        """Görünen sayfanın kenarlarından belirtilen miktarları (pt) kırpar; içerik silinmez, görünür alan daralır."""
        if min(sol, ust, sag, alt) < 0:
            raise BelgeHatasi("Kırpma miktarları eksi olamaz.")
        for i in _bos_degil(sayfalar):
            p = self._sayfa_nesnesi(i)
            r = p.rect
            yeni = pymupdf.Rect(r.x0 + sol, r.y0 + ust, r.x1 - sag, r.y1 - alt)
            if yeni.width < EN_AZ_SAYFA_BOYUTU or yeni.height < EN_AZ_SAYFA_BOYUTU:
                raise BelgeHatasi(f"Sayfa {i + 1}: kırpma sonrası alan çok küçük kalıyor.")
            un = yeni * p.derotation_matrix
            cb = p.cropbox
            p.set_cropbox(pymupdf.Rect(un.x0 + cb.x0, un.y0 + cb.y0, un.x1 + cb.x0, un.y1 + cb.y0))

    @geri_alinabilir
    def kirpmayi_kaldir(self, sayfalar: list[int]):
        for i in _bos_degil(sayfalar):
            p = self._sayfa_nesnesi(i)
            p.set_cropbox(p.mediabox)

    def icerik_sinirlari(self, i: int) -> tuple[float, float, float, float] | None:
        """Sayfadaki görünür içeriğin (metin, resim, çizim) sınırlayıcı kutusu; boşsa None."""
        p = self._sayfa_nesnesi(i)
        kutular = [pymupdf.Rect(b[:4]) for b in p.get_text("blocks")]
        kutular += [pymupdf.Rect(r) for r in (info["bbox"] for info in p.get_image_info())]
        kutular += [pymupdf.Rect(d["rect"]) for d in p.get_drawings() if d.get("rect") is not None]
        kutular = [k for k in kutular if not k.is_empty and not k.is_infinite]
        if not kutular:
            return None
        toplam = kutular[0]
        for k in kutular[1:]:
            toplam |= k
        toplam &= p.rect
        return (toplam.x0, toplam.y0, toplam.x1, toplam.y1)

    @geri_alinabilir
    def otomatik_kirp(self, sayfalar: list[int], pay: float = 12.0):
        """Her sayfayı içeriğine göre kırpar (çevresinde `pay` pt boşluk bırakır); boş sayfalar atlanır."""
        for i in _bos_degil(sayfalar):
            s = self.icerik_sinirlari(i)
            if s is None:
                continue
            p = self._sayfa_nesnesi(i)
            r = p.rect
            sol, ust = max(s[0] - pay, 0), max(s[1] - pay, 0)
            sag, alt = max(r.x1 - s[2] - pay, 0), max(r.y1 - s[3] - pay, 0)
            yeni = pymupdf.Rect(r.x0 + sol, r.y0 + ust, r.x1 - sag, r.y1 - alt)
            if yeni.width < EN_AZ_SAYFA_BOYUTU or yeni.height < EN_AZ_SAYFA_BOYUTU:
                continue
            un = yeni * p.derotation_matrix
            cb = p.cropbox
            p.set_cropbox(pymupdf.Rect(un.x0 + cb.x0, un.y0 + cb.y0, un.x1 + cb.x0, un.y1 + cb.y0))

    # --- sayfa boyutu ---
    @geri_alinabilir
    def sayfa_boyutu_degistir(self, sayfalar: list[int], genislik: float, yukseklik: float):
        """Sayfaları yeni boyuta (pt) ölçekleyerek yerleştirir (en/boy oranı korunur, ortalanır).
        Ek açıklamalar ve form alanları sayfaya işlenir (düzleşir); bağlantılar korunmaz."""
        if not (EN_AZ_SAYFA_BOYUTU <= genislik <= EN_COK_SAYFA_BOYUTU and EN_AZ_SAYFA_BOYUTU <= yukseklik <= EN_COK_SAYFA_BOYUTU):
            raise BelgeHatasi("Sayfa boyutu 20–14400 pt arasında olmalı.")
        for i in _bos_degil(sayfalar):
            eski = self._sayfa_nesnesi(i)
            kaynak = pymupdf.open()
            try:
                kaynak.insert_pdf(self._doc, from_page=i, to_page=i)
                kaynak.bake(annots=True, widgets=True)
                g0, y0 = eski.rect.width, eski.rect.height
                olcek = min(genislik / g0, yukseklik / y0)
                g, y = g0 * olcek, y0 * olcek
                yer = pymupdf.Rect((genislik - g) / 2, (yukseklik - y) / 2, (genislik + g) / 2, (yukseklik + y) / 2)
                yeni = self._doc.new_page(pno=i, width=genislik, height=yukseklik)
                yeni.show_pdf_page(yer, kaynak, 0)
                self._doc.delete_page(i + 1)
            finally:
                kaynak.close()

    # --- filigran, arka plan ---
    @geri_alinabilir
    def filigran_metin(self, sayfalar: list[int], metin: str, boyut: float = 60, renk="#808080", aci: float = 45,
                       opaklik: float = 0.3, kalin: bool = True, on_plan: bool = True):
        """Sayfa ortasına, `aci` derece (saat yönünün tersi) eğik saydam metin koyar."""
        if not metin.strip():
            raise BelgeHatasi("Filigran metni boş.")
        if not 0 < opaklik <= 1:
            raise BelgeHatasi("Saydamlık 0 ile 1 arasında olmalı.")
        genislik = self._metin_genisligi(metin, boyut, kalin)
        for i in _bos_degil(sayfalar):
            p = self._sayfa_nesnesi(i)
            r = p.rect
            merkez = pymupdf.Point(r.width / 2, r.height / 2)
            baslangic = pymupdf.Point(merkez.x - genislik / 2, merkez.y + boyut * 0.35)
            ad = self._yazi_tipi_ekle(p, kalin)
            # Görünen uzaydaki noktayı gerçek uzaya çevir; taban çizgisi sayfa dönüşüne ters döndürülür (dik okunur),
            # ardından `aci` kadar merkez etrafında eğilir.
            nokta = baslangic * p.derotation_matrix
            merkez_gercek = merkez * p.derotation_matrix
            p.insert_text(nokta, metin, fontname=ad, fontsize=boyut, color=renk_rgb(renk), fill_opacity=opaklik,
                          stroke_opacity=opaklik, rotate=p.rotation,
                          morph=(merkez_gercek, pymupdf.Matrix(aci)), overlay=not on_plan)

    @geri_alinabilir
    def filigran_resim(self, sayfalar: list[int], png: bytes, genislik_orani: float = 0.5, on_plan: bool = True):
        """Sayfa ortasına (saydamlığı/eğimi hazırlanmış) PNG koyar; sayfa genişliğinin `genislik_orani` kadarı."""
        if not 0 < genislik_orani <= 1:
            raise BelgeHatasi("Genişlik oranı 0 ile 1 arasında olmalı.")
        pix = pymupdf.Pixmap(png)
        oran = pix.height / pix.width
        for i in _bos_degil(sayfalar):
            p = self._sayfa_nesnesi(i)
            r = p.rect
            g = r.width * genislik_orani
            y = g * oran
            kutu = pymupdf.Rect((r.width - g) / 2, (r.height - y) / 2, (r.width + g) / 2, (r.height + y) / 2)
            p.insert_image(kutu * p.derotation_matrix, stream=png, keep_proportion=True,
                           rotate=p.rotation, overlay=not on_plan)

    @geri_alinabilir
    def arka_plan(self, sayfalar: list[int], renk=None, png: bytes | None = None):
        """Sayfa arkasına düz renk ya da resim koyar (içeriğin altında kalır)."""
        if renk is None and png is None:
            raise BelgeHatasi("Arka plan için bir renk ya da resim verin.")
        for i in _bos_degil(sayfalar):
            p = self._sayfa_nesnesi(i)
            kutu = p.rect * p.derotation_matrix
            kutu.normalize()
            if png is not None:
                p.insert_image(kutu, stream=png, keep_proportion=False, rotate=p.rotation, overlay=False)
            else:
                p.draw_rect(kutu, color=None, fill=renk_rgb(renk), overlay=False)

    # --- üstbilgi / altbilgi / sayfa numarası ---
    @geri_alinabilir
    def ustalt_bilgi(self, sayfalar: list[int], ust: tuple[str, str, str] = ("", "", ""),
                     alt: tuple[str, str, str] = ("", "", ""), boyut: float = 10, renk="#000000", kenar: float = 36,
                     kalin: bool = False):
        """Üstbilgi ve altbilgi (sol, orta, sağ). Yer tutucular: {sayfa} {toplam} {tarih} {dosya}."""
        if not any(ust) and not any(alt):
            raise BelgeHatasi("Üstbilgi ya da altbilgi metni girin.")
        dosya = self.yol.name if self.yol else ""
        toplam = self._doc.page_count
        for i in _bos_degil(sayfalar):
            p = self._sayfa_nesnesi(i)
            r = p.rect
            for satir, y in ((ust, kenar), (alt, r.height - kenar)):
                for konum, sablon in zip(("sol", "orta", "sag"), satir):
                    if not sablon:
                        continue
                    metin = bilgi_metni(sablon, i + 1, toplam, dosya)
                    g = self._metin_genisligi(metin, boyut, kalin)
                    x = {"sol": kenar, "orta": (r.width - g) / 2, "sag": r.width - kenar - g}[konum]
                    self._yaz(p, x, y, metin, boyut, renk, kalin)

    @geri_alinabilir
    def sayfa_numarasi_ekle(self, sayfalar: list[int], konum: str = "alt-orta", bicim: str = "{n}", baslangic: int = 1,
                            boyut: float = 11, renk="#000000", kenar: float = 30):
        if konum not in KONUMLAR:
            raise BelgeHatasi(f"Bilinmeyen konum: {konum}")
        if "{n}" not in bicim:
            raise BelgeHatasi("Biçimde {n} bulunmalı.")
        sec = _bos_degil(sayfalar)
        toplam = baslangic + len(sec) - 1
        dikey, yatay = konum.split("-")
        for sira, i in enumerate(sec):
            p = self._sayfa_nesnesi(i)
            r = p.rect
            metin = sayfa_numarasi_metni(bicim, baslangic + sira, toplam)
            g = self._metin_genisligi(metin, boyut)
            x = {"sol": kenar, "orta": (r.width - g) / 2, "sag": r.width - kenar - g}[yatay]
            y = kenar if dikey == "ust" else r.height - kenar
            self._yaz(p, x, y, metin, boyut, renk)

    # --- kalıcı silme (redaction) ve düzleştirme ---
    @geri_alinabilir
    def kalici_sil(self, sayfa: int, dikdortgenler: list[tuple], dolgu="#000000") -> int:
        """Dikdörtgenlerin altındaki metni, resim piksellerini ve çizimleri GERİ DÖNMEYECEK biçimde siler;
        yerine dolgu rengi konur (dolgu=None: boş bırakır). Kaydedilen dosyada içerik kalmaz."""
        if not dikdortgenler:
            raise BelgeHatasi("Silinecek alan seçilmedi.")
        p = self._sayfa_nesnesi(sayfa)
        for r in dikdortgenler:
            p.add_redact_annot(pymupdf.Rect(r).normalize(), fill=renk_rgb(dolgu) if dolgu else False)
        p.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_PIXELS, graphics=pymupdf.PDF_REDACT_LINE_ART_REMOVE_IF_TOUCHED)
        return len(dikdortgenler)

    @geri_alinabilir
    def kalici_sil_metin(self, aranan: str, dolgu="#000000") -> int:
        """Belgedeki `aranan` metnin her geçtiği yeri kalıcı siler; silinen yer sayısını döndürür."""
        sonuclar = self.ara(aranan)
        if not sonuclar:
            raise BelgeHatasi("Aranan metin belgede bulunamadı.")
        per_sayfa: dict[int, list] = {}
        for sayfa, rect in sonuclar:
            per_sayfa.setdefault(sayfa, []).append(rect)
        for sayfa, rects in per_sayfa.items():
            p = self._sayfa_nesnesi(sayfa)
            for r in rects:
                p.add_redact_annot(pymupdf.Rect(r), fill=renk_rgb(dolgu) if dolgu else False)
            p.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE, graphics=pymupdf.PDF_REDACT_LINE_ART_NONE)
        return len(sonuclar)

    @geri_alinabilir
    def duzlestir(self, ek_aciklamalar: bool = True, form_alanlari: bool = True):
        """Ek açıklamaları ve/veya form alanlarını sayfa içeriğine işler; artık düzenlenemezler."""
        if not ek_aciklamalar and not form_alanlari:
            raise BelgeHatasi("Düzleştirilecek bir öğe seçilmedi.")
        self._doc.bake(annots=ek_aciklamalar, widgets=form_alanlari)

    # --- mühür / resim (taşınabilir, yeniden boyutlandırılabilir) ---
    @geri_alinabilir
    def muhur_ekle(self, sayfa: int, rect: tuple, png: bytes, yazar: str = "", ad: str = "") -> int:
        r = pymupdf.Rect(rect).normalize()
        if r.width < 4 or r.height < 4:
            raise BelgeHatasi("Mühür alanı çok küçük.")
        try:
            pymupdf.Pixmap(png)  # geçerli bir resim mi?
        except Exception:
            raise BelgeHatasi("Resim okunamadı.") from None
        # PyMuPDF'in add_stamp_annot'u PNG saydamlığını yok sayar: görünümü kendimiz kurarız.
        # Resim nesnesi, geçici bir sayfaya yerleştirilerek üretilir (saydamlık maskesi dahil), sonra sayfa silinir.
        gecici = self._doc.new_page(-1, width=100, height=100)
        resim_xref = gecici.insert_image(pymupdf.Rect(0, 0, 100, 100), stream=png)
        self._doc.delete_page(self._doc.page_count - 1)
        p = self._sayfa_nesnesi(sayfa)  # sayfa ekleme/silme eski sayfa nesnelerini geçersiz kılar
        a = p.add_stamp_annot(r, stamp=0)
        a.set_rect(r)  # PyMuPDF dikdörtgeni varsayılan damganın en/boy oranına uydurur; istenen kutuyu geri yükle
        ap = self._doc.xref_get_key(a.xref, "AP/N")
        ap_xref = int(ap[1].split()[0])
        w, h = r.width, r.height
        self._doc.xref_set_key(ap_xref, "BBox", f"[0 0 {w:.3f} {h:.3f}]")
        self._doc.xref_set_key(ap_xref, "Matrix", "[1 0 0 1 0 0]")
        self._doc.xref_set_key(ap_xref, "Resources", f"<</XObject<</Im0 {resim_xref} 0 R>>>>")
        self._doc.update_stream(ap_xref, f"q {w:.3f} 0 0 {h:.3f} 0 0 cm /Im0 Do Q".encode())
        a.set_info(title=yazar, content=ad)
        return a.xref

    @geri_alinabilir
    def ek_boyutlandir(self, sayfa: int, xref: int, rect: tuple):
        """Mühür/resim, metin kutusu, dikdörtgen ve elipsin kutusunu değiştirir."""
        p = self._sayfa_nesnesi(sayfa)
        a = p.load_annot(xref)
        if a is None:
            raise BelgeHatasi("Ek açıklama bulunamadı.")
        a._sayfa_tutucu = p
        tur = a.type[1]
        if tur not in ("Stamp", "FreeText", "Square", "Circle"):
            raise BelgeHatasi("Bu ek açıklamanın boyutu değiştirilemez.")
        r = pymupdf.Rect(rect).normalize()
        if r.width < 8 or r.height < 8:
            raise BelgeHatasi("Alan çok küçük.")
        a.set_rect(r)
        if tur in ("Square", "Circle"):
            a.update()
        elif tur == "FreeText":
            self._metin_gorunumu(p, a, a.info.get("content", ""))

    # --- metin düzenleme ---
    def metin_blogu(self, sayfa: int, nokta: tuple[float, float]) -> dict | None:
        """Noktanın altındaki metin bloğu: {rect, metin, boyut, renk, kalin, italik}; yoksa None."""
        p = self._sayfa_nesnesi(sayfa)
        n = pymupdf.Point(nokta)
        for blok in p.get_text("dict")["blocks"]:
            if blok.get("type") != 0:
                continue
            kutu = pymupdf.Rect(blok["bbox"]) + (-2, -2, 2, 2)
            if not kutu.contains(n):
                continue
            satirlar, spanlar = [], []
            for satir in blok["lines"]:
                satirlar.append("".join(s["text"] for s in satir["spans"]))
                spanlar += [s for s in satir["spans"] if s["text"].strip()]
            if not spanlar:
                continue
            ilk = spanlar[0]
            renk = "#{:06x}".format(ilk["color"] & 0xFFFFFF)
            return {"rect": tuple(blok["bbox"]), "metin": "\n".join(satirlar).replace("\xa0", " "), "boyut": round(ilk["size"], 1),
                    "renk": renk, "kalin": bool(ilk["flags"] & 16) or "bold" in ilk["font"].lower(),
                    "italik": bool(ilk["flags"] & 2)}
        return None

    @geri_alinabilir
    def metin_degistir(self, sayfa: int, rect: tuple, yeni_metin: str, boyut: float, renk="#000000",
                       kalin: bool = False, italik: bool = False):
        """`rect` içindeki eski metni kalıcı siler, yerine yeni metni (Noto Sans) aynı yere yazar. Orijinal yazı tipi
        korunamaz; metin sığmazsa boyut küçültülür, yine sığmazsa kutu aşağı uzar."""
        p = self._sayfa_nesnesi(sayfa)
        if p.rotation:
            raise BelgeHatasi("Döndürülmüş sayfada metin düzenlenemez; önce sayfayı eski konumuna döndürün.")
        if not yeni_metin.strip():
            raise BelgeHatasi("Metin boş olamaz. Silmek için “Kalıcı Sil” kullanın.")
        r = pymupdf.Rect(rect).normalize()
        p.add_redact_annot(r, fill=False)
        p.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE, graphics=pymupdf.PDF_REDACT_LINE_ART_NONE)
        ad = self._yazi_tipi_ekle(p, kalin, italik)
        kutu = pymupdf.Rect(r)
        b = float(boyut)
        for _ in range(40):
            kalan = p.insert_textbox(kutu, yeni_metin, fontname=ad, fontsize=b, color=renk_rgb(renk), overlay=True) \
                if self._sigar_mi(kutu, yeni_metin, b, kalin, italik) else -1
            if kalan >= 0:
                return
            if b > 6:
                b -= 0.5
            else:
                kutu = pymupdf.Rect(kutu.x0, kutu.y0, kutu.x1, kutu.y1 + b * 2)
        raise BelgeHatasi("Metin sayfaya sığdırılamadı.")

    def _sigar_mi(self, kutu: pymupdf.Rect, metin: str, boyut: float, kalin: bool, italik: bool) -> bool:
        """Metin, kutuya satır kaydırmayla sığar mı (yazmadan önce ölçer)."""
        font = yazitipi.font(kalin, italik)
        satir_yuk = boyut * 1.2
        genislik = kutu.width
        satir_sayisi = 0
        for par in metin.split("\n"):
            mevcut = ""
            for kelime in par.split(" "):
                dene = (mevcut + " " + kelime).strip() if mevcut else kelime
                if font.text_length(dene, fontsize=boyut) <= genislik or not mevcut:
                    mevcut = dene
                else:
                    satir_sayisi += 1
                    mevcut = kelime
            satir_sayisi += 1
        return satir_sayisi * satir_yuk <= kutu.height + 0.5
