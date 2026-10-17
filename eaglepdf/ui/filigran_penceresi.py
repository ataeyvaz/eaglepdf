"""Filigran Temizle penceresi: belgeyi tarar, bulunan filigranları listeler, sayfa önizlemesinde kutularla gösterir,
elle işaretlenen alanı arar, seçilenleri siler ve sonucu yeni dosyaya yazar (orijinal korunur). Çekirdek: `core/filigran/`.

Tarama ve temizleme ayrı iş parçacığında çalışır (ilerleme + iptal). Temizlemeden önce telif/hak onayı zorunludur.
"""
from __future__ import annotations

import os
from pathlib import Path

import pymupdf as fitz
from PySide6.QtCore import QPoint, QRect, Qt, QThread, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout, QInputDialog, QLabel,
                               QLineEdit, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QScrollArea, QSplitter,
                               QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from .. import APP_NAME
from ..core.filigran import cleaner, detector, manual, ocr as fil_ocr, pdfops, report, rules

ZOOM = 1.3
TELIF_METNI = ("Bu belgede filigranı kaldırma hakkım var (belge bana ait, filigranı koyan kişi/kurum izin verdi ya da "
               "yasal olarak serbest). Başkasının telifli belgesinden izinsiz filigran silmeyeceğim.")


class TaramaIsi(QThread):
    ilerleme = Signal(int, int, str)
    bitti = Signal(object)    # ScanResult
    hata = Signal(str)

    def __init__(self, yol: str, parent=None):
        super().__init__(parent)
        self._yol = yol
        self._iptal = False

    def iptal_et(self):
        self._iptal = True

    def _ilerle(self, n, toplam, ileti=""):
        self.ilerleme.emit(int(n), int(toplam), str(ileti))

    def run(self):
        try:
            sonuc = detector.scan(self._yol, progress=self._ilerle, cancel=lambda: self._iptal, ocr=fil_ocr.available())
        except InterruptedError:
            self.hata.emit("Tarama iptal edildi.")
        except pdfops.PasswordRequired as h:
            self.hata.emit(str(h))
        except Exception as h:   # beklenmeyen: iş parçacığı sessizce ölmesin
            self.hata.emit(f"Tarama başarısız: {h}")
        else:
            self.bitti.emit(sonuc)


class TemizlemeIsi(QThread):
    ilerleme = Signal(int, int, str)
    bitti = Signal(object)    # CleanStats
    hata = Signal(str)

    def __init__(self, yol: str, bulgular: list, cikti: str, sayfalar, parent=None):
        super().__init__(parent)
        self._yol, self._bulgular, self._cikti, self._sayfalar = yol, bulgular, cikti, sayfalar

    def _ilerle(self, n, toplam, ileti=""):
        self.ilerleme.emit(int(n), int(toplam), str(ileti))

    def run(self):
        try:
            sonuc = cleaner.clean_file(self._yol, self._bulgular, self._cikti, progress=self._ilerle, verify=True,
                                       pages=self._sayfalar)
        except Exception as h:
            self.hata.emit(f"Temizleme başarısız: {h}")
        else:
            self.bitti.emit(sonuc)


class OnizlemeEtiketi(QLabel):
    """Sayfa görüntüsü; fareyle sürükleyerek dikdörtgen çizilir (elle filigran işaretleme)."""
    alanSecildi = Signal(object)   # fitz.Rect (sayfa koordinatları)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.alan_modu = False
        self._bas: QPoint | None = None
        self._simdi: QPoint | None = None

    def mousePressEvent(self, e):
        if self.alan_modu and e.button() == Qt.LeftButton:
            self._bas = self._simdi = e.position().toPoint()

    def mouseMoveEvent(self, e):
        if self._bas is not None:
            self._simdi = e.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, e):
        if self._bas is None:
            return
        r = QRect(self._bas, e.position().toPoint()).normalized()
        self._bas = self._simdi = None
        self.update()
        if r.width() >= 6 and r.height() >= 6:
            self.alanSecildi.emit(fitz.Rect(r.left() / ZOOM, r.top() / ZOOM, r.right() / ZOOM, r.bottom() / ZOOM))

    def paintEvent(self, e):
        super().paintEvent(e)
        if self._bas is not None and self._simdi is not None:
            p = QPainter(self)
            p.setPen(QPen(QColor("#1565c0"), 2, Qt.DashLine))
            p.drawRect(QRect(self._bas, self._simdi).normalized())


class FiligranPenceresi(QDialog):
    temizKaydedildi = Signal(str)   # temiz kopya yazıldı: ana pencere sekmede açmayı önerir

    def __init__(self, parent, yol: str, parola: str | None = None, engel_fn=None):
        """`yol`: kayıtlı PDF dosyası (çekirdek dosya üzerinde çalışır). `engel_fn(yol) -> bool`: True ise o yola yazılmaz."""
        super().__init__(parent)
        self.yol = str(yol)
        self.engel_fn = engel_fn
        self.sonuc: detector.ScanResult | None = None
        self._is: QThread | None = None
        self._ogeler: dict[str, QTreeWidgetItem] = {}
        self._sayfa = 0
        self._elle_sayac = 0
        pdfops.set_password(self.yol, parola)
        self.setWindowTitle(f"Filigran Temizle — {Path(self.yol).name}")
        self.resize(1100, 720)

        kok = QVBoxLayout(self)
        ust = QHBoxLayout()
        self.tara_dugme = QPushButton("Filigranları Tara")
        self.tara_dugme.clicked.connect(self.tara)
        ust.addWidget(self.tara_dugme)
        self.kural_kutu = QComboBox()
        self.kural_kutu.setMinimumWidth(160)
        self.kural_uygula = QPushButton("Kuralı Uygula")
        self.kural_uygula.clicked.connect(self._kurali_uygula)
        self.kural_kaydet = QPushButton("Seçilenleri Kural Yap…")
        self.kural_kaydet.clicked.connect(self._kural_kaydet)
        self.kural_sil = QPushButton("Kuralı Sil")
        self.kural_sil.clicked.connect(self._kural_sil)
        for w in (QLabel("Kural:"), self.kural_kutu, self.kural_uygula, self.kural_kaydet, self.kural_sil):
            ust.addWidget(w)
        ust.addStretch()
        self.rapor_dugme = QPushButton("Raporu Kaydet…")
        self.rapor_dugme.clicked.connect(self._rapor)
        ust.addWidget(self.rapor_dugme)
        kok.addLayout(ust)

        self.cubuk = QProgressBar()
        self.cubuk.hide()
        self.iptal_dugme = QPushButton("İptal")
        self.iptal_dugme.hide()
        self.iptal_dugme.clicked.connect(self._iptal)
        satir = QHBoxLayout()
        satir.addWidget(self.cubuk, 1)
        satir.addWidget(self.iptal_dugme)
        kok.addLayout(satir)

        bol = QSplitter(Qt.Horizontal)
        sol = QWidget()
        sol_y = QVBoxLayout(sol)
        sol_y.setContentsMargins(0, 0, 0, 0)
        self.agac = QTreeWidget()
        self.agac.setColumnCount(4)
        self.agac.setHeaderLabels(["Bulgu", "Tür", "Güven", "Sayfalar"])
        self.agac.setRootIsDecorated(False)
        self.agac.setColumnWidth(0, 230)
        self.agac.itemChanged.connect(self._secim_degisti)
        self.agac.currentItemChanged.connect(self._bulgu_secildi)
        sol_y.addWidget(self.agac, 3)
        self.ayrinti = QPlainTextEdit()
        self.ayrinti.setReadOnly(True)
        self.ayrinti.setPlaceholderText("Bir bulgu seçince nedenleri ve içeriği burada görünür.")
        self.ayrinti.setMaximumHeight(130)
        sol_y.addWidget(self.ayrinti)
        form = QFormLayout()
        self.yalniz = QLineEdit()
        self.yalniz.setPlaceholderText("Boş = tüm sayfalar (örn. 1-5, 8)")
        self.haric = QLineEdit()
        self.haric.setPlaceholderText("Temizlenmeyecek sayfalar")
        form.addRow("Yalnızca sayfalar:", self.yalniz)
        form.addRow("Hariç sayfalar:", self.haric)
        sol_y.addLayout(form)
        bol.addWidget(sol)

        sag = QWidget()
        sag_y = QVBoxLayout(sag)
        sag_y.setContentsMargins(0, 0, 0, 0)
        gezin = QHBoxLayout()
        self.onceki = QPushButton("◀")
        self.sonraki = QPushButton("▶")
        self.onceki.clicked.connect(lambda: self._sayfaya_git(self._sayfa - 1))
        self.sonraki.clicked.connect(lambda: self._sayfaya_git(self._sayfa + 1))
        self.sayfa_etiket = QLabel("")
        self.sonra_kutu = QCheckBox("Temizlenmiş halini göster")
        self.sonra_kutu.toggled.connect(lambda _=None: self._cizdir())
        self.elle_dugme = QPushButton("Alan İşaretle")
        self.elle_dugme.setCheckable(True)
        self.elle_dugme.setToolTip("Önizlemede filigranın üstüne dikdörtgen sürükleyin; o alandaki nesneler aranır.")
        self.elle_dugme.toggled.connect(self._elle_modu)
        for w in (self.onceki, self.sayfa_etiket, self.sonraki, self.sonra_kutu):
            gezin.addWidget(w)
        gezin.addStretch()
        gezin.addWidget(self.elle_dugme)
        sag_y.addLayout(gezin)
        self.onizleme = OnizlemeEtiketi()
        self.onizleme.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.onizleme.alanSecildi.connect(self._alan_secildi)
        kaydir = QScrollArea()
        kaydir.setWidget(self.onizleme)
        kaydir.setWidgetResizable(False)
        sag_y.addWidget(kaydir, 1)
        bol.addWidget(sag)
        bol.setSizes([430, 670])
        kok.addWidget(bol, 1)

        self.uyari = QLabel("")
        self.uyari.setWordWrap(True)
        self.uyari.setStyleSheet("color:#8a6d00")
        kok.addWidget(self.uyari)
        self.telif = QCheckBox(TELIF_METNI)
        self.telif.toggled.connect(self._dugmeleri_ayarla)
        kok.addWidget(self.telif)
        alt = QHBoxLayout()
        self.durum = QLabel("")
        self.durum.setWordWrap(True)
        alt.addWidget(self.durum, 1)
        self.temizle_dugme = QPushButton("Seçilenleri Sil ve Kaydet…")
        self.temizle_dugme.clicked.connect(self.temizle)
        kapat = QPushButton("Kapat")
        kapat.clicked.connect(self.reject)
        alt.addWidget(self.temizle_dugme)
        alt.addWidget(kapat)
        kok.addLayout(alt)

        self._kurallari_yukle()
        if not fil_ocr.available():
            self.uyari.setText("OCR dil verisi kurulu değil: taranmış sayfa filigranlarının yazısı okunamaz "
                               "(OCR → Dil Verisi…). Tarama ve temizleme yine çalışır.")
        self._dugmeleri_ayarla()

    # --- durum ---
    def _mesgul(self) -> bool:
        return self._is is not None and self._is.isRunning()

    def _dugmeleri_ayarla(self, *_):
        bos = self._mesgul()
        var = self.sonuc is not None and not bos
        self.tara_dugme.setEnabled(not bos)
        for w in (self.kural_uygula, self.kural_kaydet, self.kural_sil, self.rapor_dugme, self.elle_dugme):
            w.setEnabled(var)
        self.kural_uygula.setEnabled(var and self.kural_kutu.count() > 0)
        self.kural_sil.setEnabled(var and self.kural_kutu.count() > 0)
        self.temizle_dugme.setEnabled(var and self.telif.isChecked() and bool(self.secili_bulgular()))

    def secili_bulgular(self) -> list:
        return [f for f in (self.sonuc.findings if self.sonuc else []) if f.selected]

    def _is_baslat(self, is_, ilerleme_iletisi: str):
        self._is = is_
        is_.ilerleme.connect(self._ilerle)
        self.cubuk.setRange(0, 0)
        self.cubuk.show()
        self.iptal_dugme.setVisible(isinstance(is_, TaramaIsi))
        self.durum.setText(ilerleme_iletisi)
        is_.start()
        self._dugmeleri_ayarla()

    def _is_bitti(self):
        self.cubuk.hide()
        self.iptal_dugme.hide()
        self._dugmeleri_ayarla()

    def _ilerle(self, n: int, toplam: int, ileti: str):
        if toplam > 0:
            self.cubuk.setRange(0, toplam)
            self.cubuk.setValue(min(n, toplam))
        if ileti:
            self.durum.setText(ileti)

    def _iptal(self):
        if isinstance(self._is, TaramaIsi):
            self._is.iptal_et()

    def reject(self):
        if self._mesgul():
            if isinstance(self._is, TaramaIsi):
                self._is.iptal_et()
            self._is.wait(5000)
            if self._is.isRunning():
                return
        super().reject()

    # --- tarama ---
    def tara(self):
        if self._mesgul():
            return
        self.sonuc = None
        self.agac.clear()
        self._ogeler.clear()
        self.ayrinti.clear()
        is_ = TaramaIsi(self.yol, self)
        is_.bitti.connect(self._tarama_bitti)
        is_.hata.connect(self._is_hata)
        self._is_baslat(is_, "Taranıyor…")

    def _is_hata(self, ileti: str):
        self._is_bitti()
        self.durum.setText(ileti)
        if "iptal" not in ileti:
            QMessageBox.warning(self, APP_NAME, ileti)

    def _tarama_bitti(self, sonuc):
        self.sonuc = sonuc
        self._is_bitti()
        self.agac.blockSignals(True)
        for f in sonuc.findings:
            self._ogeyi_ekle(f)
        self.agac.blockSignals(False)
        notlar = []
        if sonuc.bilevel_pages:
            notlar.append(f"{len(sonuc.bilevel_pages)} sayfa 1-bit (siyah-beyaz) tarama: filigranı yalnızca sayfalar arası aynı piksel "
                          "deseniyle aranır (deneysel); bulunduysa önizlemede kontrol edip kendiniz işaretleyin.")
        if sonuc.scanned_pages:
            notlar.append(f"{len(sonuc.scanned_pages)} taranmış sayfa var; filigran resimden çıkarılıp yeniden yazılır.")
        if not fil_ocr.available():
            notlar.append("OCR dil verisi yok: taranmış filigran yazıları okunamadı.")
        self.uyari.setText(" ".join(notlar))
        n = len(sonuc.findings)
        self.durum.setText(f"{n} bulgu, {len(self.secili_bulgular())} tanesi otomatik seçildi." if n else
                           "Filigran bulunamadı. Gerekirse “Alan İşaretle” ile elle gösterebilirsiniz.")
        self._sayfaya_git(self._ilk_sayfa())
        self._dugmeleri_ayarla()

    def _ilk_sayfa(self) -> int:
        for f in self.sonuc.findings:
            if f.selected and f.pages:
                return f.pages[0]
        return 0

    def _ogeyi_ekle(self, f):
        it = QTreeWidgetItem([f.title, detector.KIND_LABELS.get(f.kind, f.kind), f"{f.score:.2f}", self._sayfa_metni(f)])
        it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
        it.setCheckState(0, Qt.Checked if f.selected else Qt.Unchecked)
        it.setData(0, Qt.UserRole, f.id)
        self.agac.addTopLevelItem(it)
        self._ogeler[f.id] = it

    @staticmethod
    def _sayfa_metni(f) -> str:
        p = [x + 1 for x in f.pages]
        if not p:
            return "—"
        return str(p[0]) if len(p) == 1 else f"{len(p)} sayfa ({p[0]}…{p[-1]})"

    def _bul(self, kimlik: str):
        return next((f for f in self.sonuc.findings if f.id == kimlik), None) if self.sonuc else None

    def _secim_degisti(self, item, _kolon):
        f = self._bul(item.data(0, Qt.UserRole))
        if f:
            f.selected = item.checkState(0) == Qt.Checked
            self._dugmeleri_ayarla()
            self._cizdir()

    def _bulgu_secildi(self, item, _onceki=None):
        f = self._bul(item.data(0, Qt.UserRole)) if item else None
        if not f:
            self.ayrinti.clear()
            return
        satirlar = [f.title, ""]
        if f.text:
            satirlar += ["İçerik:", f.text, ""]
        satirlar += ["Nedenler:"] + [f"• {r}" for r in f.reasons]
        if f.urls:
            satirlar += ["", "Adresler: " + ", ".join(f.urls)]
        self.ayrinti.setPlainText("\n".join(satirlar))
        if f.pages and self._sayfa not in f.pages:
            self._sayfaya_git(f.pages[0])
        else:
            self._cizdir()

    # --- önizleme ---
    def _sayfaya_git(self, n: int):
        if not self.sonuc:
            return
        self._sayfa = max(0, min(n, self.sonuc.page_count - 1))
        self._cizdir()

    def _cizdir(self):
        if not self.sonuc:
            return
        n = self.sonuc.page_count
        self.sayfa_etiket.setText(f"Sayfa {self._sayfa + 1} / {n}")
        self.onceki.setEnabled(self._sayfa > 0)
        self.sonraki.setEnabled(self._sayfa < n - 1)
        doc = None
        try:
            if self.sonra_kutu.isChecked():
                doc = cleaner.preview_page(self.yol, self.secili_bulgular(), self._sayfa)
            else:
                doc = pdfops.open_pdf(self.yol)
            pix = doc[self._sayfa].get_pixmap(matrix=fitz.Matrix(ZOOM, ZOOM), alpha=False)
            img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888).copy()
        except Exception as h:
            self.onizleme.setText(f"Önizleme çizilemedi: {h}")
            return
        finally:
            if doc is not None:
                doc.close()
        harita = QPixmap.fromImage(img)
        if not self.sonra_kutu.isChecked():
            self._kutulari_ciz(harita)
        self.onizleme.setPixmap(harita)
        self.onizleme.resize(harita.size())

    def _kutulari_ciz(self, harita: QPixmap):
        mevcut = self.agac.currentItem()
        vurgulu = mevcut.data(0, Qt.UserRole) if mevcut else None
        p = QPainter(harita)
        for f in self.sonuc.findings:
            if not f.selected and f.id != vurgulu:
                continue
            renk = QColor("#1565c0") if f.id == vurgulu else QColor("#c62828")
            p.setPen(QPen(renk, 3 if f.id == vurgulu else 2))
            for o in f.occurrences:
                if o.page == self._sayfa:
                    x0, y0, x1, y1 = o.bbox
                    p.drawRect(QRect(int(x0 * ZOOM), int(y0 * ZOOM), int((x1 - x0) * ZOOM), int((y1 - y0) * ZOOM)))
        p.end()

    # --- elle işaretleme ---
    def _elle_modu(self, acik: bool):
        self.onizleme.alan_modu = acik
        self.onizleme.setCursor(Qt.CrossCursor if acik else Qt.ArrowCursor)
        if acik:
            self.sonra_kutu.setChecked(False)
            self.durum.setText("Önizlemede filigranın üstüne dikdörtgen sürükleyin.")

    def _alan_secildi(self, rect):
        if not self.sonuc or self._mesgul():
            return
        self.setCursor(Qt.WaitCursor)
        try:
            bulunan = manual.search(self.yol, self.sonuc, self._sayfa, rect)
        except Exception as h:
            QMessageBox.warning(self, APP_NAME, f"Alan aranamadı: {h}")
            return
        finally:
            self.unsetCursor()
        if not bulunan:
            self.durum.setText("Seçilen alanda nesne bulunamadı.")
            return
        self.agac.blockSignals(True)
        for f in bulunan:
            self._elle_sayac += 1
            f.id = f"M{self._elle_sayac}"
            self.sonuc.findings.append(f)
            self._ogeyi_ekle(f)
        self.agac.blockSignals(False)
        self.agac.setCurrentItem(self._ogeler[bulunan[0].id])
        self.durum.setText(f"{len(bulunan)} nesne bulundu; en filigran benzeri seçildi, gerekirse listeden değiştirin.")
        self._dugmeleri_ayarla()
        self._cizdir()

    # --- kurallar ---
    def _kurallari_yukle(self, secili: str = ""):
        self.kural_kutu.clear()
        for r in rules.load_rules():
            self.kural_kutu.addItem(r["name"], r)
        if secili and self.kural_kutu.findText(secili) >= 0:
            self.kural_kutu.setCurrentIndex(self.kural_kutu.findText(secili))

    def _esitle_agac(self):
        self.agac.blockSignals(True)
        for f in self.sonuc.findings:
            self._ogeler[f.id].setCheckState(0, Qt.Checked if f.selected else Qt.Unchecked)
        self.agac.blockSignals(False)
        self._dugmeleri_ayarla()
        self._cizdir()

    def _kurali_uygula(self):
        kural = self.kural_kutu.currentData()
        if not kural or not self.sonuc:
            return
        n = rules.apply_rule(kural, self.sonuc.findings)
        self._esitle_agac()
        self.durum.setText(f"“{kural['name']}” kuralıyla {n} bulgu seçildi.")

    def _kural_kaydet(self):
        secili = self.secili_bulgular()
        if not secili:
            QMessageBox.information(self, APP_NAME, "Önce kural yapılacak bulguları işaretleyin.")
            return
        ad, tamam = QInputDialog.getText(self, "Kural Kaydet", "Kural adı (örn. yayıncının adı):")
        if tamam and ad.strip():
            rules.add_rule(ad.strip(), secili)
            self._kurallari_yukle(ad.strip())
            self._dugmeleri_ayarla()
            self.durum.setText(f"“{ad.strip()}” kuralı kaydedildi; başka belgelerde “Kuralı Uygula” ile kullanılır.")

    def _kural_sil(self):
        ad = self.kural_kutu.currentText()
        if ad and QMessageBox.question(self, APP_NAME, f"“{ad}” kuralı silinsin mi?") == QMessageBox.Yes:
            rules.delete_rule(ad)
            self._kurallari_yukle()
            self._dugmeleri_ayarla()

    # --- rapor ---
    def _rapor(self):
        if not self.sonuc:
            return
        yol, secim = QFileDialog.getSaveFileName(self, "Raporu Kaydet", str(Path(self.yol).with_suffix("")) + "_filigran_raporu.json",
                                                 "JSON (*.json);;CSV (*.csv)")
        if not yol:
            return
        try:
            (report.export_csv if yol.lower().endswith(".csv") else report.export_json)([self.sonuc], yol)
        except OSError as h:
            QMessageBox.warning(self, APP_NAME, f"Rapor yazılamadı: {h}")
            return
        self.durum.setText(f"Rapor kaydedildi: {yol}")

    # --- temizleme ---
    def sayfa_kumesi(self):
        """Yalnızca/hariç alanlarından 0 tabanlı sayfa kümesi; kısıt yoksa None. Hatalı girişte ValueError."""
        return pdfops.page_selection(self.yalniz.text(), self.haric.text(), self.sonuc.page_count)

    def temizle(self):
        if not self.sonuc or self._mesgul() or not self.telif.isChecked():
            return
        secili = self.secili_bulgular()
        if not secili:
            return
        try:
            sayfalar = self.sayfa_kumesi()
        except ValueError as h:
            QMessageBox.warning(self, APP_NAME, f"Sayfa aralığı anlaşılamadı: {h}")
            return
        if sayfalar is not None and not sayfalar:
            QMessageBox.warning(self, APP_NAME, "Seçilen aralıkta temizlenecek sayfa kalmadı.")
            return
        varsayilan = cleaner.output_path_for(self.yol)
        yol, _ = QFileDialog.getSaveFileName(self, "Temiz Kopyayı Kaydet", varsayilan, "PDF (*.pdf)")
        if not yol:
            return
        if os.path.normcase(os.path.abspath(yol)) == os.path.normcase(os.path.abspath(self.yol)):
            QMessageBox.warning(self, APP_NAME, "Orijinal dosyanın üzerine yazılmaz; başka bir ad seçin.")
            return
        if self.engel_fn and self.engel_fn(yol):
            return
        is_ = TemizlemeIsi(self.yol, secili, yol, sayfalar, self)
        is_.bitti.connect(self._temizleme_bitti)
        is_.hata.connect(self._is_hata)
        self._is_baslat(is_, "Filigranlar siliniyor…")

    def _temizleme_bitti(self, st):
        self._is_bitti()
        ileti = st.summary()
        if st.remaining:
            ileti += f"\n\nDikkat: {len(st.remaining)} filigran hâlâ bulunuyor (ör. “{st.remaining[0].title}”). " \
                     "Çıktıyı kontrol edin; gerekirse alanı elle işaretleyip tekrar deneyin."
        for w in st.warnings[:5]:
            ileti += f"\n• {w}"
        self.durum.setText(ileti.split("\n")[0])
        QMessageBox.information(self, APP_NAME, ileti)
        self.temizKaydedildi.emit(st.output)
