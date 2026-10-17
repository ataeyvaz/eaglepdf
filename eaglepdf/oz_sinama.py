"""Kendini sınama: paketlenmiş (PyInstaller) ya da geliştirme ortamında kritik yolların gerçekten çalıştığını doğrular.

Neden: paketlemede eksik kalan DLL, veri dosyası, gizli içe aktarma ya da Qt eklentisi ancak çalışırken ortaya çıkar.
Çalıştırma: `python main.py --oz-sinama[=rapor.txt]` ya da `EaglePDF.exe --oz-sinama=rapor.txt`.
Çıkış kodu 0: hepsi geçti (atlananlar sayılmaz); 1: en az biri başarısız. Rapor dosyaya yazılır (pencereli exe'de konsol yoktur).
Kullanıcı verisine dokunmaz: her şey geçici klasörde yapılır; ağa çıkmaz.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import traceback
from dataclasses import dataclass
from pathlib import Path

ATLANDI = "ATLANDI"


@dataclass
class Sonuc:
    ad: str
    durum: str   # "TAMAM" | "HATA" | ATLANDI
    ayrinti: str = ""

    @property
    def basarisiz(self) -> bool:
        return self.durum == "HATA"


def _turkce_pdf(klasor: Path, sayfa: int = 2) -> Path:
    """Gömülü Noto Sans ile Türkçe metinli bir PDF yazar (yazı tipi verisinin pakette olduğunu da sınar)."""
    from .core import yazitipi
    from .core.belge import Belge
    b = Belge.yeni(sayfa)
    try:
        for i in range(sayfa):
            s = b._doc[i]
            s.insert_font(fontname="noto", fontbuffer=yazitipi.tampon())
            s.insert_text((72, 100), f"Işık İstanbul şğüöç sayfa {i + 1}", fontsize=20, fontname="noto")
        yol = klasor / "ornek.pdf"
        b.kaydet(yol)
        return yol
    finally:
        b.kapat()


# --- tek tek kontroller: her biri (ayrıntı) döndürür ya da istisna fırlatır; Atla ile atlanır ---
class Atla(Exception):
    pass


def _yardim_ve_logo(t: Path):
    from . import APP_NAME, resource_dir
    from .ui.yardim import konulari_yukle
    konular = konulari_yukle()
    assert len(konular) >= 10 and all(k.govde.strip() for k in konular), "yardım konuları eksik"
    assert "{APP_NAME}" not in "".join(k.govde for k in konular)
    logo = resource_dir() / "eagle-office-logo.png"
    assert logo.is_file(), f"logo bulunamadı: {logo}"
    return f"{len(konular)} yardım konusu, logo var ({APP_NAME})"


def _simgeler_ve_tema(t: Path):
    from .ui import simgeler
    adlar = simgeler.simge_adlari()
    for ad in adlar:
        assert not simgeler.simge(ad).isNull(), f"simge çizilemedi: {ad}"   # QtSvg eklentisi
    return f"{len(adlar)} simge"


def _yazi_tipi(t: Path):
    from .core import yazitipi
    assert len(yazitipi.tampon()) > 50_000, "Noto Sans verisi pakette yok/küçük"
    return f"Noto Sans {len(yazitipi.tampon()) // 1024} KB"


def _pdf_kayit_arama(t: Path):
    from .core.belge import Belge
    yol = _turkce_pdf(t)
    b = Belge.ac(yol)
    try:
        assert b.sayfa_sayisi == 2 and b.ara("istanbul"), "Türkçe arama sonuç vermedi"
        px = b.render(0, 1.0)
        assert px.width > 100
    finally:
        b.kapat()
    return "oluştur → kaydet → aç → Türkçe ara → render"


def _donusumler(t: Path):
    import docx
    from .core import donustur
    yol = _turkce_pdf(t)
    cikti = t / "cikti"
    sonuclar = []
    word = donustur.pdf_word(yol, cikti)
    assert "stanbul" in "\n".join(p.text for p in docx.Document(str(word)).paragraphs)
    sonuclar.append("pdf→word")
    donustur.pdf_excel(yol, cikti)
    sonuclar.append("pdf→excel")
    donustur.pdf_pptx(yol, cikti)
    sonuclar.append("pdf→pptx")
    assert "stanbul" in donustur.pdf_metin(yol, cikti).read_text(encoding="utf-8-sig")
    assert "stanbul" in donustur.pdf_html(yol, cikti).read_text(encoding="utf-8")
    sonuclar.append("pdf→metin/html")
    geri = donustur.word_den_pdf(word, cikti)   # mammoth + PyMuPDF Story
    assert geri.is_file()
    sonuclar.append("word→pdf")
    sik, _ = donustur.sikistir(yol, cikti)
    assert sik.is_file()
    farklar = donustur.karsilastir(yol, yol)   # numpy
    assert farklar is not None
    sonuclar.append("sıkıştır/karşılaştır")
    return ", ".join(sonuclar)


def _koruma(t: Path):
    from .core import koruma
    from .core.belge import Belge
    yol = _turkce_pdf(t)
    b = Belge.ac(yol)
    try:
        hedef = koruma.parola_ekle(b, t / "kor.pdf", acma_parolasi="pw")
    finally:
        b.kapat()
    k = Belge.ac(hedef, "pw")
    try:
        assert k.parola_korunur and k.sayfa_sayisi == 2
    finally:
        k.kapat()
    return "AES-256 parola ekle/aç"


def _dijital_imza(t: Path):
    from .core import dijital_imza as di
    from .core.belge import Belge
    yol = _turkce_pdf(t)
    pfx = di.sertifika_olustur(t / "s.pfx", "Sınama Kişisi", "parola")
    b = Belge.ac(yol)
    try:
        imzali = di.imzala(b, t / "imzali.pdf", pfx, "parola", konum="sag_alt")   # görünür kutu: uharfbuzz + fontTools
    finally:
        b.kapat()
    d = di.dogrula(imzali)
    assert len(d) == 1 and d[0].butunluk_tamam and d[0].imzalayan == "Sınama Kişisi", f"imza doğrulanamadı: {d}"
    return "sertifika üret → görünür imzala → doğrula (pyHanko, cryptography)"


def _xmp(t: Path):
    from .core import xmp
    ornek = ('<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
             '<rdf:Description xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title><rdf:Alt><rdf:li>Eski</rdf:li></rdf:Alt>'
             '</dc:title></rdf:Description></rdf:RDF></x:xmpmeta>')
    yeni, adet = xmp.guncelle(ornek, {"baslik": "Yeni"})
    assert adet == 1 and "Yeni" in yeni and "Eski" not in yeni
    return "lxml XMP güncelleme"


def _ocr(t: Path):
    from .core import ocr
    from .core.belge import Belge
    if not ocr.hazir_mi("eng"):
        raise Atla("İngilizce dil verisi kurulu değil (OCR → Dil Verisi…)")
    import pymupdf
    kaynak = pymupdf.open()
    s = kaynak.new_page()
    s.insert_text((72, 120), "Hello World report", fontsize=28, fontname="helv")
    resim = pymupdf.open()
    sayfa = resim.new_page(width=s.rect.width, height=s.rect.height)
    sayfa.insert_image(sayfa.rect, pixmap=s.get_pixmap(dpi=200))
    yol = t / "tarama.pdf"
    resim.save(yol)
    b = Belge.ac(yol)
    try:
        b.aranabilir_yap(dil="eng")
        metin = b._doc[0].get_text()
        assert "Hello" in metin, f"OCR metni bulunamadı: {metin!r}"
    finally:
        b.kapat()
    return "taranmış sayfa → aranabilir (Tesseract)"


def _yazdirma(t: Path):
    from PySide6.QtPrintSupport import QPrinter
    from .core.belge import Belge
    from .ui.yazdir import sayfalari_yazdir
    yol = _turkce_pdf(t)
    b = Belge.ac(yol)
    try:
        yazici = QPrinter(QPrinter.HighResolution)
        yazici.setOutputFormat(QPrinter.PdfFormat)
        cikti = t / "yazdirilan.pdf"
        yazici.setOutputFileName(str(cikti))
        assert sayfalari_yazdir(b, yazici, [0, 1]) == 2
    finally:
        b.kapat()
    assert cikti.is_file() and cikti.stat().st_size > 1000
    return "QtPrintSupport: PDF'e yazdır"


def _tek_ornek_soket(t: Path):
    import uuid
    from .ui.tek_ornek import TekOrnekSunucu
    s = TekOrnekSunucu(f"EaglePDF-sinama-{uuid.uuid4().hex}")   # QtNetwork + QLockFile
    try:
        assert s.baslat() and s.calisiyor
        ikinci = TekOrnekSunucu(s.ad)
        assert ikinci.baslat() is False, "ikinci sunucu kilidi alabildi"
    finally:
        s.durdur()
    return "QLocalServer + QLockFile"


def _iliskilendirme_komutu(t: Path):
    from .core import iliskilendirme
    komut = iliskilendirme.baslatici_komutu()
    assert komut.endswith(' "%1"'), komut
    if getattr(sys, "frozen", False):
        assert komut == f'"{sys.executable}" "%1"', f"paketlenmiş uygulamada komut kendi exe'sini göstermeli: {komut}"
    else:
        assert "main.py" in komut, komut
    return komut


def _ayarlar_ve_oturum(t: Path):
    from .ui.pencere import ayarlari_ac
    a = ayarlari_ac(str(t / "a.ini"))
    a.setValue("sinama", "ok")
    a.sync()
    assert ayarlari_ac(str(t / "a.ini")).value("sinama") == "ok"
    return "QSettings INI"


def _comtypes(t: Path):
    if sys.platform != "win32":
        raise Atla("yalnızca Windows")
    import comtypes.client  # noqa: F401  (tarayıcı: WIA)
    from .core import tarayici  # noqa: F401
    return "comtypes + tarayıcı modülü içe aktarıldı"


def _ana_pencere(t: Path):
    from .ui.pencere import AnaPencere
    p = AnaPencere(str(t / "pencere.ini"))
    try:
        yol = _turkce_pdf(t)
        p.ac(str(yol))
        assert p.belge is not None and p.sekmeler.count() == 1
        p.grab()   # gerçekten boyanır (Qt platform eklentisi + tema)
        p.belge.degisti = False
    finally:
        p.close()
    return "ana pencere açıldı, belge sekmede, boyandı"


KONTROLLER = (
    ("Yardım ve logo (veri dosyaları)", _yardim_ve_logo),
    ("Simgeler (QtSvg) ve tema", _simgeler_ve_tema),
    ("Yazı tipi verisi (pymupdf-fonts)", _yazi_tipi),
    ("PDF oluştur/kaydet/aç/ara/render (PyMuPDF)", _pdf_kayit_arama),
    ("Dönüştürmeler (pdf2docx, python-docx, openpyxl, python-pptx, mammoth, numpy)", _donusumler),
    ("Parola koruma (AES-256)", _koruma),
    ("Dijital imza (pyHanko, cryptography, uharfbuzz)", _dijital_imza),
    ("XMP (lxml)", _xmp),
    ("OCR (Tesseract, dil verisi varsa)", _ocr),
    ("Yazdırma (QtPrintSupport)", _yazdirma),
    ("Tek örnek (QtNetwork, QLockFile)", _tek_ornek_soket),
    ("Birlikte aç komutu", _iliskilendirme_komutu),
    ("Ayarlar (QSettings)", _ayarlar_ve_oturum),
    ("Tarayıcı modülü (comtypes)", _comtypes),
    ("Ana pencere", _ana_pencere),
)


def calistir(kontroller=KONTROLLER) -> list[Sonuc]:
    """Tüm kontrolleri geçici klasörde çalıştırır. QApplication hazır olmalıdır."""
    sonuclar: list[Sonuc] = []
    kok = Path(tempfile.mkdtemp(prefix="eaglepdf_sinama_"))
    try:
        for n, (ad, fn) in enumerate(kontroller):
            klasor = kok / f"k{n}"
            klasor.mkdir()
            try:
                sonuclar.append(Sonuc(ad, "TAMAM", str(fn(klasor) or "")))
            except Atla as a:
                sonuclar.append(Sonuc(ad, ATLANDI, str(a)))
            except BaseException as h:   # paketleme hatası her türden olabilir (ImportError, OSError, assert…)
                if isinstance(h, (KeyboardInterrupt, SystemExit)):
                    raise
                izleme = traceback.format_exc().strip().splitlines()
                sonuclar.append(Sonuc(ad, "HATA", f"{type(h).__name__}: {h}\n    " + "\n    ".join(izleme[-6:])))
    finally:
        shutil.rmtree(kok, ignore_errors=True)
    return sonuclar


def rapor_metni(sonuclar: list[Sonuc]) -> str:
    from . import APP_NAME, __version__
    satirlar = [f"{APP_NAME} {__version__} kendini sınama — Python {sys.version.split()[0]}"
                f"{' (paketlenmiş)' if getattr(sys, 'frozen', False) else ''}", ""]
    for s in sonuclar:
        satirlar.append(f"[{s.durum:7}] {s.ad}" + (f" — {s.ayrinti}" if s.ayrinti else ""))
    hata = sum(s.basarisiz for s in sonuclar)
    atlanan = sum(s.durum == ATLANDI for s in sonuclar)
    satirlar += ["", f"SONUÇ: {len(sonuclar) - hata - atlanan} tamam, {atlanan} atlandı, {hata} hata"]
    return "\n".join(satirlar) + "\n"


def komut_satirindan(argv: list[str]) -> int | None:
    """`--oz-sinama[=rapor.txt]` verildiyse sınamayı çalıştırıp çıkış kodunu döndürür; verilmediyse None."""
    secenek = next((a for a in argv[1:] if a == "--oz-sinama" or a.startswith("--oz-sinama=")), None)
    if secenek is None:
        return None
    rapor = Path(secenek.partition("=")[2] or (Path(tempfile.gettempdir()) / "eaglepdf_oz_sinama_raporu.txt"))
    from PySide6.QtWidgets import QApplication
    from .ui import theme
    app = QApplication.instance() or QApplication(argv)
    theme.apply(app)
    sonuclar = calistir()
    metin = rapor_metni(sonuclar)
    try:
        rapor.parent.mkdir(parents=True, exist_ok=True)
        rapor.write_text(metin, encoding="utf-8")
    except OSError:
        pass
    if sys.stdout is not None:   # pencereli (konsolsuz) exe'de stdout None
        try:
            print(metin)
        except (OSError, UnicodeEncodeError):
            pass
    return 1 if any(s.basarisiz for s in sonuclar) else 0
