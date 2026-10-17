"""Sayfa ve içerik düzenleme: kırp, boyut, filigran, üstbilgi/altbilgi, sayfa numarası, arka plan, kalıcı silme
(redaction), düzleştirme, mühür/resim ve metin düzenleme (Belge'ye karışım olarak eklenir).

Sayfa numaraları 0 tabanlıdır. Koordinatlar, aksi söylenmedikçe, sayfanın görünen (döndürülmüş) uzayında,
nokta (pt) cinsinden ve sol üst köşe başlangıçlıdır. Her değiştirici yöntem geri alınabilir.
"""

import datetime
import os
import re
import zlib

import pymupdf

from . import yazitipi
from .ekaciklama import renk_rgb
from .gecmis import geri_alinabilir
from .hatalar import BelgeHatasi

EN_AZ_SAYFA_BOYUTU = 20.0
EN_COK_SAYFA_BOYUTU = 14400.0
FILIGRAN_KATMANI = "EaglePDF Filigran"  # filigranlar bu isteğe bağlı içerik katmanına etiketlenir (sonradan kaldırılabilsin)
USTALT_KATMANI = "EaglePDF Üstbilgi/Altbilgi"  # üstbilgi/altbilgi de kendi katmanında: Sayfa → Üstbilgi/Altbilgiyi Kaldır
SAYFA_NO_KATMANI = "EaglePDF Sayfa Numarası"
# Metin düzenlemede orijinal yazı tipini bulmak için: ad (boşluksuz, küçük harf) -> Windows yazı tipi dosyaları (normal, kalın, italik, kalın+italik)
SISTEM_YAZI_TIPLERI = {
    "arial": ("arial", "arialbd", "ariali", "arialbi"),
    "timesnewroman": ("times", "timesbd", "timesi", "timesbi"),
    "couriernew": ("cour", "courbd", "couri", "courbi"),
    "calibri": ("calibri", "calibrib", "calibrii", "calibriz"),
    "cambria": ("cambria", "cambriab", "cambriai", "cambriaz"),
    "consolas": ("consola", "consolab", "consolai", "consolaz"),
    "verdana": ("verdana", "verdanab", "verdanai", "verdanaz"),
    "tahoma": ("tahoma", "tahomabd", None, None),
    "segoeui": ("segoeui", "segoeuib", "segoeuii", "segoeuiz"),
    "georgia": ("georgia", "georgiab", "georgiai", "georgiaz"),
    "trebuchetms": ("trebuc", "trebucbd", "trebucit", "trebucbi"),
    "comicsansms": ("comic", "comicbd", "comici", "comicz"),
}
YAZI_TIPI_TAKMA_ADLARI = {"helvetica": "arial", "arialmt": "arial", "times": "timesnewroman", "timesnewromanps": "timesnewroman",
                          "timesnewromanpsmt": "timesnewroman", "courier": "couriernew", "couriernewps": "couriernew",
                          "couriernewpsmt": "couriernew"}
_STIL_SOZCUKLERI = re.compile(r"(bold|italic|oblique|regular|semibold|light|black|medium|bd|mt|ps)+$")
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
             italik=False, opaklik: float = 1.0, oc: int | None = None):
        """Görünen uzayda (x, taban_y) noktasına, sayfa döndürülmüş olsa da dik okunacak biçimde metin yazar.
        `oc`: verilirse metin bu isteğe bağlı içerik katmanına etiketlenir (sonradan kaldırılabilsin)."""
        ad = self._yazi_tipi_ekle(p, kalin, italik)
        nokta = pymupdf.Point(x, taban_y) * p.derotation_matrix
        p.insert_text(nokta, metin, fontname=ad, fontsize=boyut, color=renk_rgb(renk),
                      rotate=p.rotation, fill_opacity=opaklik, stroke_opacity=opaklik, oc=oc)

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
    def _katman(self, ad: str, olustur: bool = True) -> int | None:
        """Adı verilen isteğe bağlı içerik katmanının xref'i (yoksa `olustur`'a göre oluşturur ya da None döner)."""
        for xref, bilgi in (self._doc.get_ocgs() or {}).items():
            if bilgi.get("name") == ad:
                return xref
        return self._doc.add_ocg(ad, on=True) if olustur else None

    def _filigran_katmani(self, olustur: bool = True) -> int | None:
        return self._katman(FILIGRAN_KATMANI, olustur)

    def _katman_sayfalari(self, ad: str) -> list[int]:
        """Adı verilen katmana bağlı içerik taşıyan sayfalar (0 tabanlı)."""
        oc = self._katman(ad, False)
        if oc is None:
            return []
        sonuc = []
        for i in range(self._doc.page_count):
            p = self._doc[i]
            desenler = self._filigran_desenleri(p, oc)
            if desenler and any(d.search(self._doc.xref_stream(x).decode("latin-1"))
                                for d in desenler for x in p.get_contents()):
                sonuc.append(i)
        return sonuc

    def _katmandan_kaldir(self, ad: str, sayfalar: list[int], yok_iletisi: str) -> int:
        """Katmana bağlı tüm içerik bloklarını (metin: BDC…EMC, resim: q…cm /ad Do Q) seçilen sayfalardan siler; adedi döndürür."""
        oc = self._katman(ad, False)
        if oc is None:
            raise BelgeHatasi(yok_iletisi)
        toplam = 0
        for i in _bos_degil(sayfalar):
            p = self._sayfa_nesnesi(i)
            desenler = self._filigran_desenleri(p, oc)
            for x in p.get_contents():
                veri = self._doc.xref_stream(x).decode("latin-1")
                n = 0
                for d in desenler:
                    veri, k = d.subn("", veri)
                    n += k
                if n:
                    self._doc.update_stream(x, veri.encode("latin-1"))
                    toplam += n
        if not toplam:
            raise BelgeHatasi(yok_iletisi)
        return toplam

    def _filigran_blok_adlari(self, p: pymupdf.Page, oc: int) -> list[str]:
        """Sayfanın kaynaklarında filigran katmanına bağlı etiket adları (örn. MC0)."""
        tur, deger = self._doc.xref_get_key(p.xref, "Resources/Properties")
        if tur == "null":
            return []
        if tur == "xref":
            deger = self._doc.xref_object(int(deger.split()[0]), compressed=True)
        return [m.group(1) for m in re.finditer(r"/([^\s/<>\[\]]+)\s+(\d+)\s+0\s+R", deger) if int(m.group(2)) == oc]

    def _filigran_resim_adlari(self, p: pymupdf.Page, oc: int) -> list[str]:
        """Sayfadaki, filigran katmanına bağlı resim nesnelerinin kaynak adları (örn. fzImg0)."""
        adlar = []
        for tup in p.get_images(full=True):
            tur, deger = self._doc.xref_get_key(tup[0], "OC")
            if tur == "xref" and int(deger.split()[0]) == oc:
                adlar.append(tup[7])
        return adlar

    def _filigran_desenleri(self, p: pymupdf.Page, oc: int) -> list[re.Pattern]:
        """İçerik akışında filigrana ait blokları bulan düzenli ifadeler (metin: BDC…EMC, resim: q…cm /ad Do Q)."""
        desenler = []
        metin_adlari = self._filigran_blok_adlari(p, oc)
        if metin_adlari:
            desenler.append(re.compile(rf"/OC\s*/(?:{'|'.join(map(re.escape, metin_adlari))})\s*BDC.*?EMC", re.S))
        resim_adlari = self._filigran_resim_adlari(p, oc)
        if resim_adlari:
            desenler.append(re.compile(
                rf"q\s+(?:[-+\d.eE]+\s+){{6}}cm\s*/(?:{'|'.join(map(re.escape, resim_adlari))})\s+Do\s*Q"))
        return desenler

    def filigran_sayfalari(self) -> list[int]:
        """Filigran içeren sayfalar (0 tabanlı)."""
        return self._katman_sayfalari(FILIGRAN_KATMANI)

    @geri_alinabilir
    def filigranlari_kaldir(self, sayfalar: list[int]) -> int:
        """Bu uygulamayla eklenmiş tüm filigranları seçilen sayfalardan siler; silinen filigran sayısını döndürür."""
        oc = self._katman(FILIGRAN_KATMANI, False)
        return self._katmandan_kaldir(FILIGRAN_KATMANI, sayfalar,
                                      "Belgede filigran yok." if oc is None else "Seçilen sayfalarda filigran bulunamadı.")

    @geri_alinabilir
    def filigran_metin(self, sayfalar: list[int], metin: str, boyut: float = 60, renk="#808080", aci: float = 45,
                       opaklik: float = 0.3, kalin: bool = True, on_plan: bool = True):
        """Sayfa ortasına, `aci` derece (saat yönünün tersi) eğik saydam metin koyar."""
        if not metin.strip():
            raise BelgeHatasi("Filigran metni boş.")
        if not 0 < opaklik <= 1:
            raise BelgeHatasi("Saydamlık 0 ile 1 arasında olmalı.")
        genislik = self._metin_genisligi(metin, boyut, kalin)
        katman = self._filigran_katmani()
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
                          morph=(merkez_gercek, pymupdf.Matrix(aci)), overlay=not on_plan, oc=katman)

    @geri_alinabilir
    def filigran_resim(self, sayfalar: list[int], png: bytes, genislik_orani: float = 0.5, on_plan: bool = True):
        """Sayfa ortasına (saydamlığı/eğimi hazırlanmış) PNG koyar; sayfa genişliğinin `genislik_orani` kadarı."""
        if not 0 < genislik_orani <= 1:
            raise BelgeHatasi("Genişlik oranı 0 ile 1 arasında olmalı.")
        pix = pymupdf.Pixmap(png)
        oran = pix.height / pix.width
        katman = self._filigran_katmani()
        for i in _bos_degil(sayfalar):
            p = self._sayfa_nesnesi(i)
            r = p.rect
            g = r.width * genislik_orani
            y = g * oran
            kutu = pymupdf.Rect((r.width - g) / 2, (r.height - y) / 2, (r.width + g) / 2, (r.height + y) / 2)
            p.insert_image(kutu * p.derotation_matrix, stream=png, keep_proportion=True,
                           rotate=p.rotation, overlay=not on_plan, oc=katman)

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
        katman = self._katman(USTALT_KATMANI)
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
                    self._yaz(p, x, y, metin, boyut, renk, kalin, oc=katman)

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
        katman = self._katman(SAYFA_NO_KATMANI)
        for sira, i in enumerate(sec):
            p = self._sayfa_nesnesi(i)
            r = p.rect
            metin = sayfa_numarasi_metni(bicim, baslangic + sira, toplam)
            g = self._metin_genisligi(metin, boyut)
            x = {"sol": kenar, "orta": (r.width - g) / 2, "sag": r.width - kenar - g}[yatay]
            y = kenar if dikey == "ust" else r.height - kenar
            self._yaz(p, x, y, metin, boyut, renk, oc=katman)

    def ustalt_sayfalari(self) -> list[int]:
        """Bu uygulamayla eklenmiş üstbilgi/altbilgi içeren sayfalar (0 tabanlı)."""
        return self._katman_sayfalari(USTALT_KATMANI)

    @geri_alinabilir
    def ustalt_kaldir(self, sayfalar: list[int]) -> int:
        """Bu uygulamayla eklenmiş üstbilgi/altbilgi metinlerini seçilen sayfalardan siler; silinen metin sayısını döndürür."""
        return self._katmandan_kaldir(USTALT_KATMANI, sayfalar, "Seçilen sayfalarda bu uygulamayla eklenmiş üstbilgi/altbilgi yok.")

    def sayfa_numarasi_sayfalari(self) -> list[int]:
        """Bu uygulamayla eklenmiş sayfa numarası içeren sayfalar (0 tabanlı)."""
        return self._katman_sayfalari(SAYFA_NO_KATMANI)

    @geri_alinabilir
    def sayfa_numarasi_kaldir(self, sayfalar: list[int]) -> int:
        """Bu uygulamayla eklenmiş sayfa numaralarını seçilen sayfalardan siler; silinen numara sayısını döndürür."""
        return self._katmandan_kaldir(SAYFA_NO_KATMANI, sayfalar, "Seçilen sayfalarda bu uygulamayla eklenmiş sayfa numarası yok.")

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
        """Noktanın altındaki metin bloğu: {rect, metin, boyut, renk, kalin, italik, yazi_tipi}; yoksa None."""
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
                    "italik": bool(ilk["flags"] & 2), "yazi_tipi": ilk["font"]}
        return None

    @staticmethod
    def _yazi_tipi_anahtari(ad: str) -> str:
        """'ABCDEF+Calibri-BoldItalic' -> 'calibri' (alt küme öneki, stil ekleri ve harf dışı karakterler atılır)."""
        ad = ad.split("+", 1)[-1].lower()
        ad = re.sub(r"[^a-z]", "", ad)
        onceki = None
        while onceki != ad:
            onceki, ad = ad, _STIL_SOZCUKLERI.sub("", ad)
        return YAZI_TIPI_TAKMA_ADLARI.get(ad, ad)

    @staticmethod
    def _yazi_tipi_isler_mi(metin: str, **kaynak) -> pymupdf.Font | None:
        """Yazı tipi (fontfile=… ya da fontbuffer=…) metnin her harfini içeriyor mu ve PDF'e yazılınca aynı metin geri okunuyor mu?
        Evetse `pymupdf.Font` döner (satır genişliği ölçmek için); değilse None. Alt kümeli/özel kodlamalı yazı tiplerini eler."""
        try:
            font = pymupdf.Font(**kaynak)
            harfler = [c for c in metin if not c.isspace()]
            if not harfler or not all(font.has_glyph(ord(c)) for c in harfler):
                return None
            deneme = metin[:300]
            gecici = pymupdf.open()
            try:
                sayfa = gecici.new_page()
                sayfa.insert_font(fontname="DENEME", **{("fontbuffer" if "fontbuffer" in kaynak else "fontfile"): list(kaynak.values())[0]})
                sayfa.insert_textbox(pymupdf.Rect(10, 10, 580, 830), deneme, fontname="DENEME", fontsize=10)
                okunan = "".join(sayfa.get_text().split())
            finally:
                gecici.close()
            return font if okunan == "".join(deneme.split()) else None
        except Exception:  # noqa: BLE001 - bozuk/okunamayan yazı tipi: yedek yazı tipine düşülür
            return None

    def _yazi_tipi_sec(self, p: pymupdf.Page, orijinal: dict | None, metin: str, kalin: bool, italik: bool):
        """Metin düzenlemede kullanılacak yazı tipi: önce belgenin kendi yazı tipi (gömülüyse ve yeni metnin harflerini
        taşıyorsa), sonra aynı ailenin Windows'taki dosyası, olmazsa Noto Sans. (kaynak adı, Font, açıklama) döner."""
        if orijinal and orijinal.get("yazi_tipi"):
            ad = orijinal["yazi_tipi"]
            ayni_stil = (bool(orijinal.get("kalin")), bool(orijinal.get("italik"))) == (bool(kalin), bool(italik))
            if ayni_stil:   # stil değiştirilmediyse belgedeki yazı tipinin kendisi (kalın/italik hazır gelir)
                anahtar = self._yazi_tipi_anahtari(ad)
                adaylar = sorted(p.get_fonts(full=True), key=lambda t: t[3] != ad)   # tam ad eşleşmesi önce
                for tup in adaylar:
                    # metin sözlüğündeki ad ('Calibri') ile yazı tipi listesindeki ad ('ABCDEF+Calibri Regular') biçimce farklı olabilir
                    if tup[3] != ad and self._yazi_tipi_anahtari(tup[3]) != anahtar:
                        continue
                    try:
                        _, _, _, tampon = self._doc.extract_font(tup[0])
                    except Exception:  # noqa: BLE001
                        break
                    if tampon:
                        font = self._yazi_tipi_isler_mi(metin, fontbuffer=tampon)
                        if font:
                            return f"EPG{zlib.crc32(tampon):08x}", font, ("buf", tampon), f"{ad.split('+', 1)[-1]} (belgedeki yazı tipi)"
                    break
            aile = SISTEM_YAZI_TIPLERI.get(self._yazi_tipi_anahtari(ad))
            if aile and os.name == "nt":
                ad_dosya = aile[(1 if kalin else 0) + (2 if italik else 0)]
                dosya = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", (ad_dosya or "yok") + ".ttf")
                if ad_dosya and os.path.exists(dosya):
                    font = self._yazi_tipi_isler_mi(metin, fontfile=dosya)
                    if font:
                        return f"EPS{zlib.crc32(dosya.encode()):08x}", font, ("dosya", dosya), f"{font.name.split(' Regular')[0]} (Windows yazı tipi)"
        return yazitipi.kaynak_adi(kalin, italik), yazitipi.font(kalin, italik), ("buf", yazitipi.tampon(kalin, italik)), "Noto Sans (yedek yazı tipi)"

    @geri_alinabilir
    def metin_degistir(self, sayfa: int, rect: tuple, yeni_metin: str, boyut: float, renk="#000000",
                       kalin: bool = False, italik: bool = False, orijinal: dict | None = None) -> str:
        """`rect` içindeki eski metni kalıcı siler, yerine yeni metni aynı yere yazar; kullanılan yazı tipinin adını döndürür.
        `orijinal`: `metin_blogu` çıktısı verilirse orijinal yazı tipi korunmaya çalışılır (belgedeki gömülü yazı tipi ya da aynı
        ailenin Windows dosyası; yeni metnin harflerini taşımıyorsa Noto Sans'a düşülür). Metin sığmazsa boyut küçültülür,
        yine sığmazsa kutu aşağı uzar."""
        p = self._sayfa_nesnesi(sayfa)
        if p.rotation:
            raise BelgeHatasi("Döndürülmüş sayfada metin düzenlenemez; önce sayfayı eski konumuna döndürün.")
        if not yeni_metin.strip():
            raise BelgeHatasi("Metin boş olamaz. Silmek için “Kalıcı Sil” kullanın.")
        r = pymupdf.Rect(rect).normalize()
        ad, font, (tur, kaynak), aciklama = self._yazi_tipi_sec(p, orijinal, yeni_metin, kalin, italik)
        p.add_redact_annot(r, fill=False)
        p.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE, graphics=pymupdf.PDF_REDACT_LINE_ART_NONE)
        p.insert_font(fontname=ad, **({"fontbuffer": kaynak} if tur == "buf" else {"fontfile": kaynak}))
        kutu = pymupdf.Rect(r)
        b = float(boyut)
        for _ in range(40):
            kalan = p.insert_textbox(kutu, yeni_metin, fontname=ad, fontsize=b, color=renk_rgb(renk), overlay=True) \
                if self._sigar_mi(kutu, yeni_metin, b, font) else -1
            if kalan >= 0:
                return aciklama
            if b > 6:
                b -= 0.5
            else:
                kutu = pymupdf.Rect(kutu.x0, kutu.y0, kutu.x1, kutu.y1 + b * 2)
        raise BelgeHatasi("Metin sayfaya sığdırılamadı.")

    @staticmethod
    def _sigar_mi(kutu: pymupdf.Rect, metin: str, boyut: float, font: pymupdf.Font) -> bool:
        """Metin, kutuya satır kaydırmayla sığar mı (yazmadan önce ölçer)."""
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
