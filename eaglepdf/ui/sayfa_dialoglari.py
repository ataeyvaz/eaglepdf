"""Birleştir ve Böl pencereleri."""

from PySide6.QtWidgets import (
    QButtonGroup, QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QPushButton, QRadioButton, QSpinBox, QVBoxLayout,
)

from ..core.belge import BelgeHatasi, aralik_coz


def _tamam_vazgec(tamam_metni: str) -> QDialogButtonBox:
    kutu = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    kutu.button(QDialogButtonBox.Ok).setText(tamam_metni)
    kutu.button(QDialogButtonBox.Cancel).setText("Vazgeç")
    return kutu


class BirlestirPenceresi(QDialog):
    def __init__(self, parent=None, baslangic: list[str] | None = None, klasor: str = ""):
        super().__init__(parent)
        self.setWindowTitle("PDF Birleştir")
        self.resize(520, 360)
        self._klasor = klasor
        duzen = QVBoxLayout(self)
        duzen.addWidget(QLabel("Birleştirilecek PDF dosyaları (yukarıdan aşağıya sırayla):"))
        self.liste = QListWidget()
        self.liste.setDragDropMode(QListWidget.InternalMove)
        duzen.addWidget(self.liste, 1)
        for yol in baslangic or []:
            self.liste.addItem(yol)
        dugmeler = QHBoxLayout()
        for ad, fn in (("Ekle…", self._ekle), ("Kaldır", self._kaldir), ("Yukarı", lambda: self._tasi(-1)),
                       ("Aşağı", lambda: self._tasi(1))):
            d = QPushButton(ad)
            d.setAutoDefault(False)
            d.clicked.connect(fn)
            dugmeler.addWidget(d)
        dugmeler.addStretch()
        duzen.addLayout(dugmeler)
        kutu = _tamam_vazgec("Birleştir…")
        kutu.accepted.connect(self.accept)
        kutu.rejected.connect(self.reject)
        duzen.addWidget(kutu)

    def _ekle(self):
        yollar, _ = QFileDialog.getOpenFileNames(self, "PDF Ekle", self._klasor, "PDF belgeleri (*.pdf)")
        for y in yollar:
            self.liste.addItem(y)

    def _kaldir(self):
        for o in self.liste.selectedItems():
            self.liste.takeItem(self.liste.row(o))

    def _tasi(self, yon: int):
        r = self.liste.currentRow()
        h = r + yon
        if r < 0 or not 0 <= h < self.liste.count():
            return
        o = self.liste.takeItem(r)
        self.liste.insertItem(h, o)
        self.liste.setCurrentRow(h)

    def yollar(self) -> list[str]:
        return [self.liste.item(i).text() for i in range(self.liste.count())]


class BolPenceresi(QDialog):
    def __init__(self, sayfa_sayisi: int, parent=None):
        super().__init__(parent)
        self.sayfa_sayisi = sayfa_sayisi
        self.parcalar: list[list[int]] | None = None
        self.setWindowTitle("PDF Böl")
        duzen = QVBoxLayout(self)
        duzen.addWidget(QLabel(f"Belge {sayfa_sayisi} sayfa."))
        self.her_n = QRadioButton("Her")
        self.n_kutu = QSpinBox()
        self.n_kutu.setRange(1, max(sayfa_sayisi, 1))
        self.n_kutu.setValue(1)
        satir = QHBoxLayout()
        satir.addWidget(self.her_n)
        satir.addWidget(self.n_kutu)
        satir.addWidget(QLabel("sayfada bir dosya"))
        satir.addStretch()
        duzen.addLayout(satir)
        self.aralik = QRadioButton("Şu aralıklara göre (her parça ayrı dosya; parçaları “;” ile ayırın):")
        duzen.addWidget(self.aralik)
        self.aralik_kutu = QLineEdit()
        self.aralik_kutu.setPlaceholderText("örn. 1-3; 4-6; 7-")
        duzen.addWidget(self.aralik_kutu)
        grup = QButtonGroup(self)
        grup.addButton(self.her_n)
        grup.addButton(self.aralik)
        self.her_n.setChecked(True)
        self.hata = QLabel()
        self.hata.setStyleSheet("color: #c62828;")
        duzen.addWidget(self.hata)
        kutu = _tamam_vazgec("Böl…")
        kutu.accepted.connect(self._tamam)
        kutu.rejected.connect(self.reject)
        duzen.addWidget(kutu)

    def _tamam(self):
        try:
            if self.her_n.isChecked():
                n = self.n_kutu.value()
                self.parcalar = [list(range(i, min(i + n, self.sayfa_sayisi))) for i in range(0, self.sayfa_sayisi, n)]
            else:
                self.parcalar = [aralik_coz(p, self.sayfa_sayisi) for p in self.aralik_kutu.text().split(";") if p.strip()]
                if not self.parcalar:
                    raise BelgeHatasi("Sayfa aralığı boş.")
        except BelgeHatasi as h:
            self.hata.setText(str(h))
            return
        self.accept()
