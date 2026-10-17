"""Belge oturumu: bir sekmeye ait belge ve ona bağlı görünüm durumu (sekme değişince saklanıp geri yüklenir).

Görüntüleyici/paneller tektir; oturum yalnızca *belgeye özgü* durumu tutar. Ortak olanlar (araç, görünüm modu,
ayarlar) pencerede kalır. Plan: `docs/sekmeler-plani.md`.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..core.belge import Belge

EN_COK_SEKME = 8
BUYUK_BELGE_BAYT = 200 * 1024 * 1024   # bunun üstündeki dosyada bellek bilgisi gösterilir


@dataclass
class BelgeOturumu:
    belge: Belge
    gecerli_sayfa: int = 0
    olcek: float = 1.0
    arama_metni: str = ""
    arama_sonuclari: list = field(default_factory=list)
    arama_no: int = -1
    arama_acik: bool = False   # bul çubuğu görünür mü
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


def sekme_basligi(oturum: BelgeOturumu) -> str:
    """Sekme yazısı: dosya adı (yoksa “Adsız”); kaydedilmemiş değişiklikte başına “● ”."""
    ad = oturum.belge.yol.name if oturum.belge.yol else "Adsız"
    return ("● " if oturum.belge.degisti else "") + ad


def sekme_ipucu(oturum: BelgeOturumu) -> str:
    """Sekmenin üzerine gelince: tam yol (yoksa “Kaydedilmemiş yeni belge”) + durum."""
    parcalar = [str(oturum.belge.yol) if oturum.belge.yol else "Kaydedilmemiş yeni belge"]
    if oturum.belge.degisti:
        parcalar.append("Kaydedilmemiş değişiklikler var")
    if oturum.belge.parola_korunur:
        parcalar.append("Parolayla korunuyor")
    if oturum.belge.geri_alinabilir_mi:
        parcalar.append(f"Geri al: {len(oturum.belge._gecmis.geri)} adım, {oturum.belge.geri_al_bayti / (1024 * 1024):.1f} MB")
    return "\n".join(parcalar)
