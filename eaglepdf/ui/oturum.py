"""Belge oturumu: bir sekmeye ait belge ve ona bağlı görünüm durumu (sekme değişince saklanıp geri yüklenir).

Görüntüleyici/paneller tektir; oturum yalnızca *belgeye özgü* durumu tutar. Ortak olanlar (araç, görünüm modu,
ayarlar) pencerede kalır. Plan: `docs/sekmeler-plani.md`.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..core.belge import Belge

EN_COK_SEKME = 8


@dataclass
class BelgeOturumu:
    belge: Belge
    gecerli_sayfa: int = 0
    olcek: float = 1.0
    arama_metni: str = ""
    arama_sonuclari: list = field(default_factory=list)
    arama_no: int = -1
    panel_sekmesi: int = 0   # 0 küçük resimler, 1 yer imleri

    def ayni_dosya_mi(self, yol) -> bool:
        """Oturumun belgesi `yol` ile aynı dosya mı? (Windows: büyük/küçük harf duyarsız, çözümlenmiş yol.)"""
        if self.belge.yol is None or yol is None:
            return False
        from pathlib import Path
        try:
            return Path(self.belge.yol).resolve() == Path(yol).resolve()
        except OSError:
            return False
