"""OCR Dil Verisi penceresi: kurulu dilleri listeler; indirir (onayla), dosyadan ekler, siler.

Ağ erişimi yalnızca "İndir" düğmesi ve onay kutusundan sonra olur; belge ya da kişisel veri gönderilmez
(bkz. `core/ocr_veri.py`).
"""
from __future__ import annotations

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (QComboBox, QDialog, QFileDialog, QHBoxLayout, QLabel, QMessageBox, QProgressBar, QPushButton,
                               QTreeWidget, QTreeWidgetItem, QVBoxLayout)

from .. import APP_NAME
from ..core import ocr, ocr_veri
from ..core.hatalar import BelgeHatasi

ONAY_METNI = ("“{ad}” dil verisi ({kalite}) internetten indirilecek:\n{url}\n\n"
              "Yalnızca bu dosya istenir; belgeleriniz ya da kişisel bilgileriniz gönderilmez. İndirilen dosya "
              "kullanılmadan önce doğrulanır. İndirilsin mi?")


def boyut_metni(bayt: int) -> str:
    return f"{bayt / (1024 * 1024):.1f} MB"


class IndirmeIsi(QThread):
    ilerleme = Signal(int, int)
    bitti = Signal(str)    # kurulan dosyanın yolu
    hata = Signal(str)     # Türkçe hata ya da iptal iletisi

    def __init__(self, kod: str, kalite: str, hedef_klasor=None, acici=None, parent=None):
        super().__init__(parent)
        self._kod, self._kalite, self._hedef, self._acici = kod, kalite, hedef_klasor, acici
        self._iptal = False

    def iptal_et(self):
        self._iptal = True

    def _ilerle(self, okunan: int, toplam: int) -> bool:
        """İlerlemeyi arayüze bildirir; True dönerse indirme iptal edilir. (Not: `Signal.emit` PySide6'da True döndürür;
        bu yüzden `emit(...) or iptal` yazılırsa her indirme ilk blokta iptal olur.)"""
        self.ilerleme.emit(okunan, toplam)
        return self._iptal

    def run(self):
        try:
            yol = ocr_veri.indir(self._kod, self._kalite, self._hedef, ilerleme=self._ilerle, acici=self._acici)
        except ocr_veri.IndirmeIptal:
            self.hata.emit("İndirme iptal edildi.")
        except BelgeHatasi as h:
            self.hata.emit(str(h))
        except Exception as h:   # beklenmeyen: kullanıcıya anlaşılır göster, iş parçacığı sessizce ölmesin
            self.hata.emit(f"Beklenmeyen hata: {h}")
        else:
            self.bitti.emit(str(yol))


class OcrVeriPenceresi(QDialog):
    degisti = Signal()   # kurulu dil kümesi değişti (ana pencere/ayarlar OCR seçeneklerini yeniler)

    def __init__(self, parent=None, hedef_klasor=None, acici=None):
        super().__init__(parent)
        self.hedef_klasor, self.acici = hedef_klasor, acici
        self._is: IndirmeIsi | None = None
        self.setWindowTitle("OCR Dil Verisi")
        self.setMinimumSize(560, 460)
        yerlesim = QVBoxLayout(self)
        giris = QLabel("OCR (taranmış belgeden metin okuma) için dil verisi gerekir. Aşağıdan indirebilir ya da elinizdeki "
                       "bir “…traineddata” dosyasını ekleyebilirsiniz. Türkçe + İngilizce önerilir.")
        giris.setWordWrap(True)
        yerlesim.addWidget(giris)
        self.liste = QTreeWidget()
        self.liste.setHeaderLabels(["Dil", "Kod", "Boyut", "Konum"])
        self.liste.setRootIsDecorated(False)
        self.liste.itemSelectionChanged.connect(self._secim_degisti)
        yerlesim.addWidget(self.liste, 1)
        satir = QHBoxLayout()
        self.dil = QComboBox()
        for kod, ad in ocr_veri.KATALOG.items():
            self.dil.addItem(f"{ad} ({kod})", kod)
        self.kalite = QComboBox()
        for kod, (ad, _) in ocr_veri.KALITELER.items():
            self.kalite.addItem(ad, kod)
        self.indir_dugme = QPushButton("İndir…")
        self.indir_dugme.clicked.connect(self.indir_baslat)
        satir.addWidget(self.dil)
        satir.addWidget(self.kalite)
        satir.addWidget(self.indir_dugme)
        yerlesim.addLayout(satir)
        satir2 = QHBoxLayout()
        self.ekle_dugme = QPushButton("Dosyadan Ekle…")
        self.ekle_dugme.clicked.connect(self.dosyadan_ekle)
        self.sil_dugme = QPushButton("Seçileni Sil")
        self.sil_dugme.clicked.connect(self.sil)
        satir2.addWidget(self.ekle_dugme)
        satir2.addWidget(self.sil_dugme)
        satir2.addStretch()
        yerlesim.addLayout(satir2)
        self.cubuk = QProgressBar()
        self.cubuk.hide()
        self.iptal_dugme = QPushButton("İndirmeyi İptal Et")
        self.iptal_dugme.hide()
        self.iptal_dugme.clicked.connect(self._iptal_et)
        yerlesim.addWidget(self.cubuk)
        yerlesim.addWidget(self.iptal_dugme)
        self.durum = QLabel("")
        self.durum.setWordWrap(True)
        yerlesim.addWidget(self.durum)
        kapat = QPushButton("Kapat")
        kapat.clicked.connect(self.accept)
        yerlesim.addWidget(kapat)
        self.tazele()

    # --- liste ---
    def tazele(self):
        self.liste.clear()
        for d in ocr_veri.kurulu():
            oge = QTreeWidgetItem([d.ad, d.kod, boyut_metni(d.boyut), "Kullanıcı klasörü" if d.kullanici_klasorunde else "Sistem"])
            oge.setData(0, 256, d.kod)   # Qt.UserRole
            oge.setData(1, 256, d.kullanici_klasorunde)
            self.liste.addTopLevelItem(oge)
        for i in range(3):
            self.liste.resizeColumnToContents(i)
        if self.liste.topLevelItemCount() == 0:
            self.durum.setText("Henüz hiç dil verisi yok. Türkçe ve İngilizceyi indirmek için “İndir…”e basın.")
        self._secim_degisti()

    def kurulu_kodlar(self) -> list[str]:
        return [self.liste.topLevelItem(i).data(0, 256) for i in range(self.liste.topLevelItemCount())]

    def _secim_degisti(self):
        oge = self.liste.currentItem()
        self.sil_dugme.setEnabled(bool(oge and oge.data(1, 256)) and not self._calisiyor())

    def _calisiyor(self) -> bool:
        return self._is is not None and self._is.isRunning()

    # --- indirme ---
    def onay_sor(self, kod: str, kalite: str) -> bool:
        ad, depo = ocr_veri.dil_adi(kod), ocr_veri.KALITELER[kalite]
        url = ocr_veri.DEPO_URL.format(depo=depo[1], kod=kod)
        return QMessageBox.question(self, APP_NAME, ONAY_METNI.format(ad=ad, kalite=depo[0], url=url),
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes

    def indir_baslat(self):
        if self._calisiyor():
            return
        kod, kalite = self.dil.currentData(), self.kalite.currentData()
        if not self.onay_sor(kod, kalite):
            return
        self._is = IndirmeIsi(kod, kalite, self.hedef_klasor, self.acici, self)
        self._is.ilerleme.connect(self._ilerleme)
        self._is.bitti.connect(self._indirme_bitti)
        self._is.hata.connect(self._indirme_hatasi)
        self._is.finished.connect(self._is_bitti)
        self._mesgul(True)
        self.durum.setText(f"{ocr_veri.dil_adi(kod)} indiriliyor…")
        self._is.start()

    def _mesgul(self, acik: bool):
        for w in (self.indir_dugme, self.ekle_dugme, self.dil, self.kalite):
            w.setEnabled(not acik)
        self.cubuk.setVisible(acik)
        self.iptal_dugme.setVisible(acik)
        if acik:
            self.cubuk.setRange(0, 0)   # toplam bilinene kadar belirsiz
        self._secim_degisti()

    def _ilerleme(self, okunan: int, toplam: int):
        if toplam > 0:
            self.cubuk.setRange(0, 100)
            self.cubuk.setValue(int(100 * okunan / toplam))
        self.durum.setText(f"İndiriliyor… {boyut_metni(okunan)}" + (f" / {boyut_metni(toplam)}" if toplam else ""))

    def _indirme_bitti(self, yol: str):
        self.durum.setText(f"Kuruldu ve doğrulandı: {yol}")
        self.tazele()
        self.degisti.emit()

    def _indirme_hatasi(self, ileti: str):
        self.durum.setText(ileti)

    def _is_bitti(self):
        self._mesgul(False)

    def _iptal_et(self):
        if self._calisiyor():
            self._is.iptal_et()
            self.durum.setText("İptal ediliyor…")

    def bekle_bitsin(self, ms: int = 5000):
        if self._calisiyor():
            self._is.iptal_et()
            self._is.wait(ms)

    def done(self, kod):
        self.bekle_bitsin()   # pencere kapanırken çalışan indirme iptal edilir
        super().done(kod)

    # --- dosyadan ekle / sil ---
    def dosyadan_ekle(self):
        yollar, _ = QFileDialog.getOpenFileNames(self, "Dil Dosyası Seç", "", "Tesseract dil verisi (*.traineddata)")
        self._dosyalari_ekle(yollar)

    def _dosyalari_ekle(self, yollar):
        eklenen, hatalar = [], []
        for y in yollar:
            try:
                eklenen.append(ocr_veri.dosyadan_ekle(y, self.hedef_klasor).stem)
            except BelgeHatasi as h:
                hatalar.append(f"{y}: {h}")
        parcalar = []
        if eklenen:
            parcalar.append("Eklendi: " + ", ".join(eklenen))
            self.tazele()
            self.degisti.emit()
        if hatalar:
            parcalar.append("Eklenemedi:\n" + "\n".join(hatalar))
        if parcalar:
            self.durum.setText("\n".join(parcalar))
        return eklenen

    def sil(self):
        oge = self.liste.currentItem()
        if not oge or not oge.data(1, 256) or self._calisiyor():
            return
        kod = oge.data(0, 256)
        if QMessageBox.question(self, APP_NAME, f"“{ocr_veri.dil_adi(kod)}” dil verisi silinsin mi?\n(Yeniden indirebilirsiniz.)",
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        try:
            ocr_veri.sil(kod, self.hedef_klasor)
        except BelgeHatasi as h:
            self.durum.setText(str(h))
            return
        self.durum.setText(f"“{ocr_veri.dil_adi(kod)}” silindi.")
        self.tazele()
        self.degisti.emit()
