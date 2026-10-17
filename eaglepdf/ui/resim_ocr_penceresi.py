"""Resimden Metin Çıkar penceresi: resim dosyalarını (PNG, JPEG, TIFF…) OCR'lar; metni gösterir/kopyalar/.txt kaydeder,
istenirse aranabilir PDF (resim + görünmez metin) olarak kaydeder (kaydedince sekmede açmayı önerir).
OCR ayrı iş parçacığında çalışır; ilerleme ve iptal vardır. Çekirdek: `core/resim_ocr.py`.
"""
from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QListWidget,
                               QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QVBoxLayout)

from .. import APP_NAME
from ..core import ocr, resim_ocr
from ..core.belge import BelgeHatasi, _gecici_yaz
from .ocr_arayuzu import dil_secenekleri

RESIM_FILTRESI = "Resimler (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp *.gif)"
DPI_SECENEKLERI = ((200, "200 DPI (hızlı)"), (300, "300 DPI (önerilen)"), (400, "400 DPI (küçük yazı, yavaş)"))


class ResimOcrIsi(QThread):
    ilerleme = Signal(int, int)
    bitti = Signal(object)   # ResimOcrSonucu
    hata = Signal(str)       # Türkçe hata ya da iptal iletisi

    def __init__(self, yollar: list[str], dil: str, dpi: int, parent=None):
        super().__init__(parent)
        self._yollar, self._dil, self._dpi = yollar, dil, dpi
        self._iptal = False

    def iptal_et(self):
        self._iptal = True

    def _ilerle(self, n: int, toplam: int) -> bool:
        self.ilerleme.emit(n, toplam)   # (Signal.emit True döndürür: `emit(...) or iptal` her seferinde iptal ederdi)
        return self._iptal

    def run(self):
        try:
            sonuc = resim_ocr.resimlerden_ocr(self._yollar, self._dil, self._dpi, ilerleme=self._ilerle)
        except ocr.OcrIptal:
            self.hata.emit("İşlem iptal edildi.")
        except BelgeHatasi as h:
            self.hata.emit(str(h))
        except Exception as h:   # beklenmeyen: iş parçacığı sessizce ölmesin
            self.hata.emit(f"Beklenmeyen hata: {h}")
        else:
            self.bitti.emit(sonuc)


class ResimOcrPenceresi(QDialog):
    pdfKaydedildi = Signal(str)   # aranabilir PDF kaydedildi: ana pencere sekmede açmayı önerir

    def __init__(self, parent=None, yollar: list[str] | None = None, varsayilan_dil: str = "", engel_fn=None):
        """`engel_fn(yol) -> bool`: True ise o yola yazılmaz (ana pencere: başka sekmede açık dosya)."""
        super().__init__(parent)
        self.engel_fn = engel_fn
        self.sonuc: resim_ocr.ResimOcrSonucu | None = None
        self._is: ResimOcrIsi | None = None
        self.setWindowTitle("Resimden Metin Çıkar (OCR)")
        self.setMinimumSize(640, 600)
        self.setAcceptDrops(True)
        yerlesim = QVBoxLayout(self)
        giris = QLabel("PNG, JPEG, TIFF, BMP, WEBP ya da GIF dosyalarındaki yazıyı okur. Resimleri aşağıya sürükleyip bırakabilirsiniz. "
                       "Çok sayfalı TIFF'in her sayfası ayrı okunur.")
        giris.setWordWrap(True)
        yerlesim.addWidget(giris)
        self.liste = QListWidget()
        self.liste.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.liste.setMaximumHeight(130)
        yerlesim.addWidget(self.liste)
        satir = QHBoxLayout()
        self.ekle_dugme = QPushButton("Resim Ekle…")
        self.ekle_dugme.clicked.connect(self._ekle_sor)
        self.kaldir_dugme = QPushButton("Seçilileri Kaldır")
        self.kaldir_dugme.clicked.connect(self._kaldir)
        satir.addWidget(self.ekle_dugme)
        satir.addWidget(self.kaldir_dugme)
        satir.addStretch()
        yerlesim.addLayout(satir)
        form = QFormLayout()
        self.dil = QComboBox()
        for kod, ad in dil_secenekleri():
            self.dil.addItem(ad, kod)
        if varsayilan_dil and self.dil.findData(varsayilan_dil) >= 0:
            self.dil.setCurrentIndex(self.dil.findData(varsayilan_dil))
        self.dpi = QComboBox()
        for d, ad in DPI_SECENEKLERI:
            self.dpi.addItem(ad, d)
        self.dpi.setCurrentIndex(self.dpi.findData(300))
        form.addRow("Dil:", self.dil)
        form.addRow("OCR çözünürlüğü:", self.dpi)
        yerlesim.addLayout(form)
        self.oku_dugme = QPushButton("Metni Oku")
        self.oku_dugme.clicked.connect(self.oku)
        yerlesim.addWidget(self.oku_dugme)
        self.cubuk = QProgressBar()
        self.cubuk.hide()
        self.iptal_dugme = QPushButton("İptal")
        self.iptal_dugme.hide()
        self.iptal_dugme.clicked.connect(self._iptal_et)
        yerlesim.addWidget(self.cubuk)
        yerlesim.addWidget(self.iptal_dugme)
        self.metin = QPlainTextEdit()
        self.metin.setPlaceholderText("Okunan metin burada görünür (düzenleyebilirsiniz).")
        yerlesim.addWidget(self.metin, 1)
        sonuc_satiri = QHBoxLayout()
        self.kopyala_dugme = QPushButton("Panoya Kopyala")
        self.kopyala_dugme.clicked.connect(self.kopyala)
        self.txt_dugme = QPushButton("Metni Kaydet (.txt)…")
        self.txt_dugme.clicked.connect(self.txt_kaydet)
        self.pdf_dugme = QPushButton("Aranabilir PDF Kaydet…")
        self.pdf_dugme.clicked.connect(self.pdf_kaydet)
        for d in (self.kopyala_dugme, self.txt_dugme, self.pdf_dugme):
            sonuc_satiri.addWidget(d)
        yerlesim.addLayout(sonuc_satiri)
        self.durum = QLabel("")
        self.durum.setWordWrap(True)
        yerlesim.addWidget(self.durum)
        kapat = QPushButton("Kapat")
        kapat.clicked.connect(self.accept)
        yerlesim.addWidget(kapat)
        if yollar:
            self.resim_ekle(yollar)
        self._durum_guncelle()

    # --- liste ---
    def yollar(self) -> list[str]:
        return [self.liste.item(i).text() for i in range(self.liste.count())]

    def resim_ekle(self, yollar) -> int:
        """Resim olmayanları ve yinelenenleri atlayarak ekler; eklenen sayıyı döndürür."""
        var = set(self.yollar())
        eklenen = 0
        for y in (os.path.normpath(str(y)) for y in yollar):   # Qt düz eğik çizgi, dosya penceresi ters verir: tek biçime indir
            if resim_ocr.resim_mi(y) and y not in var:
                self.liste.addItem(y)
                var.add(y)
                eklenen += 1
        self._durum_guncelle()
        return eklenen

    def _ekle_sor(self):
        yollar, _ = QFileDialog.getOpenFileNames(self, "Resim Seç", "", RESIM_FILTRESI)
        self.resim_ekle(yollar)

    def _kaldir(self):
        for oge in self.liste.selectedItems():
            self.liste.takeItem(self.liste.row(oge))
        self._durum_guncelle()

    def dragEnterEvent(self, olay):
        if olay.mimeData().hasUrls() and any(resim_ocr.resim_mi(u.toLocalFile()) for u in olay.mimeData().urls()):
            olay.acceptProposedAction()

    def dropEvent(self, olay):
        self.resim_ekle([u.toLocalFile() for u in olay.mimeData().urls()])
        olay.acceptProposedAction()

    # --- durum ---
    def _calisiyor(self) -> bool:
        return self._is is not None and self._is.isRunning()

    def _durum_guncelle(self):
        mesgul = self._calisiyor()
        self.oku_dugme.setEnabled(not mesgul and self.liste.count() > 0 and self.dil.count() > 0)
        for w in (self.ekle_dugme, self.kaldir_dugme, self.dil, self.dpi, self.liste):
            w.setEnabled(not mesgul)
        var = self.sonuc is not None
        self.kopyala_dugme.setEnabled(var and not mesgul)
        self.txt_dugme.setEnabled(var and not mesgul)
        self.pdf_dugme.setEnabled(var and not mesgul)
        self.cubuk.setVisible(mesgul)
        self.iptal_dugme.setVisible(mesgul)
        if self.dil.count() == 0:
            self.durum.setText("OCR dil verisi kurulu değil: OCR menüsünden “Dil Verisi…” ile kurun.")

    # --- OCR ---
    def oku(self):
        if self._calisiyor() or not self.yollar():
            return
        self.sonuc = None
        self.metin.clear()
        self.cubuk.setRange(0, 0)
        self._is = ResimOcrIsi(self.yollar(), self.dil.currentData(), self.dpi.currentData(), self)
        self._is.ilerleme.connect(self._ilerleme)
        self._is.bitti.connect(self._bitti)
        self._is.hata.connect(self._hata)
        self._is.finished.connect(self._durum_guncelle)
        self.durum.setText("Okunuyor…")
        self._is.start()
        self._durum_guncelle()

    def _ilerleme(self, n: int, toplam: int):
        if self._is is not None and self._is._iptal:   # iptal istendi: sıradaki eski ilerleme "İptal ediliyor…"u ezmesin
            return
        if toplam > 0:
            self.cubuk.setRange(0, toplam)
            self.cubuk.setValue(n)
        self.durum.setText(f"Okunuyor… ({min(n + 1, toplam)}/{toplam})")

    def _bitti(self, sonuc):
        self.sonuc = sonuc
        self.metin.setPlainText(sonuc.toplu_metin())
        parcalar = [f"{len(sonuc.sayfalar)} sayfa okundu"]
        if sonuc.bos_mu:
            parcalar.append("hiç metin bulunamadı (resim bulanık/boş olabilir ya da dil yanlış seçilmiş olabilir)")
        if sonuc.hatalar:
            parcalar.append("okunamayanlar:\n" + "\n".join(sonuc.hatalar))
        self.durum.setText("; ".join(parcalar[:2]) + ("\n" + parcalar[2] if len(parcalar) > 2 else "") + ".")

    def _hata(self, ileti: str):
        self.durum.setText(ileti)

    def _iptal_et(self):
        if self._calisiyor():
            self._is.iptal_et()
            self.durum.setText("İptal ediliyor…")

    def done(self, kod):
        if self._calisiyor():   # pencere kapanırken çalışan OCR durdurulur
            self._is.iptal_et()
            self._is.wait(8000)
        super().done(kod)

    # --- çıktılar ---
    def duzenlenmis_metin(self) -> str:
        return self.metin.toPlainText()

    def kopyala(self):
        QGuiApplication.clipboard().setText(self.duzenlenmis_metin())
        self.durum.setText("Metin panoya kopyalandı.")

    def txt_kaydet(self):
        if self.sonuc is None:
            return
        varsayilan = str(Path(self.yollar()[0]).with_suffix(".txt")) if self.yollar() else "metin.txt"
        yol, _ = QFileDialog.getSaveFileName(self, "Metni Kaydet", varsayilan, "Metin dosyası (*.txt)")
        if yol:
            self._txt_yaz(Path(yol if yol.lower().endswith(".txt") else yol + ".txt"))

    def _txt_yaz(self, hedef: Path):
        try:
            _gecici_yaz(lambda g: Path(g).write_text(self.duzenlenmis_metin(), encoding="utf-8-sig"), hedef)   # Türkçe için BOM'lu UTF-8
        except OSError as h:
            QMessageBox.warning(self, APP_NAME, f"Kaydedilemedi:\n{h}")
            return
        self.durum.setText(f"Metin kaydedildi: {hedef}")

    def pdf_kaydet(self):
        if self.sonuc is None:
            return
        varsayilan = str(Path(self.yollar()[0]).with_suffix(".pdf")) if self.yollar() else "ocr.pdf"
        yol, _ = QFileDialog.getSaveFileName(self, "Aranabilir PDF Kaydet", varsayilan, "PDF Belgeleri (*.pdf)")
        if yol:
            self._pdf_yaz(Path(yol if yol.lower().endswith(".pdf") else yol + ".pdf"))

    def _pdf_yaz(self, hedef: Path):
        if self.engel_fn and self.engel_fn(hedef):   # başka sekmede açık dosyanın üzerine yazılmaz
            return
        try:
            _gecici_yaz(lambda g: Path(g).write_bytes(self.sonuc.pdf), hedef)
        except OSError as h:
            QMessageBox.warning(self, APP_NAME, f"Kaydedilemedi:\n{h}")
            return
        self.durum.setText(f"Aranabilir PDF kaydedildi: {hedef}")
        self.pdfKaydedildi.emit(str(hedef))
