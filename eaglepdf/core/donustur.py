"""Dönüştürme, sıkıştırma ve karşılaştırma (Qt'siz, saf Python).

Her işlev çıktı dosya(lar)ının yolunu döndürür, var olan dosyanın üzerine yazmaz (ad çakışırsa "ad (2)" verilir).
`ilerleme(tamamlanan, toplam)` verilirse çağrılır; `True` dönerse işlem `Iptal` ile durdurulur.
Sayfa numaraları 0 tabanlıdır; `sayfalar=None` tüm belge demektir. Her şey yerelde çalışır.
"""

import datetime
import html
import io
import logging
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pymupdf

from . import belge as belge_modulu
from . import ocr
from .belge import Belge, BelgeHatasi, aralik_coz

RESIM_BICIMLERI = {"png": "PNG", "jpg": "JPEG", "bmp": "BMP", "tiff": "TIFF"}
RENK_MODLARI = ("renkli", "gri", "siyahbeyaz")
SIKISTIRMA_SEVIYELERI = ("dusuk", "orta", "yuksek")
GIRDI_RESIM_UZANTILARI = (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tif", ".tiff", ".webp")
EN_COK_PIKSEL = 120_000_000  # tek sayfa/resim için bellek koruması
PUNTO_PT = 72.0


class Iptal(BelgeHatasi):
    """Kullanıcı işlemi iptal etti."""


def _ilerle(ilerleme, n: int, toplam: int):
    if ilerleme and ilerleme(n, toplam):
        raise Iptal("İşlem iptal edildi.")


def benzersiz_yol(klasor: Path, ad: str, uzanti: str) -> Path:
    klasor = Path(klasor)
    klasor.mkdir(parents=True, exist_ok=True)
    yol = klasor / f"{ad}{uzanti}"
    n = 2
    while yol.exists():
        yol = klasor / f"{ad} ({n}){uzanti}"
        n += 1
    return yol


def _ac(yol, parola=None) -> Belge:
    return Belge.ac(yol, parola)


def _sayfa_listesi(b: Belge, sayfalar) -> list[int]:
    if sayfalar is None:
        return list(range(b.sayfa_sayisi))
    liste = sorted(set(sayfalar))
    if not liste or liste[0] < 0 or liste[-1] >= b.sayfa_sayisi:
        raise BelgeHatasi("Sayfa seçimi belgenin dışında.")
    return liste


def _yaz_gecici(hedef: Path, yaz_fn):
    belge_modulu._gecici_yaz(yaz_fn, hedef)


# ---------------------------------------------------------------- PDF → resim
def _pillow():
    from PIL import Image
    return Image


def _renk_modu_uygula(pix: pymupdf.Pixmap, mod: str) -> pymupdf.Pixmap:
    if mod == "gri":
        return pix if pix.n == 1 else pymupdf.Pixmap(pymupdf.csGRAY, pix)
    if mod == "siyahbeyaz":
        gri = pix if pix.n == 1 else pymupdf.Pixmap(pymupdf.csGRAY, pix)
        a = np.frombuffer(gri.samples, dtype=np.uint8).reshape(gri.height, gri.stride)[:, :gri.width]
        ikili = np.where(a >= 128, 255, 0).astype(np.uint8)
        return pymupdf.Pixmap(pymupdf.csGRAY, gri.width, gri.height, ikili.tobytes(), False)
    return pix


def _pix_pil(pix: pymupdf.Pixmap):
    Image = _pillow()
    mod = "L" if pix.n == 1 else "RGB"
    return Image.frombytes(mod, (pix.width, pix.height), pix.samples if pix.stride == pix.width * pix.n
                           else b"".join(pix.samples[y * pix.stride:y * pix.stride + pix.width * pix.n] for y in range(pix.height)))


def pdf_resim(yol, klasor, bicim: str = "png", dpi: int = 150, renk: str = "renkli", sayfalar=None,
              tek_resim: bool = False, parola=None, kalite: int = 90, ilerleme=None) -> list[Path]:
    """Sayfaları resme çevirir. `tek_resim`: tüm sayfalar alt alta tek uzun resimde."""
    if bicim not in RESIM_BICIMLERI:
        raise BelgeHatasi(f"Desteklenmeyen resim biçimi: {bicim}")
    if renk not in RENK_MODLARI:
        raise BelgeHatasi(f"Bilinmeyen renk modu: {renk}")
    if not 36 <= dpi <= 600:
        raise BelgeHatasi("Çözünürlük 36–600 DPI arasında olmalı.")
    b = _ac(yol, parola)
    try:
        liste = _sayfa_listesi(b, sayfalar)
        olcek = dpi / PUNTO_PT
        for i in liste:
            g, y = b.sayfa_boyutu(i)
            if g * olcek * y * olcek > EN_COK_PIKSEL:
                raise BelgeHatasi(f"Sayfa {i + 1} bu çözünürlükte çok büyük; DPI'yı düşürün.")
        stem = Path(yol).stem
        uzanti = ".jpg" if bicim == "jpg" else f".{bicim}"
        kayit = dict(quality=kalite) if bicim == "jpg" else {}
        cikti: list[Path] = []
        parcalar = []
        for n, i in enumerate(liste):
            _ilerle(ilerleme, n, len(liste))
            pix = _renk_modu_uygula(b._doc[i].get_pixmap(matrix=pymupdf.Matrix(olcek, olcek), alpha=False,
                                                         colorspace=pymupdf.csGRAY if renk != "renkli" else pymupdf.csRGB), renk)
            img = _pix_pil(pix)
            if bicim == "jpg" and img.mode != "RGB":
                img = img.convert("RGB")
            if tek_resim:
                parcalar.append(img)
                continue
            hedef = benzersiz_yol(klasor, f"{stem}_sayfa_{i + 1:03d}", uzanti)
            _yaz_gecici(hedef, lambda g, img=img: img.save(g, RESIM_BICIMLERI[bicim], **kayit))
            cikti.append(hedef)
        if tek_resim:
            Image = _pillow()
            gen = max(p.width for p in parcalar)
            yuk = sum(p.height for p in parcalar)
            if gen * yuk > EN_COK_PIKSEL:
                raise BelgeHatasi("Tek resim çok büyük olurdu; DPI'yı düşürün ya da sayfaları ayrı kaydedin.")
            tuval = Image.new(parcalar[0].mode, (gen, yuk), 255 if parcalar[0].mode == "L" else (255, 255, 255))
            y = 0
            for p in parcalar:
                tuval.paste(p, ((gen - p.width) // 2, y))
                y += p.height
            hedef = benzersiz_yol(klasor, stem, uzanti)
            _yaz_gecici(hedef, lambda g: tuval.save(g, RESIM_BICIMLERI[bicim], **kayit))
            cikti.append(hedef)
        _ilerle(ilerleme, len(liste), len(liste))
        return cikti
    finally:
        b.kapat()


# ---------------------------------------------------------------- PDF → metin / HTML
def _metin_var_mi(b: Belge, liste: list[int]) -> bool:
    return any(b._doc[i].get_text().strip() for i in liste)


def _ocr_dene(b: Belge, liste: list[int], ilerleme=None) -> set[int]:
    """Metinsiz sayfalara (OCR kuruluysa) bellekteki kopyada OCR uygular; hata vermez. OCR ile metin bulunan sayfaları döndürür."""
    eksik = b.metinsiz_sayfalar(liste)
    if not eksik or not ocr.hazir_mi():
        return set()
    try:
        b.aranabilir_yap(eksik, ilerleme=ilerleme)
    except ocr.OcrIptal:
        raise Iptal("İşlem iptal edildi.") from None
    return {i for i in eksik if b._doc[i].get_text().strip()}


def _metni_hazirla(b: Belge, liste: list[int], ilerleme=None):
    """Seçili sayfalarda metin yoksa (taranmış) ve OCR dil verisi kuruluysa, bellekteki kopyaya OCR metni ekler
    (kaynak dosya değişmez). Hâlâ metin yoksa anlaşılır hata verir."""
    eksik = b.metinsiz_sayfalar(liste)
    if eksik and ocr.hazir_mi():
        try:
            b.aranabilir_yap(eksik, ilerleme=ilerleme)
        except ocr.OcrIptal:
            raise Iptal("İşlem iptal edildi.") from None
    if not _metin_var_mi(b, liste):
        if ocr.hazir_mi():
            raise BelgeHatasi("Belgede metin bulunamadı; sayfalar OCR ile de okunamadı (boş ya da çok bulanık olabilir).")
        raise BelgeHatasi("Belgede metin bulunamadı (taranmış sayfalar olabilir). OCR için Türkçe dil verisi kurulmalı: "
                          "Yardım → Nasıl Kullanılır → OCR.")


def pdf_metin(yol, klasor, sayfalar=None, sayfa_ayraci: bool = True, parola=None, ilerleme=None) -> Path:
    b = _ac(yol, parola)
    try:
        liste = _sayfa_listesi(b, sayfalar)
        _metni_hazirla(b, liste, ilerleme)
        parcalar = []
        for n, i in enumerate(liste):
            _ilerle(ilerleme, n, len(liste))
            metin = b._doc[i].get_text().replace("\xa0", " ").rstrip()
            parcalar.append((f"— Sayfa {i + 1} —\n\n" if sayfa_ayraci else "") + metin)
        hedef = benzersiz_yol(klasor, Path(yol).stem, ".txt")
        icerik = "\n\n".join(parcalar) + "\n"
        _yaz_gecici(hedef, lambda g: Path(g).write_text(icerik, encoding="utf-8-sig"))
        _ilerle(ilerleme, len(liste), len(liste))
        return hedef
    finally:
        b.kapat()


def _sayisal_varliklari_coz(metin: str) -> str:
    """PyMuPDF'in &#x15f; gibi yazdığı Unicode karakterleri gerçek karaktere çevirir (<, >, & dokunulmaz)."""
    def cevir(m):
        ch = chr(int(m.group(1), 16))
        return ch if ch not in "<>&" else m.group(0)
    return re.sub(r"&#x([0-9a-fA-F]+);", cevir, metin)


def pdf_html(yol, klasor, sayfalar=None, parola=None, ilerleme=None) -> Path:
    b = _ac(yol, parola)
    try:
        liste = _sayfa_listesi(b, sayfalar)
        _metni_hazirla(b, liste, ilerleme)
        govde = []
        for n, i in enumerate(liste):
            _ilerle(ilerleme, n, len(liste))
            govde.append(f'<section id="sayfa-{i + 1}" style="margin:0 0 24px 0;border-bottom:1px solid #ccc">'
                         f"{_sayisal_varliklari_coz(b._doc[i].get_text('html'))}</section>")
        baslik = html.escape(b._doc.metadata.get("title") or Path(yol).stem)
        belge_html = ('<!DOCTYPE html>\n<html lang="tr"><head><meta charset="utf-8">'
                      f"<title>{baslik}</title></head><body>\n" + "\n".join(govde) + "\n</body></html>\n")
        hedef = benzersiz_yol(klasor, Path(yol).stem, ".html")
        _yaz_gecici(hedef, lambda g: Path(g).write_text(belge_html, encoding="utf-8"))
        _ilerle(ilerleme, len(liste), len(liste))
        return hedef
    finally:
        b.kapat()


# ---------------------------------------------------------------- PDF → Word
def _ocr_word(b: Belge, liste: list[int], hedef: Path, ilerleme=None):
    """OCR ile okunmuş sayfalardan düz Word belgesi (pdf2docx görünmez metni görmez): sayfa başına paragraflar."""
    import docx
    d = docx.Document()
    for n, i in enumerate(liste):
        _ilerle(ilerleme, n, len(liste))
        if n:
            d.add_page_break()
        for blok in b._doc[i].get_text("blocks", sort=True):
            if blok[6] == 0 and blok[4].strip():  # 0 = metin bloğu
                d.add_paragraph(" ".join(blok[4].replace(" ", " ").split()))
    _yaz_gecici(hedef, lambda g: d.save(g))
    _ilerle(ilerleme, len(liste), len(liste))


def pdf_word(yol, klasor, sayfalar=None, parola=None, ilerleme=None) -> Path:
    """pdf2docx (MIT) ile: paragraflar, biçim, tablolar ve resimler korunmaya çalışılır.
    Taranmış sayfalarda OCR metni kullanılır (yalnızca paragraflar; sayfa düzeni korunmaz)."""
    from pdf2docx import Converter
    b = _ac(yol, parola)
    try:
        liste = _sayfa_listesi(b, sayfalar)
        _metni_hazirla(b, liste, ilerleme)
        if b.degisti:  # OCR eklendi
            hedef = benzersiz_yol(klasor, Path(yol).stem, ".docx")
            _ocr_word(b, liste, hedef, ilerleme)
            return hedef
    finally:
        b.kapat()
    hedef = benzersiz_yol(klasor, Path(yol).stem, ".docx")
    onceki = logging.root.manager.disable
    logging.disable(logging.INFO)  # pdf2docx her sayfa için bilgi satırı basar
    try:
        _ilerle(ilerleme, 0, 1)
        cv = Converter(str(yol), password=parola or "")
        try:
            _yaz_gecici(hedef, lambda g: cv.convert(g, pages=liste))
        finally:
            cv.close()
        _ilerle(ilerleme, 1, 1)
    finally:
        logging.disable(onceki)
    return hedef


# ---------------------------------------------------------------- PDF → Excel
_BIN_NOKTALI = re.compile(r"^-?\d{1,3}(\.\d{3})+(,\d+)?$")
_ONDALIK_VIRGUL = re.compile(r"^-?\d+,\d+$")
_TAMSAYI = re.compile(r"^-?\d+$")


def sayi_cozumle(metin: str):
    """“1.234,50” → 1234.5, “240,50” → 240.5, “12” → 12; sıfırla başlayan kodlar (007) ve diğerleri metin kalır."""
    m = metin.strip()
    if not m:
        return None
    if _BIN_NOKTALI.match(m):
        return float(m.replace(".", "").replace(",", "."))
    if _ONDALIK_VIRGUL.match(m) and not m.lstrip("-").startswith("00"):
        return float(m.replace(",", "."))
    if _TAMSAYI.match(m) and (len(m.lstrip("-")) == 1 or not m.lstrip("-").startswith("0")) and len(m) < 16:
        return int(m)
    return metin.strip()


def pdf_excel(yol, klasor, sayfalar=None, sayi_algila: bool = True, parola=None, ilerleme=None) -> tuple[Path, int]:
    """Sayfalardaki tabloları ayrı sayfalara (sheet) yazar → (dosya, tablo sayısı). Tablo yoksa satır satır metin yazar
    (tablo sayısı 0)."""
    import openpyxl
    from openpyxl.utils import get_column_letter
    b = _ac(yol, parola)
    try:
        liste = _sayfa_listesi(b, sayfalar)
        _metni_hazirla(b, liste, ilerleme)
        wb = openpyxl.Workbook()
        wb.remove(wb.active)
        tablo_sayisi = 0
        for n, i in enumerate(liste):
            _ilerle(ilerleme, n, len(liste))
            for k, tablo in enumerate(b._doc[i].find_tables().tables, 1):
                satirlar = tablo.extract()
                if not satirlar or not any(any((h or "").strip() for h in s) for s in satirlar):
                    continue
                ws = wb.create_sheet(f"S{i + 1}-T{k}"[:31])
                for r, satir in enumerate(satirlar, 1):
                    for c, hucre in enumerate(satir, 1):
                        metin = (hucre or "").replace("\n", " ").strip()
                        ws.cell(r, c, sayi_cozumle(metin) if sayi_algila else (metin or None))
                for c in range(1, max(len(s) for s in satirlar) + 1):
                    en_uzun = max((len(str(ws.cell(r, c).value or "")) for r in range(1, len(satirlar) + 1)), default=8)
                    ws.column_dimensions[get_column_letter(c)].width = min(max(en_uzun + 2, 8), 60)
                tablo_sayisi += 1
        if tablo_sayisi == 0:
            ws = wb.create_sheet("Metin")
            satir_no = 1
            for i in liste:
                for satir in b._doc[i].get_text().replace("\xa0", " ").splitlines():
                    if satir.strip():
                        ws.cell(satir_no, 1, satir.strip())
                        satir_no += 1
            ws.column_dimensions["A"].width = 100
        hedef = benzersiz_yol(klasor, Path(yol).stem, ".xlsx")
        _yaz_gecici(hedef, lambda g: wb.save(g))
        _ilerle(ilerleme, len(liste), len(liste))
        return hedef, tablo_sayisi
    finally:
        b.kapat()


# ---------------------------------------------------------------- PDF → PowerPoint
def _yazi_tipi_adi(ad: str) -> str:
    return re.sub(r"^[A-Z]{6}\+", "", ad).replace("-Bold", "").replace("-Italic", "").replace(",Bold", "").strip() or "Arial"


def pdf_pptx(yol, klasor, sayfalar=None, mod: str = "duzenlenebilir", dpi: int = 150, parola=None, ilerleme=None) -> Path:
    """Her sayfa bir slayt. mod='resim': sayfa görüntüsü; 'duzenlenebilir': metinsiz arka plan görüntüsü + düzenlenebilir
    metin kutuları (konumlar sayfayla birebir)."""
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.util import Emu, Pt
    if mod not in ("resim", "duzenlenebilir"):
        raise BelgeHatasi(f"Bilinmeyen biçim: {mod}")
    b = _ac(yol, parola)
    try:
        liste = _sayfa_listesi(b, sayfalar)
        ocr_sayfalari = _ocr_dene(b, liste, ilerleme)  # taranmış sayfalar: metin slayt notuna (kutu eklenmez: resimle çakışırdı)
        g0, y0 = b.sayfa_boyutu(liste[0])
        prs = Presentation()
        prs.slide_width, prs.slide_height = Emu(round(g0 * 12700)), Emu(round(y0 * 12700))
        bos = prs.slide_layouts[6]
        for n, i in enumerate(liste):
            _ilerle(ilerleme, n, len(liste))
            sayfa = b._doc[i]
            g, y = b.sayfa_boyutu(i)
            olcek = g0 / g  # farklı boyutlu sayfalar ilk sayfaya göre ölçeklenir
            slayt = prs.slides.add_slide(bos)
            if mod == "resim":
                png = sayfa.get_pixmap(matrix=pymupdf.Matrix(dpi / PUNTO_PT, dpi / PUNTO_PT), alpha=False).tobytes("png")
            else:
                gecici = pymupdf.open()
                try:
                    gecici.insert_pdf(b._doc, from_page=i, to_page=i)
                    gs = gecici[0]
                    gs.add_redact_annot(gs.rect, fill=False)
                    gs.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_NONE, graphics=pymupdf.PDF_REDACT_LINE_ART_NONE)
                    png = gs.get_pixmap(matrix=pymupdf.Matrix(dpi / PUNTO_PT, dpi / PUNTO_PT), alpha=False).tobytes("png")
                finally:
                    gecici.close()
            slayt.shapes.add_picture(io.BytesIO(png), 0, 0, width=prs.slide_width, height=round(y * olcek * 12700))
            metin_blogu = []
            for blok in sayfa.get_text("dict")["blocks"]:
                if blok.get("type") != 0:
                    continue
                satirlar = [("".join(s["text"] for s in sa["spans"]).replace("\xa0", " "), sa["spans"]) for sa in blok["lines"]]
                metin_blogu.append("\n".join(t for t, _ in satirlar))
                if mod != "duzenlenebilir" or i in ocr_sayfalari:
                    continue
                x0, yy0, x1, yy1 = (v * olcek for v in blok["bbox"])
                kutu = slayt.shapes.add_textbox(Emu(round(x0 * 12700)), Emu(round(yy0 * 12700)),
                                                Emu(round((x1 - x0 + 4) * 12700)), Emu(round((yy1 - yy0) * 12700)))
                tf = kutu.text_frame
                tf.word_wrap = False
                tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
                for k, (_t, spanlar) in enumerate(satirlar):
                    par = tf.paragraphs[0] if k == 0 else tf.add_paragraph()
                    for sp in spanlar:
                        if not sp["text"]:
                            continue
                        r = par.add_run()
                        r.text = sp["text"].replace("\xa0", " ")
                        r.font.size = Pt(max(sp["size"] * olcek, 1))
                        r.font.name = _yazi_tipi_adi(sp["font"])
                        r.font.bold = bool(sp["flags"] & 16) or "bold" in sp["font"].lower()
                        r.font.italic = bool(sp["flags"] & 2) or "italic" in sp["font"].lower()
                        r.font.color.rgb = RGBColor((sp["color"] >> 16) & 255, (sp["color"] >> 8) & 255, sp["color"] & 255)
            if metin_blogu:
                slayt.notes_slide.notes_text_frame.text = "\n\n".join(metin_blogu)
        hedef = benzersiz_yol(klasor, Path(yol).stem, ".pptx")
        _yaz_gecici(hedef, lambda gy: prs.save(gy))
        _ilerle(ilerleme, len(liste), len(liste))
        return hedef
    finally:
        b.kapat()


# ---------------------------------------------------------------- → PDF
def _okuma_kodlamasi(veri: bytes) -> str:
    """UTF-8 (BOM'lu/BOM'suz), olmazsa Windows-1254 (Türkçe) ile çözer."""
    for kod in ("utf-8-sig", "cp1254", "latin-1"):
        try:
            return veri.decode(kod)
        except UnicodeDecodeError:
            continue
    return veri.decode("latin-1", errors="replace")


TABLO_CSS = ("body { font-size: 11pt; } table { border-collapse: collapse; margin: 6pt 0; } "
             "td, th { border: 0.5pt solid #555555; padding: 2pt 4pt; font-size: 9.5pt; } "
             "th { background-color: #eeeeee; } img { max-width: 100%; } pre { font-size: 9.5pt; }")


def html_den_pdf(html_metni: str, hedef: Path, arsiv=None, yatay: bool = False, kenar: float = 54, css: str = TABLO_CSS):
    """HTML'i A4 sayfalara dizip PDF yazar (PyMuPDF Story; Türkçe harfler dahil)."""
    story = pymupdf.Story(html=html_metni, user_css=css, archive=arsiv)
    kutu = pymupdf.paper_rect("a4-l" if yatay else "a4")
    alan = kutu + (kenar, kenar, -kenar, -kenar)

    def yaz(g):
        tampon = io.BytesIO()  # dosyaya yazdırmak Windows'ta kilit bırakıyor; belleğe yazıp kendimiz kaydediyoruz
        yazar = pymupdf.DocumentWriter(tampon)
        daha = 1
        while daha:
            dev = yazar.begin_page(kutu)
            daha, _ = story.place(alan)
            story.draw(dev)
            yazar.end_page()
        yazar.close()
        Path(g).write_bytes(tampon.getvalue())

    _yaz_gecici(Path(hedef), yaz)


def metinden_pdf(yol, klasor, ilerleme=None) -> Path:
    veri = Path(yol).read_bytes()
    if not veri.strip():
        raise BelgeHatasi("Dosya boş.")
    satirlar = html.escape(_okuma_kodlamasi(veri)).replace("\t", "    ").splitlines()
    govde = "<br>".join(s.replace("  ", "&nbsp; ") for s in satirlar)
    hedef = benzersiz_yol(klasor, Path(yol).stem, ".pdf")
    _ilerle(ilerleme, 0, 1)
    html_den_pdf(f"<body>{govde}</body>", hedef)
    _ilerle(ilerleme, 1, 1)
    return hedef


def html_dosyasindan_pdf(yol, klasor, ilerleme=None) -> Path:
    yol = Path(yol)
    metin = _okuma_kodlamasi(yol.read_bytes())
    hedef = benzersiz_yol(klasor, yol.stem, ".pdf")
    _ilerle(ilerleme, 0, 1)
    html_den_pdf(metin, hedef, arsiv=pymupdf.Archive(str(yol.parent)))  # göreli resimler yanındaki klasörden alınır
    _ilerle(ilerleme, 1, 1)
    return hedef


def word_den_pdf(yol, klasor, ilerleme=None) -> Path:
    """Word (.docx) → PDF: mammoth ile HTML'e, oradan PDF'e. Başlık, paragraf, liste, tablo, resim ve temel biçim
    korunur; sayfa düzeni (üst/alt bilgi, sütun, metin kutusu) korunmaz."""
    import mammoth
    arsiv = pymupdf.Archive()
    sayac = [0]

    def resim_isle(image):
        with image.open() as f:
            veri = f.read()
        uzanti = (image.content_type.split("/")[-1] or "png").replace("jpeg", "jpg")
        if uzanti not in ("png", "jpg", "gif", "bmp"):
            return {"src": ""}  # EMF/WMF gibi biçimler Story'de çizilemez
        sayac[0] += 1
        ad = f"resim{sayac[0]}.{uzanti}"
        arsiv.add(veri, ad)
        return {"src": ad}

    _ilerle(ilerleme, 0, 1)
    try:
        with open(yol, "rb") as f:
            sonuc = mammoth.convert_to_html(f, convert_image=mammoth.images.img_element(resim_isle))
    except Exception as h:
        raise BelgeHatasi(f"Word belgesi okunamadı: {h}") from None
    if not re.sub(r"<[^>]+>", "", sonuc.value).strip() and "<img" not in sonuc.value:
        raise BelgeHatasi("Belgede çevrilecek içerik bulunamadı.")
    hedef = benzersiz_yol(klasor, Path(yol).stem, ".pdf")
    html_den_pdf(f"<body>{sonuc.value}</body>", hedef, arsiv=arsiv)
    _ilerle(ilerleme, 1, 1)
    return hedef


def _hucre_metni(v) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "Evet" if v else "Hayır"
    if isinstance(v, (datetime.datetime, datetime.date)):
        return v.strftime("%d.%m.%Y %H:%M" if isinstance(v, datetime.datetime) and (v.hour or v.minute) else "%d.%m.%Y")
    if isinstance(v, float):
        return f"{v:,.6f}".rstrip("0").rstrip(".").replace(",", "X").replace(".", ",").replace("X", ".")
    if isinstance(v, int):
        return f"{v:,}".replace(",", ".") if abs(v) >= 10000 else str(v)
    return str(v)


def excel_den_pdf(yol, klasor, ilerleme=None) -> Path:
    """Excel (.xlsx) → PDF: her sayfa (sheet) bir tablo olarak; formüller son hesaplanan değerleriyle yazılır."""
    import openpyxl
    try:
        wb = openpyxl.load_workbook(str(yol), data_only=True, read_only=True)
    except Exception as h:
        raise BelgeHatasi(f"Excel dosyası okunamadı: {h}") from None
    parcalar, en_cok_sutun = [], 0
    try:
        for ws in wb.worksheets:
            satirlar = [[_hucre_metni(h) for h in satir] for satir in ws.iter_rows(values_only=True)]
            while satirlar and not any(satirlar[-1]):
                satirlar.pop()
            if not satirlar:
                continue
            sutun = max(len(s) for s in satirlar)
            while sutun and not any(len(s) >= sutun and s[sutun - 1] for s in satirlar):
                sutun -= 1
            if not sutun:
                continue
            en_cok_sutun = max(en_cok_sutun, sutun)
            govde = "".join("<tr>" + "".join(f"<td>{html.escape(s[c]) if c < len(s) else ''}</td>" for c in range(sutun)) + "</tr>"
                            for s in satirlar)
            parcalar.append(f"<h3>{html.escape(ws.title)}</h3><table>{govde}</table>")
    finally:
        wb.close()
    if not parcalar:
        raise BelgeHatasi("Çalışma kitabında çevrilecek veri bulunamadı.")
    hedef = benzersiz_yol(klasor, Path(yol).stem, ".pdf")
    _ilerle(ilerleme, 0, 1)
    html_den_pdf("<body>" + "".join(parcalar) + "</body>", hedef, yatay=en_cok_sutun > 6,
                 css=TABLO_CSS + (" td { font-size: 8pt; }" if en_cok_sutun > 12 else ""))
    _ilerle(ilerleme, 1, 1)
    return hedef


def _resmi_hazirla(yol: Path):
    """Resmi PDF'e gömülecek biçimde (bayt, uzantı, genişlik_px, yükseklik_px) hazırlar: EXIF yönü uygulanır,
    saydamlık beyaza düzleştirilir; uygun JPEG'ler olduğu gibi (kayıpsız) gömülür."""
    Image = _pillow()
    from PIL import ImageOps
    try:
        with Image.open(yol) as im:
            ham_jpeg = im.format == "JPEG" and (im.getexif().get(274, 1) in (0, 1)) and im.mode in ("RGB", "L")
            im.load()
            dondurulmus = ImageOps.exif_transpose(im)
            if ham_jpeg:
                return yol.read_bytes(), "jpg", im.width, im.height
            if dondurulmus.mode in ("RGBA", "LA", "P"):
                dondurulmus = dondurulmus.convert("RGBA")
                zemin = Image.new("RGB", dondurulmus.size, (255, 255, 255))
                zemin.paste(dondurulmus, mask=dondurulmus.split()[3])
                dondurulmus = zemin
            elif dondurulmus.mode not in ("RGB", "L"):
                dondurulmus = dondurulmus.convert("RGB")
            tampon = io.BytesIO()
            dondurulmus.save(tampon, "PNG")
            return tampon.getvalue(), "png", dondurulmus.width, dondurulmus.height
    except OSError as h:
        raise BelgeHatasi(f"Resim açılamadı ({yol.name}): {h}") from None


def resimlerden_pdf(yollar: list, klasor, ad: str | None = None, sayfa_boyutu: str = "A4", yon: str = "otomatik",
                    kenar: float = 0.0, ayri_dosyalar: bool = False, ilerleme=None) -> list[Path]:
    """Resimleri PDF'e çevirir. sayfa_boyutu: A3/A4/A5/Letter/Legal ya da 'resim' (sayfa = resim boyutu).
    yon: otomatik / dikey / yatay. kenar: sayfa kenar boşluğu (pt). ayri_dosyalar: her resim ayrı PDF."""
    if not yollar:
        raise BelgeHatasi("Resim seçilmedi.")
    if sayfa_boyutu != "resim" and sayfa_boyutu not in belge_modulu.SAYFA_BOYUTLARI:
        raise BelgeHatasi(f"Bilinmeyen sayfa boyutu: {sayfa_boyutu}")
    if yon not in ("otomatik", "dikey", "yatay"):
        raise BelgeHatasi(f"Bilinmeyen yön: {yon}")
    yollar = [Path(y) for y in yollar]
    cikti: list[Path] = []
    belge = None
    try:
        for n, yol in enumerate(yollar):
            _ilerle(ilerleme, n, len(yollar))
            veri, uzanti, gp, yp = _resmi_hazirla(yol)
            if belge is None or ayri_dosyalar:
                belge = pymupdf.open()
            if sayfa_boyutu == "resim":
                sg, sy = gp * 0.75, yp * 0.75  # 96 dpi varsayımı
            else:
                sg, sy = belge_modulu.SAYFA_BOYUTLARI[sayfa_boyutu]
                yatay = (gp > yp) if yon == "otomatik" else yon == "yatay"
                if yatay != (sg > sy):
                    sg, sy = sy, sg
            sayfa = belge.new_page(width=sg, height=sy)
            alan = pymupdf.Rect(kenar, kenar, sg - kenar, sy - kenar)
            if alan.is_empty:
                raise BelgeHatasi("Kenar boşluğu sayfadan büyük.")
            sayfa.insert_image(alan, stream=veri, keep_proportion=True)
            if ayri_dosyalar or n == len(yollar) - 1:
                hedef = benzersiz_yol(klasor, yol.stem if ayri_dosyalar else (ad or (yol.stem if len(yollar) == 1 else "Resimler")), ".pdf")
                _yaz_gecici(hedef, lambda g, bl=belge: bl.save(g, garbage=3, deflate=True))
                cikti.append(hedef)
                belge.close()
                belge = None
        _ilerle(ilerleme, len(yollar), len(yollar))
        return cikti
    finally:
        if belge is not None:
            belge.close()


# ---------------------------------------------------------------- sıkıştırma
@dataclass
class SikistirmaSonucu:
    eski_boyut: int
    yeni_boyut: int
    kucultuldu: bool   # False: dosya zaten en küçük hâlindeydi, özgün kopyalandı

    @property
    def kazanc_orani(self) -> float:
        return 1 - self.yeni_boyut / self.eski_boyut if self.eski_boyut else 0.0


def sikistir(yol, klasor, seviye: str = "orta", parola=None, ilerleme=None) -> tuple[Path, SikistirmaSonucu]:
    """dusuk: yalnızca gereksiz nesneleri atar/akışları sıkıştırır (kayıpsız). orta: >170 dpi resimleri 130 dpi/JPEG %75'e
    indirir. yuksek: >110 dpi resimleri 80 dpi/JPEG %50'ye indirir. Sonuç özgünden büyük çıkarsa özgün kopyalanır."""
    if seviye not in SIKISTIRMA_SEVIYELERI:
        raise BelgeHatasi(f"Bilinmeyen sıkıştırma düzeyi: {seviye}")
    yol = Path(yol)
    eski = yol.stat().st_size
    b = _ac(yol, parola)
    hedef = benzersiz_yol(klasor, f"{yol.stem}_sikistirilmis", ".pdf")
    try:
        _ilerle(ilerleme, 0, 3)
        doc = b._doc
        if seviye != "dusuk":
            esik, hedef_dpi, kalite = (170, 130, 75) if seviye == "orta" else (110, 80, 50)
            try:
                doc.rewrite_images(dpi_threshold=esik, dpi_target=hedef_dpi, quality=kalite)
            except Exception:
                pass  # resim yeniden yazılamazsa yalnızca yapısal sıkıştırma yapılır
        _ilerle(ilerleme, 1, 3)
        try:
            doc.subset_fonts()
        except Exception:
            pass
        _ilerle(ilerleme, 2, 3)
        _yaz_gecici(hedef, lambda g: doc.save(g, garbage=4, deflate=True, deflate_images=True, deflate_fonts=True, clean=True))
    finally:
        b.kapat()
    yeni = hedef.stat().st_size
    kucultuldu = yeni < eski
    if not kucultuldu:
        shutil.copyfile(yol, hedef)  # daha büyük çıkan sonucu verme: özgün kalsın
        yeni = hedef.stat().st_size
    _ilerle(ilerleme, 3, 3)
    return hedef, SikistirmaSonucu(eski, yeni, kucultuldu)


# ---------------------------------------------------------------- karşılaştırma
@dataclass
class SayfaFarki:
    sayfa: int                      # 0 tabanlı
    yalniz: str | None              # "a" ya da "b": sayfa yalnızca birinde var
    eklenen: list[str]              # B'de olup A'da olmayan kelime grupları
    silinen: list[str]              # A'da olup B'de olmayan kelime grupları
    piksel_orani: float             # değişen piksellerin oranı (0–1)
    fark_png: bytes | None          # değişen yerler kırmızı işaretli görüntü

    @property
    def farkli(self) -> bool:
        return bool(self.yalniz or self.eklenen or self.silinen or self.piksel_orani > 0.0005)


def _gri_matris(b: Belge, i: int, genislik_pt: float, yukseklik_pt: float, olcek: float):
    """Sayfayı verilen boyuta ölçekleyip (taşan/boş yerler beyaz) gri numpy dizisi olarak verir."""
    g, y = b.sayfa_boyutu(i)
    k = min(genislik_pt / g, yukseklik_pt / y) * olcek
    pix = b._doc[i].get_pixmap(matrix=pymupdf.Matrix(k, k), colorspace=pymupdf.csGRAY, alpha=False)
    a = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.stride)[:, :pix.width]
    tuval = np.full((round(yukseklik_pt * olcek), round(genislik_pt * olcek)), 255, dtype=np.uint8)
    h, w = min(tuval.shape[0], a.shape[0]), min(tuval.shape[1], a.shape[1])
    tuval[:h, :w] = a[:h, :w]
    return tuval


def _kelime_farki(a: list[str], b: list[str]) -> tuple[list[str], list[str]]:
    import difflib
    eklenen, silinen = [], []
    for islem, a1, a2, b1, b2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if islem in ("replace", "delete"):
            silinen.append(" ".join(a[a1:a2]))
        if islem in ("replace", "insert"):
            eklenen.append(" ".join(b[b1:b2]))
    return eklenen, silinen


def karsilastir(yol_a, yol_b, dpi: int = 72, parola_a=None, parola_b=None, ilerleme=None) -> list[SayfaFarki]:
    """İki PDF'i sayfa sayfa karşılaştırır: kelime farkları ve (değişen yerleri kırmızı gösteren) görsel fark."""
    a, b = _ac(yol_a, parola_a), _ac(yol_b, parola_b)
    try:
        toplam = max(a.sayfa_sayisi, b.sayfa_sayisi)
        olcek = dpi / PUNTO_PT
        sonuc = []
        for i in range(toplam):
            _ilerle(ilerleme, i, toplam)
            if i >= a.sayfa_sayisi or i >= b.sayfa_sayisi:
                sonuc.append(SayfaFarki(i, "a" if i >= b.sayfa_sayisi else "b", [], [], 1.0, None))
                continue
            kelimeler_a = a._doc[i].get_text().split()
            kelimeler_b = b._doc[i].get_text().split()
            eklenen, silinen = _kelime_farki(kelimeler_a, kelimeler_b)
            ga, ya = a.sayfa_boyutu(i)
            gb, yb = b.sayfa_boyutu(i)
            gen, yuk = max(ga, gb), max(ya, yb)
            ma, mb = _gri_matris(a, i, gen, yuk, olcek), _gri_matris(b, i, gen, yuk, olcek)
            degisen = np.abs(ma.astype(np.int16) - mb.astype(np.int16)) > 48
            oran = float(degisen.mean())
            png = None
            if oran > 0:
                zemin = (255 - (255 - ma) // 3).astype(np.uint8)  # A sayfasının soluk hâli
                rgb = np.stack([zemin, zemin, zemin], axis=-1)
                rgb[degisen] = (230, 30, 30)
                png = pymupdf.Pixmap(pymupdf.csRGB, rgb.shape[1], rgb.shape[0], rgb.tobytes(), False).tobytes("png")
            sonuc.append(SayfaFarki(i, None, eklenen, silinen, oran, png))
        _ilerle(ilerleme, toplam, toplam)
        return sonuc
    finally:
        a.kapat()
        b.kapat()
