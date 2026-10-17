"""Ana pencerenin Faz 4 bölümü: Dönüştür menüsü (PDF'den/PDF'e, sıkıştır, karşılaştır, tarayıcıdan PDF).

`AnaPencere`ye karışım olarak eklenir; `belge`, `ayarlar`, `m_sayfa`, `_eylem`, `ac`, `farkli_kaydet` üyelerini kullanır.
"""

import shutil
import tempfile
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFileDialog, QInputDialog, QMenu, QMessageBox

from .. import APP_NAME
from ..core import donustur, tarayici
from ..core.belge import BelgeHatasi
from . import simgeler
from .donusum_penceresi import TURLER, DonusumPenceresi
from .karsilastirma_penceresi import KarsilastirmaPenceresi

PDFDEN = (("pdf-word", "Word (.docx)…"), ("pdf-excel", "Excel (.xlsx)…"), ("pdf-pptx", "PowerPoint (.pptx)…"),
          ("pdf-resim", "Resim (PNG, JPG, BMP, TIFF)…"), ("pdf-metin", "Metin (.txt)…"), ("pdf-html", "HTML (.html)…"))
PDFE = (("resim-pdf", "Resimlerden…"), ("word-pdf", "Word belgesinden (.docx)…"), ("excel-pdf", "Excel dosyasından (.xlsx)…"),
        ("metin-pdf", "Metin dosyasından (.txt)…"), ("html-pdf", "HTML dosyasından…"))
TARAMA_RENKLERI = (("Renkli", "renkli"), ("Gri tonlama", "gri"), ("Siyah-beyaz", "siyahbeyaz"))


class DonusumArayuzu:
    def _donusum_kur(self):
        self.m_donustur = QMenu("Dö&nüştür", self)
        self.menuBar().insertMenu(self.m_sayfa.menuAction(), self.m_donustur)
        self._donusum_eylemleri = {}
        pdfden = self.m_donustur.addMenu(simgeler.simge("donustur"), "PDF'den")
        pdfe = self.m_donustur.addMenu(simgeler.simge("donustur"), "PDF'e")
        for menu, liste in ((pdfden, PDFDEN), (pdfe, PDFE)):
            for tur, ad in liste:
                e = self._eylem(ad, lambda t=tur: self.donustur_ac(t))
                self._donusum_eylemleri[tur] = e
                menu.addAction(e)
        self.e_sikistir = self._eylem("PDF Sıkıştır…", lambda: self.donustur_ac("sikistir"), simge="sikistir")
        self.e_karsilastir = self._eylem("PDF Karşılaştır…", self.karsilastir_ac, simge="karsilastir")
        self.e_tarayici = self._eylem("Tarayıcıdan PDF Oluştur…", self.tarayicidan_pdf, simge="tarayici")
        self.m_donustur.addSeparator()
        for e in (self.e_sikistir, self.e_karsilastir):
            self.m_donustur.addAction(e)
        self.m_donustur.addSeparator()
        self.m_donustur.addAction(self.e_tarayici)
        # araç çubuğu (ana çubuğun sonuna)
        self.arac.addSeparator()
        self.e_donustur_menu = self._eylem("Dönüştür", lambda: self.m_donustur.exec(self.arac.mapToGlobal(self.arac.rect().bottomRight())),
                                           simge="donustur")
        self.arac.addAction(self.e_donustur_menu)
        self.arac.addAction(self.e_sikistir)

    # --- ortak ---
    def _kayitli_pdf_yolu(self) -> str | None:
        """Açık belge kayıtlıysa yolu; değişmişse kullanıcıya sorar. None: kullanıcı vazgeçti ya da yol yok."""
        if not self.belge or not self.belge.yol:
            return None
        if self.belge.degisti:
            cevap = QMessageBox.question(
                self, APP_NAME, "Açık belgede kaydedilmemiş değişiklikler var. Dönüştürme/sıkıştırma kayıtlı dosyayı kullanır.\n"
                                "Önce “Farklı Kaydet” ile kaydetmek ister misiniz?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel, QMessageBox.Yes)
            if cevap == QMessageBox.Cancel:
                return ""
            if cevap == QMessageBox.Yes and not self.farkli_kaydet():
                return ""
        return str(self.belge.yol)

    def donustur_ac(self, tur: str):
        dosyalar: list[str] = []
        if TURLER[tur].girdi_uzantilari == (".pdf",):
            yol = self._kayitli_pdf_yolu()
            if yol == "":
                return
            if yol:
                dosyalar = [yol]
        d = DonusumPenceresi(tur, dosyalar, str(self.ayarlar.value("donusum_klasoru", "")), self)
        d.exec()
        if d.secili_klasor.isChecked() and d.klasor_kutu.text().strip():
            self.ayarlar.setValue("donusum_klasoru", d.klasor_kutu.text().strip())
        self._donusum_sonrasi(d)

    def _donusum_sonrasi(self, d: DonusumPenceresi):
        if not d.acilacak:
            return
        pdfler = [y for y in d.acilacak if y.lower().endswith(".pdf")]
        if d.tur.cikti_pdf and pdfler:
            self.ac_coklu(pdfler)   # her PDF çıktısı bir sekmede
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(d.acilacak[0]).parent)))

    def karsilastir_ac(self):
        a = self._kayitli_pdf_yolu()
        if a == "":
            return
        KarsilastirmaPenceresi(a or "", "", str(self.ayarlar.value("son_klasor", "")), self).exec()

    # --- tarayıcı ---
    def tarayicidan_pdf(self):
        if not tarayici.kullanilabilir():
            QMessageBox.information(self, APP_NAME, "Tarayıcıdan PDF oluşturmak yalnızca Windows'ta (WIA tarayıcı sürücüsüyle) çalışır.")
            return
        ad, tamam = QInputDialog.getItem(self, "Tarayıcıdan PDF", "Tarama rengi:", [a for a, _ in TARAMA_RENKLERI], 0, False)
        if not tamam:
            return
        renk = dict(TARAMA_RENKLERI)[ad]
        gecici = Path(tempfile.mkdtemp(prefix="eaglepdf-tarama-"))
        sayfalar: list[Path] = []
        try:
            while True:
                try:
                    sayfalar.append(tarayici.tara(gecici, renk))
                except donustur.Iptal:
                    break
                except BelgeHatasi as h:
                    QMessageBox.warning(self, APP_NAME, str(h))
                    break
                if QMessageBox.question(self, "Tarayıcıdan PDF", f"{len(sayfalar)} sayfa tarandı. Başka sayfa taramak ister misiniz?",
                                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
                    break
            if not sayfalar:
                return
            varsayilan = Path(str(self.ayarlar.value("son_klasor", ""))) / "Tarama.pdf"
            yol, _ = QFileDialog.getSaveFileName(self, "Taramayı Kaydet", str(varsayilan), "PDF belgeleri (*.pdf)")
            if not yol:
                return
            hedef = Path(yol if yol.lower().endswith(".pdf") else yol + ".pdf")
            if hedef.exists():  # üzerine yazmayı kullanıcı sistem penceresinde onayladı
                hedef.unlink()
            try:
                [pdf] = donustur.resimlerden_pdf(sayfalar, hedef.parent, hedef.stem, "A4", "otomatik", 0.0)
            except (BelgeHatasi, OSError) as h:
                QMessageBox.warning(self, APP_NAME, str(h))
                return
            self.ac(str(pdf))
        finally:
            shutil.rmtree(gecici, ignore_errors=True)
