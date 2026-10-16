"""Ana pencerenin Faz 5 koruma bölümü: Koruma menüsü (parola ekle, parolayı kaldır, izinler).

`AnaPencere`ye karışım olarak eklenir; `belge`, `ayarlar`, `m_sayfa`, `_eylem`, `_kayitli_pdf_yolu` üyelerini kullanır.
"""

from pathlib import Path

from PySide6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QGroupBox, QLabel,
                               QLineEdit, QMenu, QMessageBox, QVBoxLayout)

from .. import APP_NAME
from ..core import koruma
from ..core.belge import BelgeHatasi

IZIN_ADLARI = (("yazdir", "Yazdırma"), ("yuksek_kalite_yazdir", "Yüksek kalitede yazdırma"), ("kopyala", "Metin ve resim kopyalama"),
               ("duzenle", "İçeriği düzenleme"), ("aciklama", "Açıklama ekleme"), ("form", "Form doldurma"),
               ("sayfa_duzenle", "Sayfa ekleme/silme/döndürme"), ("erisilebilirlik", "Erişilebilirlik (ekran okuyucu)"))
PDF_FILTRESI = "PDF Belgeleri (*.pdf)"


class ParolaEkleDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Parola Ekle")
        self.setMinimumWidth(420)
        yerlesim = QVBoxLayout(self)
        yerlesim.addWidget(QLabel("Belge AES-256 ile korunur. İki parolayı birlikte ya da yalnızca birini verebilirsiniz.\n"
                                  "Parolayı unutursanız belge kurtarılamaz."))
        form = QFormLayout()
        self.acma = QLineEdit(echoMode=QLineEdit.Password)
        self.acma2 = QLineEdit(echoMode=QLineEdit.Password)
        self.sahip = QLineEdit(echoMode=QLineEdit.Password)
        form.addRow("Açma parolası:", self.acma)
        form.addRow("Açma parolası (tekrar):", self.acma2)
        form.addRow("Sahip parolası:", self.sahip)
        yerlesim.addLayout(form)
        yerlesim.addWidget(QLabel("Açma parolası belgeyi açmak için sorulur. Sahip parolası, aşağıdaki kısıtlamaları kaldırmak içindir "
                                  "(boşsa açma parolası kullanılır)."))
        kutu = QGroupBox("İzin verilenler")
        kl = QVBoxLayout(kutu)
        self.izin_kutulari = {}
        for kimlik, ad in IZIN_ADLARI:
            c = QCheckBox(ad)
            c.setChecked(True)
            self.izin_kutulari[kimlik] = c
            kl.addWidget(c)
        yerlesim.addWidget(kutu)
        self.hata = QLabel()
        self.hata.setStyleSheet("color:#c62828")
        yerlesim.addWidget(self.hata)
        dugmeler = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        dugmeler.button(QDialogButtonBox.Ok).setText("Kaydet…")
        dugmeler.button(QDialogButtonBox.Cancel).setText("Vazgeç")
        dugmeler.accepted.connect(self._onayla)
        dugmeler.rejected.connect(self.reject)
        yerlesim.addWidget(dugmeler)

    def _onayla(self):
        if not self.acma.text() and not self.sahip.text():
            self.hata.setText("En az bir parola girin.")
        elif self.acma.text() != self.acma2.text():
            self.hata.setText("Açma parolası iki kutuda aynı değil.")
        else:
            self.accept()

    def degerler(self) -> dict:
        return {"acma_parolasi": self.acma.text(), "sahip_parolasi": self.sahip.text(),
                "izinler": {k: c.isChecked() for k, c in self.izin_kutulari.items()}}


class KorumaArayuzu:
    def _koruma_kur(self):
        self.m_koruma = QMenu("&Koruma", self)
        self.menuBar().insertMenu(self.m_sayfa.menuAction(), self.m_koruma)
        self.e_parola_ekle = self._eylem("Parola Ekle…", self.parola_ekle, simge="kilit")
        self.e_parola_kaldir = self._eylem("Parolayı Kaldır…", self.parola_kaldir)
        self.e_izinler = self._eylem("Belge İzinleri…", self.izinleri_goster)
        for e in (self.e_parola_ekle, self.e_parola_kaldir, self.e_izinler):
            self.m_koruma.addAction(e)
        self._belge_eylemleri += [self.e_parola_ekle, self.e_parola_kaldir, self.e_izinler]

    def _koruma_kayit_yolu(self, baslik: str, sonek: str) -> Path | None:
        varsayilan = Path(self.ayarlar.value("son_klasor", ""))
        varsayilan /= (self.belge.yol.stem + sonek) if self.belge.yol else ("Adsız" + sonek)
        yol, _ = QFileDialog.getSaveFileName(self, baslik, str(varsayilan) + ".pdf", PDF_FILTRESI)
        if not yol:
            return None
        return Path(yol if yol.lower().endswith(".pdf") else yol + ".pdf")

    def parola_ekle(self):
        if not self.belge:
            return
        d = ParolaEkleDialog(self)
        if not d.exec():
            return
        yol = self._koruma_kayit_yolu("Korumalı Kopyayı Kaydet", " (korumalı)")
        if not yol:
            return
        try:
            koruma.parola_ekle(self.belge, yol, **d.degerler())
        except (BelgeHatasi, OSError) as h:
            QMessageBox.warning(self, APP_NAME, f"Korumalı kopya yazılamadı:\n{h}")
            return
        self.statusBar().showMessage(f"Korumalı kopya kaydedildi: {yol}", 6000)

    def parola_kaldir(self):
        if not self.belge:
            return
        if not koruma.sifreli_mi(self.belge):
            QMessageBox.information(self, APP_NAME, "Bu belge zaten parolasız.")
            return
        yol = self._koruma_kayit_yolu("Parolasız Kopyayı Kaydet", " (parolasız)")
        if not yol:
            return
        try:
            koruma.parola_kaldir(self.belge, yol)
        except (BelgeHatasi, OSError) as h:
            QMessageBox.warning(self, APP_NAME, f"Parolasız kopya yazılamadı:\n{h}")
            return
        self.statusBar().showMessage(f"Parolasız kopya kaydedildi: {yol}", 6000)

    def izinleri_goster(self):
        if not self.belge:
            return
        izin = koruma.mevcut_izinler(self.belge)
        if not koruma.sifreli_mi(self.belge):
            QMessageBox.information(self, APP_NAME, "Bu belge korumalı değil; tüm işlemlere izin var.")
            return
        satirlar = [f"{'✔' if izin[k] else '✘'}  {ad}" for k, ad in IZIN_ADLARI]
        QMessageBox.information(self, "Belge İzinleri", "Bu belge parolayla korunuyor.\n\n" + "\n".join(satirlar))
