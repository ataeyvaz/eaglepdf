"""Ana pencerenin Faz 5 OCR bölümü: OCR menüsü (aranabilir PDF yap, bölgeden metin çıkar).

`AnaPencere`ye karışım olarak eklenir; `belge`, `ayarlar`, `m_sayfa`, `_eylem`, `_dene`, `_arac_grubu`,
`_arac_eylemleri`, `_arac_uygula` üyelerini kullanır.
"""

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QApplication, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit,
                               QMenu, QMessageBox, QPlainTextEdit, QProgressDialog, QPushButton, QVBoxLayout)

from .. import APP_NAME
from ..core import ocr
from ..core.belge import BelgeHatasi, aralik_coz

IPUCLARI = {"ocr_bolge": "Metni çıkarılacak alanı sürükleyerek seçin; metin panoya kopyalanabilir."}
DIL_SECENEKLERI = (("tur+eng", "Türkçe + İngilizce"), ("tur", "Yalnızca Türkçe"), ("eng", "Yalnızca İngilizce"))


def dil_secenekleri() -> list[tuple[str, str]]:
    """Dil verisi kurulu olan seçenekler."""
    return [(kod, ad) for kod, ad in DIL_SECENEKLERI if ocr.hazir_mi(kod)]


class AranabilirPenceresi(QDialog):
    def __init__(self, sayfa_sayisi: int, metinsiz: int, parent=None, varsayilan_dil: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Aranabilir PDF Yap (OCR)")
        self.setMinimumWidth(420)
        self._sayfa_sayisi = sayfa_sayisi
        yerlesim = QVBoxLayout(self)
        yerlesim.addWidget(QLabel(
            f"Taranmış sayfalara görünmez bir metin katmanı eklenir; görünüm değişmez, ama arama, seçme ve kopyalama çalışır.\n"
            f"Belgede {sayfa_sayisi} sayfadan {metinsiz} tanesinde metin yok. Metni olan sayfalar atlanır."))
        form = QFormLayout()
        self.sayfalar = QLineEdit()
        self.sayfalar.setPlaceholderText("Boş = tüm sayfalar (örn. 1-3, 5)")
        self.dil = QComboBox()
        for kod, ad in dil_secenekleri():
            self.dil.addItem(ad, kod)
        if varsayilan_dil and self.dil.findData(varsayilan_dil) >= 0:
            self.dil.setCurrentIndex(self.dil.findData(varsayilan_dil))
        form.addRow("Sayfalar:", self.sayfalar)
        form.addRow("Dil:", self.dil)
        yerlesim.addLayout(form)
        self.hata = QLabel()
        self.hata.setStyleSheet("color:#c62828")
        yerlesim.addWidget(self.hata)
        dugmeler = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        dugmeler.button(QDialogButtonBox.Ok).setText("Başlat")
        dugmeler.button(QDialogButtonBox.Cancel).setText("Vazgeç")
        dugmeler.accepted.connect(self._onayla)
        dugmeler.rejected.connect(self.reject)
        yerlesim.addWidget(dugmeler)

    def _onayla(self):
        try:
            self.secili_sayfalar()
        except BelgeHatasi as h:
            self.hata.setText(str(h))
            return
        if self.dil.count() == 0:
            self.hata.setText("OCR dil verisi kurulu değil.")
            return
        self.accept()

    def secili_sayfalar(self) -> list[int] | None:
        metin = self.sayfalar.text().strip()
        return aralik_coz(metin, self._sayfa_sayisi) if metin else None

    def secili_dil(self) -> str:
        return self.dil.currentData()


class OcrMetinPenceresi(QDialog):
    def __init__(self, metin: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Bölgeden Çıkarılan Metin")
        self.resize(480, 320)
        yerlesim = QVBoxLayout(self)
        self.kutu = QPlainTextEdit(metin)
        yerlesim.addWidget(self.kutu)
        self.kopyala = QPushButton("Panoya Kopyala")
        self.kopyala.clicked.connect(self._kopyala)
        kapat = QPushButton("Kapat")
        kapat.clicked.connect(self.accept)
        yerlesim.addWidget(self.kopyala)
        yerlesim.addWidget(kapat)

    def _kopyala(self):
        QGuiApplication.clipboard().setText(self.kutu.toPlainText())
        self.kopyala.setText("Kopyalandı ✔")


class OcrArayuzu:
    def _ocr_kur(self):
        self.m_ocr = QMenu("&OCR", self)
        self.menuBar().insertMenu(self.m_sayfa.menuAction(), self.m_ocr)
        self.e_aranabilir = self._eylem("Aranabilir PDF Yap…", self.aranabilir_yap_ac, simge="ara")
        e = self._eylem("Bölgeden Metin Çıkar", self._arac_uygula, simge="metin", isaretli=False)
        self._arac_grubu.addAction(e)
        self._arac_eylemleri["ocr_bolge"] = e
        self._ek_ipuclari = {**getattr(self, "_ek_ipuclari", {}), **IPUCLARI}
        self.m_ocr.addAction(self.e_aranabilir)
        self.m_ocr.addAction(e)
        self._belge_eylemleri += [self.e_aranabilir, e]

    def _ocr_hazir_mi(self) -> bool:
        if dil_secenekleri():
            return True
        QMessageBox.warning(
            self, APP_NAME, "OCR için dil verisi bulunamadı.\n`tur.traineddata` (ve `eng.traineddata`) dosyalarını şu klasöre koyun:\n"
                            f"{ocr.kullanici_tessdata()}\n\nAyrıntı için Yardım → Nasıl Kullanılır → OCR.")
        return False

    def aranabilir_yap_ac(self):
        b = self.belge
        if not b or not self._ocr_hazir_mi():
            return
        d = AranabilirPenceresi(b.sayfa_sayisi, len(b.metinsiz_sayfalar()), self, str(self.ayarlar.value("ocr_dil", "")))
        if not d.exec():
            return
        sayfalar = d.secili_sayfalar()
        ilerleme = QProgressDialog("Sayfalar taranıyor…", "İptal", 0, 100, self)
        ilerleme.setWindowTitle("OCR")
        ilerleme.setMinimumDuration(0)
        ilerleme.setAutoClose(False)
        ilerleme.setAutoReset(False)

        def geri_bildirim(n: int, toplam: int) -> bool:
            ilerleme.setLabelText(f"Sayfalar taranıyor… ({min(n + 1, toplam)}/{toplam})")
            ilerleme.setValue(int(100 * n / max(toplam, 1)))
            QApplication.processEvents()
            return ilerleme.wasCanceled()

        sonuc = []
        try:
            ok = self._dene(lambda: sonuc.append(b.aranabilir_yap(sayfalar, d.secili_dil(), ilerleme=geri_bildirim)),
                            sayfalar or list(range(b.sayfa_sayisi)))
        except ocr.OcrIptal:
            ok = False
            self.statusBar().showMessage("OCR iptal edildi; belge değişmedi.", 5000)
        finally:
            ilerleme.close()
        if ok and sonuc:
            self._ocr_ozeti(sonuc[0])

    def _ocr_ozeti(self, s: ocr.OcrSonucu):
        parcalar = [f"{s.islenen} sayfa işlendi ({s.kelime} kelime)"]
        if s.atlanan_metinli:
            parcalar.append(f"{s.atlanan_metinli} sayfa zaten metin içerdiği için atlandı")
        if s.atlanan_dondurulmus:
            parcalar.append(f"{s.atlanan_dondurulmus} döndürülmüş sayfa atlandı (önce döndürmeyi düzeltip dışa aktarın)")
        self.statusBar().showMessage("; ".join(parcalar) + ".", 8000)

    # --- görüntüleyiciden gelen eylem ---
    def _ocr_eylemi(self, arac: str, sayfa: int, veri) -> bool:
        if arac != "ocr_bolge":
            return False
        if not self._ocr_hazir_mi():
            return True
        p1, p2 = veri
        rect = (min(p1[0], p2[0]), min(p1[1], p2[1]), max(p1[0], p2[0]), max(p1[1], p2[1]))
        kodlar = [k for k, _ in dil_secenekleri()]
        dil = str(self.ayarlar.value("ocr_dil", "")) if str(self.ayarlar.value("ocr_dil", "")) in kodlar else kodlar[0]
        QApplication.setOverrideCursor(self.cursor())
        try:
            metin = self.belge.bolgeden_metin(sayfa, rect, dil)
        except BelgeHatasi as h:
            QMessageBox.warning(self, APP_NAME, str(h))
            return True
        finally:
            QApplication.restoreOverrideCursor()
        if not metin:
            self.statusBar().showMessage("Seçilen alanda metin bulunamadı.", 5000)
        else:
            OcrMetinPenceresi(metin, self).exec()
        return True
