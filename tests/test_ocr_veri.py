import io
import urllib.error

import pytest

from eaglepdf.core import ocr, ocr_veri
from eaglepdf.core.hatalar import BelgeHatasi
from eaglepdf.core.ocr_veri import IndirmeIptal

_ENG = ocr.tessdata_bul("eng")
pytestmark = pytest.mark.skipif(_ENG is None, reason="Doğrulama için kurulu bir eng.traineddata gerekir")


@pytest.fixture(scope="module")
def gercek() -> bytes:
    return (_ENG / "eng.traineddata").read_bytes()


class SahteCevap:
    """urllib cevabını taklit eder: geturl, headers, read, bağlam yöneticisi."""

    def __init__(self, veri: bytes, url="https://raw.githubusercontent.com/x/y/main/eng.traineddata",
                 uzunluk: int | None = -1, hata_sonra: int | None = None):
        self._f = io.BytesIO(veri)
        self._url = url
        self.headers = {"Content-Length": str(len(veri) if uzunluk == -1 else uzunluk)} if uzunluk is not None else {}
        self._hata_sonra = hata_sonra
        self._okunan = 0

    def geturl(self):
        return self._url

    def read(self, n=-1):
        if self._hata_sonra is not None and self._okunan >= self._hata_sonra:
            raise urllib.error.URLError("bağlantı koptu")
        parca = self._f.read(n)
        self._okunan += len(parca)
        return parca

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def acici_donduren(cevap, kayit=None):
    def acici(url):
        if kayit is not None:
            kayit.append(url)
        return cevap
    return acici


def gecici_dosya_yok(klasor):
    return not [p for p in klasor.iterdir() if p.name.startswith(".")]


# --- indir ---
def test_indir_basarili_dogrulanir_ve_ilerleme_bildirir(tmp_path, gercek):
    ilerlemeler = []
    hedef = ocr_veri.indir("eng", "fast", tmp_path, ilerleme=lambda o, t: ilerlemeler.append((o, t)) or False,
                           acici=acici_donduren(SahteCevap(gercek)))
    assert hedef == tmp_path / "eng.traineddata" and hedef.read_bytes() == gercek
    assert ilerlemeler[-1] == (len(gercek), len(gercek)) and gecici_dosya_yok(tmp_path)


def test_kaliteye_gore_dogru_depo_adresi(tmp_path, gercek):
    kayit = []
    ocr_veri.indir("eng", "fast", tmp_path, acici=acici_donduren(SahteCevap(gercek), kayit))
    ocr_veri.indir("eng", "best", tmp_path, acici=acici_donduren(SahteCevap(gercek), kayit))
    assert kayit[0] == "https://github.com/tesseract-ocr/tessdata_fast/raw/main/eng.traineddata"
    assert kayit[1] == "https://github.com/tesseract-ocr/tessdata_best/raw/main/eng.traineddata"


def test_gecersiz_icerik_reddedilir_mevcut_dosya_korunur(tmp_path, gercek):
    (tmp_path / "eng.traineddata").write_bytes(gercek)
    for kotu in (b"<html>404 Not Found</html>" * 5000, gercek[: len(gercek) // 2], b"\x00" * 100_000):
        with pytest.raises(BelgeHatasi):
            ocr_veri.indir("eng", "fast", tmp_path, acici=acici_donduren(SahteCevap(kotu)))
        assert (tmp_path / "eng.traineddata").read_bytes() == gercek   # eski dosya bozulmadı
        assert gecici_dosya_yok(tmp_path)


def test_yeni_indirme_yoksa_dosya_olusmaz(tmp_path):
    with pytest.raises(BelgeHatasi):
        ocr_veri.indir("tur", "fast", tmp_path, acici=acici_donduren(SahteCevap(b"x" * 100_000)))
    assert not (tmp_path / "tur.traineddata").exists() and gecici_dosya_yok(tmp_path)


def test_eksik_indirme_yakalanir(tmp_path, gercek):
    with pytest.raises(BelgeHatasi, match="eksik"):
        ocr_veri.indir("eng", "fast", tmp_path, acici=acici_donduren(SahteCevap(gercek, uzunluk=len(gercek) + 5000)))
    assert gecici_dosya_yok(tmp_path) and not (tmp_path / "eng.traineddata").exists()


def test_beklenmeyen_sunucuya_yonlendirme_reddedilir(tmp_path, gercek):
    cevap = SahteCevap(gercek, url="https://kotu-site.example/eng.traineddata")
    with pytest.raises(BelgeHatasi, match="Beklenmeyen sunucu"):
        ocr_veri.indir("eng", "fast", tmp_path, acici=acici_donduren(cevap))
    assert not (tmp_path / "eng.traineddata").exists() and gecici_dosya_yok(tmp_path)


def test_izinli_sunuculardan_yonlendirme_kabul(tmp_path, gercek):
    for url in ("https://github.com/a/b/raw/main/eng.traineddata", "https://raw.githubusercontent.com/a/b/eng.traineddata",
                "https://media.githubusercontent.com/media/a/b/eng.traineddata"):
        ocr_veri.indir("eng", "fast", tmp_path, acici=acici_donduren(SahteCevap(gercek, url=url)))


def test_asiri_buyuk_dosya_reddedilir(tmp_path, monkeypatch, gercek):
    monkeypatch.setattr(ocr_veri, "EN_COK_BAYT", 10_000)
    with pytest.raises(BelgeHatasi, match="çok büyük"):
        ocr_veri.indir("eng", "fast", tmp_path, acici=acici_donduren(SahteCevap(gercek)))   # Content-Length bildirimi
    with pytest.raises(BelgeHatasi, match="çok büyük"):
        ocr_veri.indir("eng", "fast", tmp_path, acici=acici_donduren(SahteCevap(gercek, uzunluk=None)))   # bildirimsiz akış
    assert gecici_dosya_yok(tmp_path)


def test_iptal_gecici_dosyayi_siler_eskiyi_korur(tmp_path, gercek):
    (tmp_path / "eng.traineddata").write_bytes(gercek)
    with pytest.raises(IndirmeIptal):
        ocr_veri.indir("eng", "fast", tmp_path, ilerleme=lambda o, t: o > 0, acici=acici_donduren(SahteCevap(gercek)))
    assert (tmp_path / "eng.traineddata").read_bytes() == gercek and gecici_dosya_yok(tmp_path)


def test_ag_hatasi_anlasilir_mesaj(tmp_path):
    def acici(url):
        raise urllib.error.URLError("Name or service not known")
    with pytest.raises(BelgeHatasi, match="İnternet bağlantınızı") as h:
        ocr_veri.indir("eng", "fast", tmp_path, acici=acici)
    assert "Dosyadan Ekle" in str(h.value) and gecici_dosya_yok(tmp_path)


def test_baglanti_yarida_kopar(tmp_path, gercek):
    with pytest.raises(BelgeHatasi, match="kesildi"):
        ocr_veri.indir("eng", "fast", tmp_path, acici=acici_donduren(SahteCevap(gercek, hata_sonra=1000)))
    assert gecici_dosya_yok(tmp_path) and not (tmp_path / "eng.traineddata").exists()


def test_gecersiz_kod_ve_kalite(tmp_path):
    with pytest.raises(BelgeHatasi):
        ocr_veri.indir("../x", "fast", tmp_path, acici=lambda u: pytest.fail("ağa gidilmemeli"))
    with pytest.raises(BelgeHatasi):
        ocr_veri.indir("zzz", "fast", tmp_path, acici=lambda u: pytest.fail("ağa gidilmemeli"))   # kataloğ dışı
    with pytest.raises(BelgeHatasi):
        ocr_veri.indir("eng", "ultra", tmp_path, acici=lambda u: pytest.fail("ağa gidilmemeli"))


def test_katalog_ve_kalite_tutarli():
    assert {"tur", "eng"} <= set(ocr_veri.KATALOG) and all(ocr_veri.kod_gecerli_mi(k) for k in ocr_veri.KATALOG)
    assert set(ocr_veri.KALITELER) == {"fast", "best"}
    assert not ocr_veri.kod_gecerli_mi("") and not ocr_veri.kod_gecerli_mi("a/b") and not ocr_veri.kod_gecerli_mi("..")
    assert ocr_veri.dil_adi("tur") == "Türkçe" and ocr_veri.dil_adi("xyz") == "xyz"


# --- dosyadan ekle ---
def test_dosyadan_ekle_kopyalar(tmp_path, gercek):
    kaynak = tmp_path / "kaynak" / "eng.traineddata"
    kaynak.parent.mkdir()
    kaynak.write_bytes(gercek)
    hedef = ocr_veri.dosyadan_ekle(kaynak, tmp_path / "hedef")
    assert hedef == tmp_path / "hedef" / "eng.traineddata" and hedef.read_bytes() == gercek
    assert gecici_dosya_yok(tmp_path / "hedef")


def test_dosyadan_ekle_hatalar(tmp_path, gercek):
    (tmp_path / "metin.txt").write_text("x")
    with pytest.raises(BelgeHatasi, match="traineddata"):
        ocr_veri.dosyadan_ekle(tmp_path / "metin.txt", tmp_path / "h")
    (tmp_path / "..traineddata").write_bytes(gercek)
    with pytest.raises(BelgeHatasi, match="geçersiz"):
        ocr_veri.dosyadan_ekle(tmp_path / "..traineddata", tmp_path / "h")
    (tmp_path / "bozuk.traineddata").write_bytes(b"x" * 100_000)
    with pytest.raises(BelgeHatasi, match="biçimi tanınmadı"):   # yapı denetimi artık yükleme denemesinden önce yakalar
        ocr_veri.dosyadan_ekle(tmp_path / "bozuk.traineddata", tmp_path / "h")
    with pytest.raises(BelgeHatasi, match="bulunamadı"):
        ocr_veri.dosyadan_ekle(tmp_path / "yok.traineddata", tmp_path / "h")
    assert not (tmp_path / "h").exists() or not list((tmp_path / "h").glob("*"))   # hiçbiri kopyalanmadı


def test_yapi_denetimi_sahte_dosyalari_eler(tmp_path, gercek):
    """Tamamı sıfır dosya OCR yükleme denemesinden hatasız geçiyordu; başlık denetimi bunu yakalar."""
    import struct
    kotu = {
        "sifir": b"\x00" * 100_000,
        "html": b"<html>404 Not Found</html>" * 5000,
        "yarim": gercek[: len(gercek) // 2],
        "ofset_boyut_disi": struct.pack("<i", 2) + struct.pack("<2q", 20, 10**9) + b"\x01" * 100_000,
        "ofset_azalan": struct.pack("<i", 2) + struct.pack("<2q", 50_000, 20) + b"\x01" * 100_000,
        "ofset_baslik_icinde": struct.pack("<i", 2) + struct.pack("<2q", 3, 90_000) + b"\x01" * 100_000,
        "hepsi_yok": struct.pack("<i", 3) + struct.pack("<3q", -1, -1, -1) + b"\x01" * 100_000,
        "n_cok_buyuk": struct.pack("<i", 5000) + b"\x01" * 100_000,
    }
    for ad, veri in kotu.items():
        (tmp_path / "x.traineddata").write_bytes(veri)
        with pytest.raises(BelgeHatasi):
            ocr_veri.dogrula(tmp_path / "x.traineddata", "eng")
    (tmp_path / "x.traineddata").write_bytes(gercek)
    ocr_veri.dogrula(tmp_path / "x.traineddata", "eng")   # gerçek dosya geçer


def test_sifir_dosya_indirmesi_reddedilir(tmp_path, gercek):
    (tmp_path / "eng.traineddata").write_bytes(gercek)
    with pytest.raises(BelgeHatasi):
        ocr_veri.indir("eng", "fast", tmp_path, acici=acici_donduren(SahteCevap(b"\x00" * 100_000)))
    assert (tmp_path / "eng.traineddata").read_bytes() == gercek and gecici_dosya_yok(tmp_path)


def test_dogrula_kucuk_dosya(tmp_path):
    (tmp_path / "k.traineddata").write_bytes(b"x")
    with pytest.raises(BelgeHatasi, match="çok küçük"):
        ocr_veri.dogrula(tmp_path / "k.traineddata", "k")


# --- listele / sil ---
def test_kurulu_listesi_ve_silinebilirlik(tmp_path, gercek, monkeypatch):
    kullanici, sistem = tmp_path / "kullanici", tmp_path / "sistem"
    kullanici.mkdir()
    sistem.mkdir()
    (kullanici / "tur.traineddata").write_bytes(gercek)
    (sistem / "tur.traineddata").write_bytes(b"sistem kopyasi")   # aynı kod: kullanıcı klasörü önce aranır → o listelenir
    (sistem / "eng.traineddata").write_bytes(gercek)
    (sistem / "osd.traineddata").write_bytes(b"osd")
    (sistem / "deu.traineddata").write_bytes(gercek)
    monkeypatch.setattr(ocr, "kullanici_tessdata", lambda: kullanici)
    monkeypatch.setattr(ocr, "tessdata_adaylari", lambda: [kullanici, sistem])
    liste = ocr_veri.kurulu()
    assert [d.kod for d in liste] == ["tur", "eng", "deu"]                 # tur/eng önce; osd yok; yineleme yok
    tur, eng, deu = liste
    assert tur.yol == kullanici / "tur.traineddata" and tur.kullanici_klasorunde and tur.ad == "Türkçe"
    assert not eng.kullanici_klasorunde and not deu.kullanici_klasorunde and deu.ad == "Almanca"
    assert tur.boyut == len(gercek)


def test_sil_yalniz_kullanici_klasorunden(tmp_path, gercek):
    (tmp_path / "tur.traineddata").write_bytes(gercek)
    assert ocr_veri.sil("tur", tmp_path) is True and not (tmp_path / "tur.traineddata").exists()
    with pytest.raises(BelgeHatasi, match="kullanıcı klasöründe yok"):
        ocr_veri.sil("tur", tmp_path)
    for kotu in ("..", "a/b", "../x", ""):
        with pytest.raises(BelgeHatasi):
            ocr_veri.sil(kotu, tmp_path)


def test_indirilen_dil_ocr_tarafindan_bulunur(tmp_path, gercek, monkeypatch):
    monkeypatch.setattr(ocr, "tessdata_adaylari", lambda: [tmp_path])
    assert not ocr.hazir_mi("eng")
    ocr_veri.indir("eng", "fast", tmp_path, acici=acici_donduren(SahteCevap(gercek)))
    assert ocr.hazir_mi("eng") and ocr.kullanilabilir_diller() == ["eng"]


def test_yukleme_denemesi_ikinci_savunma_hatti(tmp_path, gercek, monkeypatch):
    """Yapı denetimi geçse bile Tesseract'ın yükleyemediği dosya reddedilir (yarım dosya, başlığı sağlam)."""
    monkeypatch.setattr(ocr_veri, "_yapiyi_denetle", lambda yol: None)   # birinci hattı kapat
    (tmp_path / "x.traineddata").write_bytes(gercek[: len(gercek) // 2])
    with pytest.raises(BelgeHatasi, match="yüklenemedi"):
        ocr_veri.dogrula(tmp_path / "x.traineddata", "eng")
