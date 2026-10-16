"""Sertifikalı dijital imza (pyHanko, MIT): imzala, doğrula, imza alanı ekle, kendinden imzalı sertifika üret (Qt'siz).

İmza PDF'e *artımlı güncelleme* olarak eklenir; belgenin önceki baytları değişmez. Bu yüzden imzalama her zaman
kaydedilmiş içerik üzerinden yeni bir dosyaya yapılır (açık belge/özgün dosya korunur). İmzadan sonra belgeyi
PyMuPDF ile yeniden yazıp kaydetmek imzaları geçersiz kılar — arayüz bunu uyarır.
"""
from __future__ import annotations

import datetime
import io
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

from . import yazitipi
from .belge import Belge, _gecici_yaz
from .hatalar import BelgeHatasi

# Görünür imza kutusu için hazır konumlar → (x0, y0, x1, y1) sayfa genişliği/yüksekliği oranı, üstten-sola
KONUMLAR = {
    "sag_alt": (0.55, 0.88, 0.95, 0.96),
    "sol_alt": (0.05, 0.88, 0.45, 0.96),
    "sag_ust": (0.55, 0.04, 0.95, 0.12),
    "sol_ust": (0.05, 0.04, 0.45, 0.12),
}
KONUM_ADLARI = {"sag_alt": "Sağ alt", "sol_alt": "Sol alt", "sag_ust": "Sağ üst", "sol_ust": "Sol üst"}


def _pyhanko():
    """pyHanko ağır içe aktarılır; yalnızca imza işlemlerinde yüklenir."""
    from pyhanko.sign import fields, signers, validation
    return fields, signers, validation


# ------------------------------------------------------------------ sertifika
@dataclass
class SertifikaBilgisi:
    ad: str
    veren: str
    baslangic: datetime.datetime
    bitis: datetime.datetime
    kendinden_imzali: bool

    @property
    def suresi_dolmus(self) -> bool:
        return self.bitis < datetime.datetime.now(datetime.timezone.utc)


def _isim(name) -> str:
    """x509 adından okunabilir ad (CN, yoksa tamamı)."""
    ayrik = name.native if hasattr(name, "native") else {}
    return str(ayrik.get("common_name") or ayrik.get("organization_name") or name.human_friendly)


def imzalayici_yukle(pfx_yolu, parola: str):
    """.pfx/.p12 dosyasından imzalayıcıyı yükler. Parola yanlış/dosya bozuksa Türkçe hata verir."""
    _, signers, _ = _pyhanko()
    yol = Path(pfx_yolu)
    if not yol.is_file():
        raise BelgeHatasi(f"Sertifika dosyası bulunamadı: {yol}")
    try:
        imzalayici = signers.SimpleSigner.load_pkcs12(str(yol), passphrase=parola.encode("utf-8") if parola else None)
    except Exception:
        raise BelgeHatasi("Sertifika açılamadı: parola yanlış ya da dosya geçerli bir .pfx/.p12 değil.") from None
    if imzalayici is None:  # pyHanko hatayı kaydedip None döndürür (yanlış parola / bozuk dosya)
        raise BelgeHatasi("Sertifika açılamadı: parola yanlış ya da dosya geçerli bir .pfx/.p12 değil.")
    return imzalayici


def sertifika_bilgisi(pfx_yolu, parola: str) -> SertifikaBilgisi:
    s = imzalayici_yukle(pfx_yolu, parola)
    c = s.signing_cert
    return SertifikaBilgisi(_isim(c.subject), _isim(c.issuer), c.not_valid_before, c.not_valid_after,
                            c.subject == c.issuer)


def sertifika_olustur(hedef, ad: str, parola: str, eposta: str = "", yil: int = 5) -> Path:
    """Kendinden imzalı bir sertifika + özel anahtarı .pfx olarak yazar.
    Not: kendinden imzalı sertifikaya başka bilgisayarlar *güvenmez*; imza bütünlüğü doğrulanır ama kimlik doğrulanmaz."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    if not ad.strip():
        raise BelgeHatasi("Ad boş olamaz.")
    if not parola:
        raise BelgeHatasi("Sertifika dosyası için bir parola girin.")
    anahtar = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nitelikler = [x509.NameAttribute(NameOID.COMMON_NAME, ad.strip())]
    if eposta.strip():
        nitelikler.append(x509.NameAttribute(NameOID.EMAIL_ADDRESS, eposta.strip()))
    isim = x509.Name(nitelikler)
    simdi = datetime.datetime.now(datetime.timezone.utc)
    sertifika = (x509.CertificateBuilder().subject_name(isim).issuer_name(isim).public_key(anahtar.public_key())
                 .serial_number(x509.random_serial_number()).not_valid_before(simdi - datetime.timedelta(minutes=5))
                 .not_valid_after(simdi + datetime.timedelta(days=365 * max(yil, 1)))
                 .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=True, key_encipherment=False,
                                              data_encipherment=False, key_agreement=False, key_cert_sign=False,
                                              crl_sign=False, encipher_only=False, decipher_only=False), critical=True)
                 .sign(anahtar, hashes.SHA256()))
    from cryptography.hazmat.primitives.serialization import pkcs12
    veri = pkcs12.serialize_key_and_certificates(
        ad.strip().encode("utf-8"), anahtar, sertifika, None, serialization.BestAvailableEncryption(parola.encode("utf-8")))
    hedef = Path(hedef)
    _gecici_yaz(lambda g: Path(g).write_bytes(veri), hedef)
    return hedef


# ------------------------------------------------------------------ imza durumu
def _kaynak_bayt(kaynak) -> bytes:
    """İmzalanacak/denetlenecek baytlar. Kayıtlı ve değişmemiş `Belge` için *dosyanın kendi baytları* (PyMuPDF'in
    yeniden yazdığı kopya var olan imzaları bozar). Değişmiş belgede yeniden yazılan içerik kullanılır."""
    if isinstance(kaynak, Belge):
        if kaynak.yol and not kaynak.degisti and Path(kaynak.yol).is_file() and not kaynak._doc.is_encrypted:
            return Path(kaynak.yol).read_bytes()
        return kaynak._doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_NONE)
    return Path(kaynak).read_bytes()


def imzali_mi(belge: Belge) -> bool:
    """Belgede en az bir doldurulmuş dijital imza var mı? (Boş imza alanı sayılmaz.)"""
    if not belge._doc.get_sigflags() & 1:
        return False
    from pyhanko.pdf_utils.reader import PdfFileReader
    try:
        return bool(PdfFileReader(io.BytesIO(_kaynak_bayt(belge))).embedded_signatures)
    except Exception:
        return False


def bos_imza_alanlari(belge: Belge) -> list[str]:
    """Henüz imzalanmamış imza alanlarının adları."""
    fields, _, _ = _pyhanko()
    from pyhanko.pdf_utils.reader import PdfFileReader
    okuyucu = PdfFileReader(io.BytesIO(_kaynak_bayt(belge)))
    return [ad for ad, _, _ in fields.enumerate_sig_fields(okuyucu, filled_status=False)]


def _yeni_alan_adi(bayt: bytes, istenen: str = "") -> str:
    """Belgede kullanılmayan bir imza alanı adı (Imza1, Imza2, …); `istenen` boşsa ve çakışmıyorsa o kullanılır."""
    fields, _, _ = _pyhanko()
    from pyhanko.pdf_utils.reader import PdfFileReader
    var = {ad for ad, _, _ in fields.enumerate_sig_fields(PdfFileReader(io.BytesIO(bayt)))}
    if istenen.strip():
        if istenen.strip() in var:
            raise BelgeHatasi(f"“{istenen.strip()}” adlı bir imza alanı zaten var.")
        return istenen.strip()
    n = len(var) + 1
    while f"Imza{n}" in var:
        n += 1
    return f"Imza{n}"


def _kutu(belge_doc: pymupdf.Document, sayfa: int, konum: str) -> tuple[int, int, int, int]:
    """Üstten-sola oranları → pyHanko'nun PDF koordinatları (alttan-sola)."""
    if konum not in KONUMLAR:
        raise BelgeHatasi(f"Bilinmeyen konum: {konum}")
    s = belge_doc[sayfa]
    g, y = s.rect.width, s.rect.height
    x0, y0, x1, y1 = KONUMLAR[konum]
    return round(x0 * g), round(y - y1 * y), round(x1 * g), round(y - y0 * y)


def _damga_stili(imzalayici_adi: str):
    """Türkçe karakterli görünür imza kutusu stili (Noto Sans gömülür)."""
    from pyhanko.pdf_utils.font.opentype import GlyphAccumulatorFactory
    from pyhanko.pdf_utils.text import TextBoxStyle
    from pyhanko.stamp import TextStampStyle
    gecici = Path(tempfile.mkdtemp(prefix="eaglepdf_font_")) / "noto.ttf"
    gecici.write_bytes(yazitipi.tampon())
    fabrika = GlyphAccumulatorFactory(str(gecici), font_size=9)
    return TextStampStyle(
        stamp_text="Dijital olarak imzalayan:\n%(signer)s\nTarih: %(ts)s",
        text_box_style=TextBoxStyle(font=fabrika, font_size=9)), gecici.parent


def imzala(kaynak, hedef, pfx_yolu, parola: str, sayfa: int = 0, konum: str | None = "sag_alt",
           alan_adi: str | None = None, neden: str = "", yer: str = "", iletisim: str = "") -> Path:
    """Belgeyi imzalayıp `hedef`e yazar (kaynağın üzerine yazılmaz).
    `konum=None` → görünmez imza. `alan_adi` mevcut boş bir imza alanının adıysa o alan doldurulur."""
    fields, signers, _ = _pyhanko()
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    hedef = Path(hedef)
    if isinstance(kaynak, Belge) and kaynak.yol and hedef.resolve() == kaynak.yol.resolve():
        raise BelgeHatasi("İmzalı kopya, açık dosyanın üzerine yazılamaz; yeni bir ad seçin.")
    imzalayici = imzalayici_yukle(pfx_yolu, parola)
    bayt = _kaynak_bayt(kaynak)
    doc = pymupdf.open("pdf", bayt)
    try:
        if not 0 <= sayfa < doc.page_count:
            raise BelgeHatasi("Sayfa belgenin dışında.")
        kutu = _kutu(doc, sayfa, konum) if konum and not alan_adi else None
    finally:
        doc.close()
    yazici = IncrementalPdfFileWriter(io.BytesIO(bayt))
    alan = alan_adi or _yeni_alan_adi(bayt)
    meta = signers.PdfSignatureMetadata(field_name=alan, reason=neden or None, location=yer or None,
                                        contact_info=iletisim or None, md_algorithm="sha256")
    yeni_alan = None
    damga, font_dizini = None, None
    if not alan_adi:
        yeni_alan = fields.SigFieldSpec(alan, on_page=sayfa, box=kutu)
    if kutu or alan_adi:
        damga, font_dizini = _damga_stili(alan)
    try:
        imzaci = signers.PdfSigner(meta, imzalayici, stamp_style=damga, new_field_spec=yeni_alan)
        cikti = io.BytesIO()
        try:
            imzaci.sign_pdf(yazici, output=cikti)
        except BelgeHatasi:
            raise
        except Exception as h:
            raise BelgeHatasi(f"İmzalanamadı: {h}") from None
    finally:
        if font_dizini:
            import shutil
            shutil.rmtree(font_dizini, ignore_errors=True)
    _gecici_yaz(lambda g: Path(g).write_bytes(cikti.getvalue()), hedef)
    return hedef


def bos_alan_ekle(kaynak, hedef, sayfa: int = 0, konum: str = "sag_alt", alan_adi: str = "") -> tuple[Path, str]:
    """İleride imzalanmak üzere boş (ertelenmiş) imza alanı ekler → (dosya, alan adı)."""
    fields, _, _ = _pyhanko()
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    hedef = Path(hedef)
    if isinstance(kaynak, Belge) and kaynak.yol and hedef.resolve() == kaynak.yol.resolve():
        raise BelgeHatasi("Kopya, açık dosyanın üzerine yazılamaz; yeni bir ad seçin.")
    bayt = _kaynak_bayt(kaynak)
    doc = pymupdf.open("pdf", bayt)
    try:
        if not 0 <= sayfa < doc.page_count:
            raise BelgeHatasi("Sayfa belgenin dışında.")
        kutu = _kutu(doc, sayfa, konum)
    finally:
        doc.close()
    ad = _yeni_alan_adi(bayt, alan_adi)
    yazici = IncrementalPdfFileWriter(io.BytesIO(bayt))
    fields.append_signature_field(yazici, fields.SigFieldSpec(ad, on_page=sayfa, box=kutu))
    cikti = io.BytesIO()
    yazici.write(cikti)
    _gecici_yaz(lambda g: Path(g).write_bytes(cikti.getvalue()), hedef)
    return hedef, ad


# ------------------------------------------------------------------ doğrulama
@dataclass
class ImzaDurumu:
    alan: str
    imzalayan: str
    zaman: datetime.datetime | None
    butunluk_tamam: bool          # imzalanan baytlar değişmedi, imza matematiksel olarak geçerli
    belge_sonradan_degisti: bool  # imzadan sonra izin verilmeyen değişiklik var
    guvenilir: bool               # sertifika güvenilen bir kök zincirine bağlı mı (kendinden imzalıda False)
    ozet: str = ""                # kullanıcıya gösterilecek tek satır
    ayrinti: list[str] = field(default_factory=list)


def dogrula(kaynak, guvenilen_sertifikalar: list | None = None) -> list[ImzaDurumu]:
    """Belgedeki tüm dijital imzaları denetler. Boş liste = imza yok.
    Güven: yalnızca `guvenilen_sertifikalar` (asn1crypto sertifika listesi) ya da imzalayıcının kendisi verilirse sağlanır;
    sistem sertifika deposu kullanılmaz."""
    _, _, validation = _pyhanko()
    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko_certvalidator import ValidationContext
    okuyucu = PdfFileReader(io.BytesIO(_kaynak_bayt(kaynak)))
    sonuc = []
    for gomulu in okuyucu.embedded_signatures:
        baglam = ValidationContext(trust_roots=guvenilen_sertifikalar or [], allow_fetching=False)
        try:
            durum = validation.validate_pdf_signature(gomulu, signer_validation_context=baglam)
        except Exception as h:
            sonuc.append(ImzaDurumu(gomulu.field_name, "?", None, False, False, False,
                                    f"İmza okunamadı: {h}"))
            continue
        imzalayan = _isim(gomulu.signer_cert.subject)
        ayr = []
        if not durum.intact:
            ayr.append("İmzalanan içerik değişmiş.")
        if not durum.valid:
            ayr.append("İmza matematiksel olarak geçerli değil.")
        degisti = bool(durum.modification_level is not None and durum.modification_level.value > 1)
        if degisti:
            ayr.append("İmzadan sonra belgeye izin verilmeyen değişiklikler yapılmış.")
        guvenilir = bool(durum.trusted)
        if not guvenilir:
            ayr.append("Sertifikaya güvenilmiyor (kendinden imzalı ya da tanınmayan veren).")
        tamam = bool(durum.intact and durum.valid)
        if tamam and not degisti:
            ozet = "Geçerli imza" + ("" if guvenilir else " (kimlik doğrulanmadı)")
        else:
            ozet = "GEÇERSİZ imza"
        zaman = getattr(durum, "signer_reported_dt", None)
        sonuc.append(ImzaDurumu(gomulu.field_name, imzalayan, zaman, tamam, degisti, guvenilir, ozet, ayr))
    return sonuc
