"""Geri al / yinele: değişiklikten önce belgenin anlık görüntüsü (bayt) alınır.

`@geri_alinabilir` ile işaretlenen `Belge` yöntemleri çalışmadan önce anlık görüntü alır; yöntem hata verirse
görüntü atılır. Bellek sınırı aşılınca en eski görüntüler silinir.
"""

from functools import wraps

import pymupdf

EN_COK_ADIM = 30
EN_COK_BAYT = 300 * 1024 * 1024


class Gecmis:
    def __init__(self):
        self.geri: list[tuple[bytes, bool]] = []
        self.ileri: list[tuple[bytes, bool]] = []

    def ekle(self, veri: bytes, degisti: bool):
        self.geri.append((veri, degisti))
        self.ileri.clear()
        while len(self.geri) > EN_COK_ADIM or (len(self.geri) > 1 and sum(len(v) for v, _ in self.geri) > EN_COK_BAYT):
            self.geri.pop(0)

    def son_geri_at(self):
        if self.geri:
            self.geri.pop()


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
