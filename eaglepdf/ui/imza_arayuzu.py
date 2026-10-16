"""Ana pencerenin Faz 5 dijital imza bölümü (Koruma menüsüne eklenir): sertifikayla imzala, imzaları doğrula,
boş imza alanı ekle, sertifika oluştur.

`AnaPencere`ye karışım olarak eklenir; `belge`, `ayarlar`, `m_koruma`, `_eylem`, `_belge_eylemleri`, `ac` üyelerini kullanır.
"""

from pathlib import Path

from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
                               QLineEdit, QMessageBox, QPushButton, QVBoxLayout)

from .. import APP_NAME
from ..core import dijital_imza as di
from ..core.belge import BelgeHatasi
from .koruma_arayuzu import PDF_FILTRESI

PFX_FILTRESI = "Sertifika dosyaları (*.pfx *.p12)"


def _hata_etiketi() -> QLabel:
    e = QLabel()
    e.setWordWrap(True)
    e.setStyleSheet("color:#c62828")
    return e


def _dugmeler(ok: str, dlg: QDialog, onayla) -> QDialogButtonBox:
    d = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    d.button(QDialogButtonBox.Ok).setText(ok)
    d.button(QDialogButtonBox.Cancel).setText("Vazgeç")
    d.accepted.connect(onayla)
    d.rejected.connect(dlg.reject)
    return d


class ImzalaPenceresi(QDialog):
    def __init__(self, sayfa_sayisi: int, pfx_yolu: str = "", bos_alanlar: list[str] | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Dijital İmzala")
        self.setMinimumWidth(460)
        self._sayfa_sayisi = sayfa_sayisi
        yerlesim = QVBoxLayout(self)
        yerlesim.addWidget(QLabel("Belge sertifikanızla imzalanır ve yeni bir dosya olarak kaydedilir. İmzadan sonra belgeyi "
                                  "değiştirmek imzayı geçersiz kılar."))
        form = QFormLayout()
        satir = QHBoxLayout()
        self.pfx = QLineEdit(pfx_yolu)
        goz = QPushButton("Seç…")
        goz.clicked.connect(self._sec)
        satir.addWidget(self.pfx)
        satir.addWidget(goz)
        form.addRow("Sertifika (.pfx):", satir)
        self.parola = QLineEdit(echoMode=QLineEdit.Password)
        form.addRow("Sertifika parolası:", self.parola)
        self.alan = QComboBox()
        self.alan.addItem("Yeni imza (konumu aşağıdan seçin)", "")
        for ad in bos_alanlar or []:
            self.alan.addItem(f"Mevcut boş alan: {ad}", ad)
        form.addRow("İmza alanı:", self.alan)
        self.konum = QComboBox()
        self.konum.addItem("Görünmez imza", None)
        for kod, ad in di.KONUM_ADLARI.items():
            self.konum.addItem(f"Görünür — {ad}", kod)
        self.konum.setCurrentIndex(1)
        form.addRow("Konum:", self.konum)
        self.sayfa = QLineEdit("1")
        form.addRow(f"Sayfa (1–{sayfa_sayisi}):", self.sayfa)
        self.neden = QLineEdit()
        self.neden.setPlaceholderText("örn. Onayladım")
        self.yer = QLineEdit()
        form.addRow("Neden (isteğe bağlı):", self.neden)
        form.addRow("Yer (isteğe bağlı):", self.yer)
        yerlesim.addLayout(form)
        self.hata = _hata_etiketi()
        yerlesim.addWidget(self.hata)
        yerlesim.addWidget(_dugmeler("İmzala…", self, self._onayla))
        self.alan.currentIndexChanged.connect(lambda: (self.konum.setEnabled(not self.alan.currentData()),
                                                       self.sayfa.setEnabled(not self.alan.currentData())))

    def _sec(self):
        yol, _ = QFileDialog.getOpenFileName(self, "Sertifika Seç", self.pfx.text(), PFX_FILTRESI)
        if yol:
            self.pfx.setText(yol)

    def _onayla(self):
        try:
            bilgi = di.sertifika_bilgisi(self.pfx.text().strip(), self.parola.text())
            if not self.alan.currentData() and not 1 <= int(self.sayfa.text() or 0) <= self._sayfa_sayisi:
                raise BelgeHatasi(f"Sayfa 1–{self._sayfa_sayisi} arasında olmalı.")
        except ValueError:
            self.hata.setText("Sayfa numarası geçersiz.")
            return
        except BelgeHatasi as h:
            self.hata.setText(str(h))
            return
        if bilgi.suresi_dolmus:
            self.hata.setText(f"Bu sertifikanın süresi {bilgi.bitis:%d.%m.%Y} tarihinde dolmuş.")
            return
        self.accept()

    def degerler(self) -> dict:
        alan = self.alan.currentData() or None
        return {"pfx_yolu": self.pfx.text().strip(), "parola": self.parola.text(), "alan_adi": alan,
                "sayfa": int(self.sayfa.text() or 1) - 1 if not alan else 0,
                "konum": None if alan else self.konum.currentData(), "neden": self.neden.text().strip(),
                "yer": self.yer.text().strip()}


class SertifikaOlusturPenceresi(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sertifika Oluştur")
        self.setMinimumWidth(440)
        yerlesim = QVBoxLayout(self)
        yerlesim.addWidget(QLabel(
            "Kendi adınıza bir imza sertifikası (.pfx) oluşturur. Bu sertifikaya başka bilgisayarlar güvenmez: "
            "imzanın bozulmadığı doğrulanır, ancak kimliğiniz doğrulanmış sayılmaz. Resmî geçerlilik için bir sertifika "
            "otoritesinin sertifikasını kullanın."))
        form = QFormLayout()
        self.ad = QLineEdit()
        self.eposta = QLineEdit()
        self.parola = QLineEdit(echoMode=QLineEdit.Password)
        self.parola2 = QLineEdit(echoMode=QLineEdit.Password)
        form.addRow("Ad Soyad:", self.ad)
        form.addRow("E-posta (isteğe bağlı):", self.eposta)
        form.addRow("Parola:", self.parola)
        form.addRow("Parola (tekrar):", self.parola2)
        yerlesim.addLayout(form)
        self.hata = _hata_etiketi()
        yerlesim.addWidget(self.hata)
        yerlesim.addWidget(_dugmeler("Oluştur…", self, self._onayla))

    def _onayla(self):
        if not self.ad.text().strip():
            self.hata.setText("Adınızı girin.")
        elif not self.parola.text():
            self.hata.setText("Bir parola girin; unutursanız sertifika kurtarılamaz.")
        elif self.parola.text() != self.parola2.text():
            self.hata.setText("Parola iki kutuda aynı değil.")
        else:
            self.accept()


class BosAlanPenceresi(QDialog):
    def __init__(self, sayfa_sayisi: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("İmza Alanı Ekle")
        self._sayfa_sayisi = sayfa_sayisi
        yerlesim = QVBoxLayout(self)
        yerlesim.addWidget(QLabel("Boş bir imza alanı eklenir; belgeyi alan kişi sonra imzalayabilir."))
        form = QFormLayout()
        self.ad = QLineEdit()
        self.ad.setPlaceholderText("örn. Yonetici (boşsa otomatik)")
        self.konum = QComboBox()
        for kod, ad in di.KONUM_ADLARI.items():
            self.konum.addItem(ad, kod)
        self.sayfa = QLineEdit("1")
        form.addRow("Alan adı:", self.ad)
        form.addRow("Konum:", self.konum)
        form.addRow(f"Sayfa (1–{sayfa_sayisi}):", self.sayfa)
        yerlesim.addLayout(form)
        self.hata = _hata_etiketi()
        yerlesim.addWidget(self.hata)
        yerlesim.addWidget(_dugmeler("Kaydet…", self, self._onayla))

    def _onayla(self):
        try:
            ok = 1 <= int(self.sayfa.text()) <= self._sayfa_sayisi
        except ValueError:
            ok = False
        if ok:
            self.accept()
        else:
            self.hata.setText(f"Sayfa 1–{self._sayfa_sayisi} arasında olmalı.")

    def degerler(self) -> dict:
        return {"sayfa": int(self.sayfa.text()) - 1, "konum": self.konum.currentData(), "alan_adi": self.ad.text().strip()}


class ImzaArayuzu:
    def _imza_kur(self):
        m = self.m_koruma
        m.addSeparator()
        self.e_imzala = self._eylem("Dijital İmzala…", self.dijital_imzala, simge="imza")
        self.e_imza_dogrula = self._eylem("İmzaları Doğrula…", self.imzalari_dogrula)
        self.e_imza_alani = self._eylem("Boş İmza Alanı Ekle…", self.imza_alani_ekle)
        self.e_sertifika = self._eylem("Sertifika Oluştur…", self.sertifika_olustur)
        for e in (self.e_imzala, self.e_imza_dogrula, self.e_imza_alani):
            m.addAction(e)
        m.addSeparator()
        m.addAction(self.e_sertifika)
        self._belge_eylemleri += [self.e_imzala, self.e_imza_dogrula, self.e_imza_alani]

    # --- ortak ---
    def _imza_kayit_yolu(self, baslik: str, sonek: str) -> Path | None:
        b = self.belge
        varsayilan = Path(self.ayarlar.value("son_klasor", "")) / ((b.yol.stem if b.yol else "Adsız") + sonek)
        yol, _ = QFileDialog.getSaveFileName(self, baslik, str(varsayilan) + ".pdf", PDF_FILTRESI)
        return Path(yol if yol.lower().endswith(".pdf") else yol + ".pdf") if yol else None

    def _imza_icin_uygun_mu(self) -> bool:
        """İmzalı belge değiştirilmişse yeni imza eklenemez (PyMuPDF yeniden yazımı eski imzayı bozardı)."""
        if self.belge.degisti and di.imzali_mi(self.belge):
            QMessageBox.information(self, APP_NAME, "Bu belge imzalı ve değiştirilmiş. Yeni imza eklemeden önce değişiklikleri "
                                                    "geri alın; imzalı belge değiştirilirse mevcut imzalar geçersiz olur.")
            return False
        return True

    def _kopyayi_ac_sor(self, yol: Path, ileti: str):
        self.statusBar().showMessage(ileti, 8000)
        if QMessageBox.question(self, APP_NAME, f"{ileti}\n\nBu kopyayı şimdi açmak ister misiniz?",
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes) == QMessageBox.Yes:
            self.ac(str(yol))

    # --- eylemler ---
    def dijital_imzala(self):
        b = self.belge
        if not b or not self._imza_icin_uygun_mu():
            return
        try:
            bos = di.bos_imza_alanlari(b)
        except Exception:
            bos = []
        d = ImzalaPenceresi(b.sayfa_sayisi, str(self.ayarlar.value("pfx_yolu", "")), bos, self)
        if not d.exec():
            return
        v = d.degerler()
        yol = self._imza_kayit_yolu("İmzalı Kopyayı Kaydet", " (imzalı)")
        if not yol:
            return
        try:
            di.imzala(b, yol, **v)
        except (BelgeHatasi, OSError) as h:
            QMessageBox.warning(self, APP_NAME, f"İmzalanamadı:\n{h}")
            return
        self.ayarlar.setValue("pfx_yolu", v["pfx_yolu"])
        self._kopyayi_ac_sor(yol, f"İmzalı kopya kaydedildi: {yol}")

    def imzalari_dogrula(self):
        b = self.belge
        if not b:
            return
        try:
            durumlar = di.dogrula(b)
        except Exception as h:
            QMessageBox.warning(self, APP_NAME, f"İmzalar denetlenemedi:\n{h}")
            return
        if not durumlar:
            QMessageBox.information(self, "İmzaları Doğrula", "Bu belgede dijital imza yok.")
            return
        satirlar = []
        for s in durumlar:
            zaman = f" — {s.zaman:%d.%m.%Y %H:%M}" if s.zaman else ""
            satirlar.append(f"{'✔' if s.butunluk_tamam and not s.belge_sonradan_degisti else '✘'}  {s.alan}: {s.imzalayan}{zaman}\n"
                            f"     {s.ozet}" + "".join(f"\n     • {a}" for a in s.ayrinti))
        if b.degisti:
            satirlar.append("\nNot: Belgede kaydedilmemiş değişiklikler var; denetim şu anki içeriğe göre yapıldı.")
        QMessageBox.information(self, "İmzaları Doğrula", "\n\n".join(satirlar))

    def imza_alani_ekle(self):
        b = self.belge
        if not b or not self._imza_icin_uygun_mu():
            return
        d = BosAlanPenceresi(b.sayfa_sayisi, self)
        if not d.exec():
            return
        yol = self._imza_kayit_yolu("İmza Alanlı Kopyayı Kaydet", " (imza alanlı)")
        if not yol:
            return
        try:
            _, ad = di.bos_alan_ekle(b, yol, **d.degerler())
        except (BelgeHatasi, OSError) as h:
            QMessageBox.warning(self, APP_NAME, f"İmza alanı eklenemedi:\n{h}")
            return
        self._kopyayi_ac_sor(yol, f"“{ad}” imza alanı eklendi: {yol}")

    def sertifika_olustur(self):
        d = SertifikaOlusturPenceresi(self)
        if not d.exec():
            return
        yol, _ = QFileDialog.getSaveFileName(self, "Sertifikayı Kaydet", str(Path.home() / "imza-sertifikam.pfx"), PFX_FILTRESI)
        if not yol:
            return
        yol = yol if yol.lower().endswith((".pfx", ".p12")) else yol + ".pfx"
        try:
            di.sertifika_olustur(yol, d.ad.text(), d.parola.text(), d.eposta.text())
        except (BelgeHatasi, OSError) as h:
            QMessageBox.warning(self, APP_NAME, f"Sertifika oluşturulamadı:\n{h}")
            return
        self.ayarlar.setValue("pfx_yolu", yol)
        QMessageBox.information(self, APP_NAME, f"Sertifika kaydedildi:\n{yol}\n\nDosyayı ve parolasını güvenli saklayın. "
                                                "Dijital İmzala penceresinde otomatik seçilecektir.")

    # --- kayıt uyarısı ---
    def _imzali_kayit_onayi(self) -> bool:
        """Değiştirilmiş imzalı belgeyi kaydederken imzaların geçersiz olacağını söyler. False: vazgeçildi."""
        b = self.belge
        if not b or not b.degisti or not di.imzali_mi(b):
            return True
        return QMessageBox.warning(
            self, APP_NAME, "Bu belge dijital imzalı. Değişiklikleri kaydederseniz mevcut imzalar GEÇERSİZ olur.\n"
                            "Devam edilsin mi?", QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel) == QMessageBox.Yes
