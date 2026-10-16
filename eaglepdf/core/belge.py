"""PDF belge işlemleri (Qt'siz, saf Python). Motor: PyMuPDF.

Kurallar: orijinal dosya korunur — kayıt önce geçici dosyaya yazılır, sonra yerine konur;
kaynak dosyanın üzerine yazmak için açıkça `uzerine_yaz=True` verilmelidir.
Sayfa numaraları kullanıcıya 1'den, bu modülde 0'dan başlar.
"""

import os
import re
import secrets
import tempfile
from pathlib import Path

import pymupdf

from .. import metin_tr
from .duzenleme import DuzenlemeIslemleri
from .ekaciklama import EkAciklamaIslemleri
from .gecmis import Gecmis, belgeyi_degistir, geri_alinabilir
from .hatalar import BelgeHatasi, ParolaGerekli
from . import xmp as xmp_modulu
from .ocr import OcrIslemleri

_TUM_IZIN_BITLERI = (pymupdf.PDF_PERM_PRINT | pymupdf.PDF_PERM_MODIFY | pymupdf.PDF_PERM_COPY | pymupdf.PDF_PERM_ANNOTATE
                     | pymupdf.PDF_PERM_FORM | pymupdf.PDF_PERM_ACCESSIBILITY | pymupdf.PDF_PERM_ASSEMBLE | pymupdf.PDF_PERM_PRINT_HQ)
SAYFA_BOYUTLARI = {"A3": (842, 1191), "A4": (595, 842), "A5": (420, 595), "Letter": (612, 792), "Legal": (612, 1008)}


def aralik_coz(metin: str, sayfa_sayisi: int) -> list[int]:
    """'1-3, 5, 8-' gibi bir aralık yazısını 0 tabanlı sıralı sayfa listesine çevirir."""
    sonuc: list[int] = []
    for parca in metin.replace(";", ",").split(","):
        parca = parca.strip()
        if not parca:
            continue
        try:
            if "-" in parca:
                bas, son = (x.strip() for x in parca.split("-", 1))
                bas_n = int(bas) if bas else 1
                son_n = int(son) if son else sayfa_sayisi
            else:
                bas_n = son_n = int(parca)
        except ValueError:
            raise BelgeHatasi(f"Geçersiz sayfa aralığı: “{parca}”") from None
        if bas_n < 1 or son_n > sayfa_sayisi or bas_n > son_n:
            raise BelgeHatasi(f"Sayfa aralığı 1–{sayfa_sayisi} arasında olmalı: “{parca}”")
        sonuc.extend(range(bas_n - 1, son_n))
    if not sonuc:
        raise BelgeHatasi("Sayfa aralığı boş.")
    return sorted(set(sonuc))


def _gecici_yaz(kaydet_fn, hedef: Path, yerine_koymadan_once=None):
    """Hedefle aynı klasörde geçici dosyaya yazar, başarılıysa yerine koyar.
    `yerine_koymadan_once`: Windows'ta açık dosyanın üzerine yazılamadığı için, yazma bittikten sonra
    ve yer değiştirmeden hemen önce çağrılır (örn. kaynak belgeyi kapatmak için)."""
    hedef = Path(hedef)
    fd, gecici = tempfile.mkstemp(suffix=".tmp", prefix=hedef.stem + "_", dir=hedef.parent)
    os.close(fd)
    try:
        kaydet_fn(gecici)
        if yerine_koymadan_once:
            yerine_koymadan_once()
        os.replace(gecici, hedef)
    except BaseException:
        Path(gecici).unlink(missing_ok=True)
        raise


class Belge(OcrIslemleri, EkAciklamaIslemleri, DuzenlemeIslemleri):
    def __init__(self, doc: pymupdf.Document, yol: Path | None):
        self._doc = doc
        self._gecmis = Gecmis()
        self.yol = yol
        self.degisti = False
        self._parola: str | None = None   # parolayla açıldıysa; kayıtta korumayı sürdürmek için
        self._yetki = 0                   # authenticate sonucu: 2 açma, 4 sahip, 6 ikisi
        self._izinler = -1                # açılışta okunan izin bitleri
        self._koru = False                # yalnızca kayıt sırasında: bu yazımda şifrele

    # --- açma ---
    @classmethod
    def ac(cls, yol, parola: str | None = None) -> "Belge":
        yol = Path(yol)
        if not yol.is_file():
            raise BelgeHatasi(f"Dosya bulunamadı: {yol}")
        try:
            doc = pymupdf.open(yol)
        except Exception as hata:
            raise BelgeHatasi(f"PDF açılamadı: {hata}") from None
        yetki = 0
        if doc.needs_pass:
            yetki = doc.authenticate(parola) if parola is not None else 0
            if not yetki:
                doc.close()
                raise ParolaGerekli("Bu belge parolayla korunuyor." if parola is None else "Parola yanlış.")
        if not doc.is_pdf:
            doc.close()
            raise BelgeHatasi("Bu dosya bir PDF belgesi değil.")
        belge = cls(doc, yol)
        if yetki:
            belge._parola, belge._yetki, belge._izinler = parola, yetki, doc.permissions
        return belge

    @property
    def parola_korunur(self) -> bool:
        """Belge parolayla açıldı: Kaydet parolayı (AES-256) sürdürür."""
        return self._parola is not None

    @property
    def sahip_yetkisi_var(self) -> bool:
        return self._yetki in (4, 6)

    @property
    def izinler_kilitli(self) -> bool:
        """Parolalı belgede bazı izinler (yazdırma, kopyalama, düzenleme…) kapalı."""
        return self._parola is not None and (self._izinler & _TUM_IZIN_BITLERI) != _TUM_IZIN_BITLERI

    @property
    def koruma_dusecek(self) -> bool:
        """Belge şifreli ama parolası bilinmiyor (boş açma parolası + sahip kısıtları): kayıtta kısıtlar düşer."""
        return self._parola is None and bool(self._doc.metadata.get("encryption"))

    @classmethod
    def yeni(cls, sayfa_sayisi: int = 1, boyut: str = "A4") -> "Belge":
        doc = pymupdf.open()
        for _ in range(sayfa_sayisi):
            doc.new_page(width=SAYFA_BOYUTLARI[boyut][0], height=SAYFA_BOYUTLARI[boyut][1])
        belge = cls(doc, None)
        belge.degisti = True
        return belge

    def kapat(self):
        self._doc.close()

    # --- bilgi ---
    @property
    def sayfa_sayisi(self) -> int:
        return self._doc.page_count

    def sayfa_boyutu(self, i: int) -> tuple[float, float]:
        """Dönüş uygulanmış sayfa boyutu (nokta)."""
        r = self._doc[i].rect
        return r.width, r.height

    def ozellikler(self) -> dict:
        m = self._doc.metadata or {}
        return {
            "Başlık": m.get("title", ""), "Yazar": m.get("author", ""), "Konu": m.get("subject", ""),
            "Anahtar sözcükler": m.get("keywords", ""), "Oluşturan": m.get("creator", ""),
            "Üretici": m.get("producer", ""), "Oluşturma tarihi": self.pdf_tarihi(m.get("creationDate", "")),
            "Değiştirme tarihi": self.pdf_tarihi(m.get("modDate", "")), "Sayfa sayısı": str(self.sayfa_sayisi),
            "Dosya boyutu": f"{self.yol.stat().st_size} bayt" if self.yol and self.yol.exists() else "",
        }

    DUZENLENEBILIR_OZELLIKLER = {"baslik": "title", "yazar": "author", "konu": "subject", "anahtar": "keywords"}

    @staticmethod
    def pdf_tarihi(metin: str) -> str:
        """`D:20261016233047+03'00'` → `16.10.2026 23:30`; çözülemezse metni olduğu gibi döndürür."""
        m = re.match(r"D:(\d{4})(\d{2})?(\d{2})?(\d{2})?(\d{2})?", metin or "")
        if not m:
            return metin or ""
        y, ay, g, sa, dk = m.groups()
        tarih = f"{g or '01'}.{ay or '01'}.{y}"
        return f"{tarih} {sa}:{dk or '00'}" if sa else tarih

    @geri_alinabilir
    def ozellikleri_ata(self, baslik: str | None = None, yazar: str | None = None, konu: str | None = None,
                        anahtar: str | None = None):
        """Verilen (None olmayan) belge özelliklerini yazar; boş metin alanı siler."""
        yeni = dict(self._doc.metadata or {})
        for ad, deger in (("baslik", baslik), ("yazar", yazar), ("konu", konu), ("anahtar", anahtar)):
            if deger is not None:
                yeni[self.DUZENLENEBILIR_OZELLIKLER[ad]] = deger.strip()
        self._doc.set_metadata(yeni)
        # XMP'de aynı alanlar varsa onları da güncelle (okuyucular XMP'yi Info'ya tercih edebilir)
        xmp = self._doc.get_xml_metadata()
        if xmp and xmp.strip():
            degerler = {k: v for k, v in (("baslik", baslik), ("yazar", yazar), ("konu", konu), ("anahtar", anahtar)) if v is not None}
            yeni_xmp, adet = xmp_modulu.guncelle(xmp, degerler)
            if adet:
                self._doc.set_xml_metadata(yeni_xmp)

    @geri_alinabilir
    def ozellikleri_temizle(self):
        """Tüm üst veriyi (başlık, yazar, tarihler, üretici, XMP) siler; gizlilik için."""
        self._doc.set_metadata({})
        self._doc.del_xml_metadata()

    def icindekiler(self) -> list[tuple[int, str, int]]:
        """Yer imleri: (düzey, başlık, 0 tabanlı sayfa)."""
        return [(d, b, max(s - 1, 0)) for d, b, s in self._doc.get_toc(simple=True)]

    # --- görüntüleme ---
    def render(self, i: int, olcek: float = 1.0):
        """Sayfayı RGB pixmap olarak döndürür (pymupdf.Pixmap: .samples, .width, .height, .stride)."""
        matris = pymupdf.Matrix(olcek, olcek)
        return self._doc[i].get_pixmap(matrix=matris, alpha=False)

    def kelimeler(self, i: int) -> list[tuple]:
        """Sayfadaki kelimeler: (x0, y0, x1, y1, metin, blok, satır, sıra) — metin seçme için, içerik sırasıyla."""
        return [(*k[:4], k[4].replace("\xa0", " "), k[5], k[6], k[7]) for k in self._doc[i].get_text("words")]

    def ara(self, aranan: str) -> list[tuple[int, tuple[float, float, float, float]]]:
        """Türkçe büyük/küçük harf duyarsız arama → [(sayfa, (x0, y0, x1, y1)), ...]."""
        aranan = aranan.strip()
        if not aranan:
            return []
        kucuk_aranan = metin_tr.kucuk(aranan)
        sonuc = []
        for i in range(self.sayfa_sayisi):
            sayfa = self._doc[i]
            metin = sayfa.get_text().replace(" ", " ")  # bazı yazı tipleri sert boşluk üretir (uzunluk korunur)
            kucuk_metin = metin_tr.kucuk(metin)
            bas = 0
            gorulen: set[str] = set()
            while (k := kucuk_metin.find(kucuk_aranan, bas)) != -1:
                bas = k + max(len(kucuk_aranan), 1)
                parca = metin[k:k + len(kucuk_aranan)]
                if parca in gorulen:
                    continue
                gorulen.add(parca)
                for r in sayfa.search_for(parca):
                    sonuc.append((i, (r.x0, r.y0, r.x1, r.y1)))
        return sonuc

    # --- sayfa işlemleri (bellekte; kaydedene dek dosyaya yazılmaz) ---
    @geri_alinabilir
    def sayfa_sil(self, sayfalar: list[int]):
        if len(set(sayfalar)) >= self.sayfa_sayisi:
            raise BelgeHatasi("Belgenin tüm sayfaları silinemez.")
        self._doc.delete_pages(sorted(set(sayfalar)))
        self.degisti = True

    @geri_alinabilir
    def sayfa_dondur(self, sayfalar: list[int], aci: int):
        """aci: 90 (sağa), -90 (sola), 180."""
        for i in sayfalar:
            sayfa = self._doc[i]
            sayfa.set_rotation((sayfa.rotation + aci) % 360)
        self.degisti = True

    @geri_alinabilir
    def bos_sayfa_ekle(self, sonra: int, boyut: str = "A4"):
        """`sonra` sayfasından sonra boş sayfa ekler (-1: en başa)."""
        gen, yuk = SAYFA_BOYUTLARI[boyut]
        self._doc.new_page(pno=sonra + 1, width=gen, height=yuk)
        self.degisti = True

    @geri_alinabilir
    def sayfa_tasi(self, sayfa: int, hedef: int):
        """`sayfa`yı `hedef` konumuna taşır (hedef = taşıma sonrası 0 tabanlı yeni sıra)."""
        sira = list(range(self.sayfa_sayisi))
        sira.insert(hedef, sira.pop(sayfa))
        self._doc.select(sira)
        self.degisti = True

    @geri_alinabilir
    def sirala(self, yeni_sira: list[int]):
        if sorted(yeni_sira) != list(range(self.sayfa_sayisi)):
            raise BelgeHatasi("Sayfa sırası geçersiz.")
        self._doc.select(yeni_sira)
        self.degisti = True

    @geri_alinabilir
    def sona_ekle(self, kaynak: "Belge | Path | str", sayfalar: list[int] | None = None):
        """Başka bir PDF'in sayfalarını (varsayılan: hepsi) sona ekler."""
        diger, kapat = (kaynak, False) if isinstance(kaynak, Belge) else (Belge.ac(kaynak), True)
        try:
            for i in (sayfalar if sayfalar is not None else range(diger.sayfa_sayisi)):
                self._doc.insert_pdf(diger._doc, from_page=i, to_page=i)
        finally:
            if kapat:
                diger.kapat()
        self.degisti = True

    # --- geri al / yinele ---
    @property
    def geri_alinabilir_mi(self) -> bool:
        return bool(self._gecmis.geri)

    @property
    def yinelenebilir_mi(self) -> bool:
        return bool(self._gecmis.ileri)

    def geri_al(self) -> bool:
        if not self._gecmis.geri:
            return False
        self._gecmis.ileri.append((self._doc.tobytes(), self.degisti))
        veri, degisti = self._gecmis.geri.pop()
        belgeyi_degistir(self, veri)
        self.degisti = degisti
        return True

    def yinele(self) -> bool:
        if not self._gecmis.ileri:
            return False
        self._gecmis.geri.append((self._doc.tobytes(), self.degisti))
        veri, _degisti = self._gecmis.ileri.pop()
        belgeyi_degistir(self, veri)
        self.degisti = True
        return True

    # --- kayıt ---
    def kaydet(self, hedef, uzerine_yaz: bool = False, parolayi_koru: bool = True):
        """Geçici dosyaya yaz → yerine koy. Kaynağın üzerine yazmak açık onay (`uzerine_yaz`) ister.
        Belge parolayla açıldıysa `parolayi_koru` ile aynı parola(lar) ve izinlerle şifrelenir; False → parolasız yazar."""
        hedef = Path(hedef)
        self._koru = bool(parolayi_koru and self._parola is not None)
        if self.yol and hedef.resolve() == self.yol.resolve() and not uzerine_yaz:
            raise BelgeHatasi("Açık dosyanın üzerine yazmak için onay gerekir; “Farklı Kaydet” kullanın.")
        if self.yol and hedef.resolve() == self.yol.resolve():
            # Önce geçici dosyaya yaz; Windows'ta yer değiştirmek için açık belge kapatılır, sonra yeniden açılır
            try:
                _gecici_yaz(self._motoru_yaz, hedef, self._doc.close)
            finally:
                if self._doc.is_closed:
                    self._doc = pymupdf.open(hedef)
                    if self._doc.needs_pass:  # şifreli yazıldıysa aynı parolayla yeniden aç
                        self._doc.authenticate(self._parola)
        else:
            _gecici_yaz(self._motoru_yaz, hedef)
            self.yol = hedef
        self.degisti = False

    def _motoru_yaz(self, hedef: str):
        """Belgeyi `hedef`e yazar. Gömülü yazı tipleri yalnızca belgenin bir kopyasında küçültülür (alt küme);
        çalışan belge değişmez, böylece sonradan eklenen metinlerde eksik harf olmaz."""
        kopya = pymupdf.open("pdf", self._doc.tobytes())
        try:
            try:
                kopya.subset_fonts()
            except Exception:
                pass  # yazı tipi küçültülemezse tam yazı tipiyle kaydedilir
            if self._koru:
                kullanici = self._parola if self._yetki in (2, 6) else ""
                # Yalnızca açma parolası biliniyorsa ve kısıtlar varsa sahip parolası bilinmeyen rastgele bir değer olur:
                # aynı parola sahip de olsaydı açma parolasını bilen herkes kısıtları aşardı.
                sahip = self._parola if self.sahip_yetkisi_var or not self.izinler_kilitli else secrets.token_urlsafe(24)
                kopya.save(hedef, garbage=3, deflate=True, encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw=kullanici,
                           owner_pw=sahip, permissions=self._izinler)
            else:
                kopya.save(hedef, garbage=3, deflate=True)
        finally:
            kopya.close()

    def sayfalari_kaydet(self, sayfalar: list[int], hedef):
        """Seçili sayfaları ayrı bir PDF olarak yazar (çıkar)."""
        yeni = pymupdf.open()
        try:
            for i in sayfalar:
                yeni.insert_pdf(self._doc, from_page=i, to_page=i)
            _gecici_yaz(lambda g: yeni.save(g, garbage=3, deflate=True), Path(hedef))
        finally:
            yeni.close()


def birlestir(yollar: list, hedef) -> int:
    """Dosyaları sırayla tek PDF'te birleştirir; sayfa sayısını döndürür."""
    if len(yollar) < 2:
        raise BelgeHatasi("Birleştirmek için en az iki dosya gerekir.")
    hedef = Path(hedef)
    if hedef.resolve() in {Path(y).resolve() for y in yollar}:
        raise BelgeHatasi("Çıktı dosyası, birleştirilen dosyalardan biri olamaz.")
    cikti = pymupdf.open()
    try:
        for yol in yollar:
            b = Belge.ac(yol)
            try:
                cikti.insert_pdf(b._doc)
            finally:
                b.kapat()
        sayi = cikti.page_count
        _gecici_yaz(lambda g: cikti.save(g, garbage=3, deflate=True), hedef)
        return sayi
    finally:
        cikti.close()


def bol(yol, klasor, parcalar: list[list[int]] | None = None, her_n: int | None = None) -> list[Path]:
    """PDF'i böler. `parcalar`: her biri 0 tabanlı sayfa listesi; ya da `her_n`: her n sayfada bir.
    Çıktı adı: <ad>_1.pdf, <ad>_2.pdf …"""
    b = Belge.ac(yol)
    try:
        if parcalar is None:
            if not her_n or her_n < 1:
                raise BelgeHatasi("Bölme ölçütü belirtilmedi.")
            parcalar = [list(range(i, min(i + her_n, b.sayfa_sayisi))) for i in range(0, b.sayfa_sayisi, her_n)]
        klasor = Path(klasor)
        klasor.mkdir(parents=True, exist_ok=True)
        yazilan = []
        for n, sayfalar in enumerate(parcalar, 1):
            hedef = klasor / f"{Path(yol).stem}_{n}.pdf"
            b.sayfalari_kaydet(sayfalar, hedef)
            yazilan.append(hedef)
        return yazilan
    finally:
        b.kapat()
