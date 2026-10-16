"""Belge Özellikleri penceresi: başlık/yazar/konu/anahtar sözcükler düzenlenir, diğer bilgiler salt okunur."""

from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
                               QVBoxLayout)

from .. import APP_NAME

DUZENLENEN = (("baslik", "Başlık", "Başlık"), ("yazar", "Yazar", "Yazar"), ("konu", "Konu", "Konu"),
              ("anahtar", "Anahtar sözcükler", "Anahtar sözcükler"))
SALT_OKUNUR = ("Oluşturan", "Üretici", "Oluşturma tarihi", "Değiştirme tarihi", "Sayfa sayısı", "Dosya boyutu")


class OzelliklerPenceresi(QDialog):
    def __init__(self, ozellikler: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Belge Özellikleri")
        self.setMinimumWidth(460)
        self.temizle_istendi = False
        yerlesim = QVBoxLayout(self)
        form = QFormLayout()
        self.alanlar: dict[str, QLineEdit] = {}
        self._ilk: dict[str, str] = {}
        for kimlik, etiket, anahtar in DUZENLENEN:
            kutu = QLineEdit(ozellikler.get(anahtar, ""))
            self.alanlar[kimlik] = kutu
            self._ilk[kimlik] = kutu.text()
            form.addRow(f"{etiket}:", kutu)
        for ad in SALT_OKUNUR:
            if ozellikler.get(ad):
                deger = QLabel(ozellikler[ad])
                deger.setTextInteractionFlags(deger.textInteractionFlags() | deger.textInteractionFlags().TextSelectableByMouse)
                form.addRow(f"{ad}:", deger)
        yerlesim.addLayout(form)
        self.temizle = QPushButton("Tüm bilgileri temizle (gizlilik)…")
        self.temizle.setToolTip("Başlık, yazar, tarihler, üretici ve XMP üst verisi silinir.")
        self.temizle.clicked.connect(self._temizle_sor)
        yerlesim.addWidget(self.temizle)
        dugmeler = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        dugmeler.button(QDialogButtonBox.Ok).setText("Tamam")
        dugmeler.button(QDialogButtonBox.Cancel).setText("Vazgeç")
        dugmeler.accepted.connect(self.accept)
        dugmeler.rejected.connect(self.reject)
        yerlesim.addWidget(dugmeler)

    def _temizle_sor(self):
        if QMessageBox.question(self, APP_NAME, "Belgedeki tüm üst veri (başlık, yazar, tarihler, üretici…) silinsin mi?\n"
                                "Geri Al ile döndürebilirsiniz.", QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes:
            self.temizle_istendi = True
            for k in self.alanlar.values():
                k.clear()
            self.accept()

    def degisenler(self) -> dict[str, str]:
        """Yalnızca değiştirilen alanlar (kimlik → yeni metin)."""
        return {k: v.text() for k, v in self.alanlar.items() if v.text().strip() != self._ilk[k].strip()}
