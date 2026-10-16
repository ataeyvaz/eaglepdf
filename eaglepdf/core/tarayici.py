"""Tarayıcıdan sayfa alma (Windows WIA, `comtypes` ile). Tarayıcı olmayan/Windows dışı makinelerde anlaşılır hata verir.

Not: gerçek bir tarayıcıyla denenmedi (geliştirme makinesinde tarayıcı yok); hata yolları sahte WIA nesnesiyle test edilir.
"""

import sys
import time
from pathlib import Path

from .donustur import Iptal
from .hatalar import BelgeHatasi

WIA_PNG = "{B96B3CAF-0728-11D3-9D7B-0000F81EF32E}"
WIA_TARAYICI = 1
RENK_NIYETI = {"renkli": 1, "gri": 2, "siyahbeyaz": 4}
EN_IYI_KALITE = 0x20000
# bilinen WIA HRESULT'ları (işaretsiz)
HATA_KULLANICI_IPTAL = 0x80210064
HATA_CIHAZ_YOK = 0x80210015
HATA_CIHAZ_MESGUL = 0x80210006
HATA_KAGIT_YOK = 0x80210003
HATA_KAPAK_ACIK = 0x80210016
HATA_BAGLI_DEGIL = 0x80210005


def kullanilabilir() -> bool:
    """WIA bu bilgisayarda kullanılabilir mi (Windows + comtypes)?"""
    if sys.platform != "win32":
        return False
    try:
        import comtypes.client  # noqa: F401
        return True
    except ImportError:
        return False


def _wia_olustur(ad: str):
    import comtypes.client
    return comtypes.client.CreateObject(ad)


def hata_cevir(kod: int | None, ayrinti: str = "") -> BelgeHatasi:
    kod = (kod or 0) & 0xFFFFFFFF
    if kod == HATA_KULLANICI_IPTAL:
        return Iptal("Tarama iptal edildi.")
    mesajlar = {
        HATA_CIHAZ_YOK: "Tarayıcı bulunamadı. Tarayıcının bağlı ve açık olduğundan emin olun.",
        HATA_BAGLI_DEGIL: "Tarayıcıya bağlanılamadı. Kabloyu/ağ bağlantısını ve gücünü kontrol edin.",
        HATA_CIHAZ_MESGUL: "Tarayıcı şu an meşgul. Başka bir işlem bitince yeniden deneyin.",
        HATA_KAGIT_YOK: "Tarayıcıda kâğıt yok ya da kâğıt sıkıştı.",
        HATA_KAPAK_ACIK: "Tarayıcının kapağı açık.",
    }
    return BelgeHatasi(mesajlar.get(kod, f"Tarama başarısız oldu ({ayrinti or hex(kod)})."))


def tarayicilar() -> list[str]:
    """Bağlı tarayıcı adları; WIA yoksa ya da hata olursa boş liste."""
    if not kullanilabilir():
        return []
    try:
        yonetici = _wia_olustur("WIA.DeviceManager")
        sonuc = []
        for i in range(1, yonetici.DeviceInfos.Count + 1):
            bilgi = yonetici.DeviceInfos.Item(i)
            if bilgi.Type == WIA_TARAYICI:
                sonuc.append(str(bilgi.Properties("Name").Value))
        return sonuc
    except Exception:
        return []


def tara(klasor, renk: str = "renkli", wia_olusturucu=None) -> Path:
    """Tek sayfa tarar (Windows'un tarama penceresi açılır), PNG dosyası yolunu döndürür.
    İptalde `Iptal`, sorunlarda Türkçe mesajlı `BelgeHatasi` fırlatır."""
    if renk not in RENK_NIYETI:
        raise BelgeHatasi(f"Bilinmeyen renk modu: {renk}")
    if wia_olusturucu is None:
        if not kullanilabilir():
            raise BelgeHatasi("Tarayıcıdan almak yalnızca Windows'ta (WIA) çalışır.")
        wia_olusturucu = _wia_olustur
    klasor = Path(klasor)
    klasor.mkdir(parents=True, exist_ok=True)
    hedef = klasor / f"tarama_{time.strftime('%Y%m%d-%H%M%S')}_{time.time_ns() % 100000}.png"
    try:
        pencere = wia_olusturucu("WIA.CommonDialog")
        resim = pencere.ShowAcquireImage(WIA_TARAYICI, RENK_NIYETI[renk], EN_IYI_KALITE, WIA_PNG, False, True, True)
        if resim is None:
            raise Iptal("Tarama iptal edildi.")
        resim.SaveFile(str(hedef))
    except BelgeHatasi:
        raise
    except Exception as h:
        kod = getattr(h, "hresult", None)
        if kod is None and getattr(h, "args", None):
            kod = h.args[0] if isinstance(h.args[0], int) else None
        raise hata_cevir(kod, str(h)) from None
    if not hedef.is_file():
        raise BelgeHatasi("Tarama dosyası oluşturulamadı.")
    return hedef
