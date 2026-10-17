"""Geri al / yinele: değişiklikten önce belgenin anlık görüntüsü (bayt) alınır.

`@geri_alinabilir` ile işaretlenen `Belge` yöntemleri çalışmadan önce anlık görüntü alır; yöntem hata verirse
görüntü atılır. Bellek iki düzeyde sınırlanır:

* **Belge başına:** en çok `EN_COK_ADIM` adım ve geri-al yığını için `EN_COK_BAYT`.
* **Genel (tüm açık belgeler):** `GENEL_BUTCE`. Aşılınca önce *etkin olmayan* belgelerin en çok bayt tutanından en eski
  görüntüler silinir; sonra etkin belgenin en eskisi (etkin belgede en az bir geri-al adımı her zaman korunur).
"""

import weakref
from functools import wraps

import pymupdf

EN_COK_ADIM = 30
EN_COK_BAYT = 300 * 1024 * 1024        # belge başına (yalnızca geri-al yığını)
GENEL_BUTCE = 400 * 1024 * 1024        # tüm belgelerin geri al/yinele görüntüleri toplamı

_kayitli: "weakref.WeakSet[Gecmis]" = weakref.WeakSet()
_etkin_ref: "weakref.ref[Gecmis] | None" = None


class Gecmis:
    def __init__(self):
        self.geri: list[tuple[bytes, bool]] = []
        self.ileri: list[tuple[bytes, bool]] = []
        _kayitli.add(self)

    def bayt(self) -> int:
        """Bu geçmişin tuttuğu toplam bayt (geri + ileri)."""
        return sum(len(v) for v, _ in self.geri) + sum(len(v) for v, _ in self.ileri)

    def ekle(self, veri: bytes, degisti: bool):
        self.geri.append((veri, degisti))
        self.ileri.clear()
        self.denetle()

    def denetle(self):
        """Belge başına sınırları, sonra genel bütçeyi uygular (ekleme/geri al/yinele sonrası çağrılır)."""
        while len(self.geri) > EN_COK_ADIM or (len(self.geri) > 1 and sum(len(v) for v, _ in self.geri) > EN_COK_BAYT):
            self.geri.pop(0)
        butceyi_uygula()

    def son_geri_at(self):
        if self.geri:
            self.geri.pop()

    def temizle(self):
        """Tüm görüntüleri bırakır (belge kapanırken)."""
        self.geri.clear()
        self.ileri.clear()
        if etkin() is self:
            etkin_ata(None)


def etkin_ata(gecmis: "Gecmis | None"):
    """Etkin sekmenin geçmişi: genel bütçe aşımında en son bunun görüntülerine dokunulur."""
    global _etkin_ref
    _etkin_ref = weakref.ref(gecmis) if gecmis is not None else None


def etkin() -> "Gecmis | None":
    return _etkin_ref() if _etkin_ref is not None else None


def toplam_bayt() -> int:
    return sum(g.bayt() for g in list(_kayitli))


def butceyi_uygula(butce: int | None = None):
    sinir = GENEL_BUTCE if butce is None else butce
    while toplam_bayt() > sinir:
        simdiki = etkin()
        digerleri = [g for g in list(_kayitli) if g is not simdiki and (g.geri or g.ileri)]
        if digerleri:
            kurban = max(digerleri, key=Gecmis.bayt)
            (kurban.geri or kurban.ileri).pop(0)   # en eski geri-al adımı; yoksa en uzak yinele adımı
            continue
        if simdiki is not None and len(simdiki.geri) > 1:
            simdiki.geri.pop(0)
            continue
        break   # tek bir görüntü bütçeyi aşsa bile etkin belgenin son adımı korunur


def geri_alinabilir(fn):
    @wraps(fn)
    def sar(self, *args, **kwargs):
        self._gecmis.ekle(self._doc.tobytes(), self.degisti)
        try:
            sonuc = fn(self, *args, **kwargs)
        except BaseException:
            self._gecmis.son_geri_at()
            raise
        self.degisti = True
        return sonuc

    return sar


def belgeyi_degistir(belge, veri: bytes):
    """Belgenin motor nesnesini baytlardan açılan yenisiyle değiştirir (eskisi kapatılır)."""
    eski = belge._doc
    belge._doc = pymupdf.open("pdf", veri)
    eski.close()
