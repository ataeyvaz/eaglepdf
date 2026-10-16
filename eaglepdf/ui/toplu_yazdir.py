"""Toplu yazdırma: dosya listesini tek yazıcı ayarıyla sırayla yazdırır (her dosya ayrı yazdırma işi)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtWidgets import (QAbstractItemView, QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
                               QListWidget, QPushButton, QVBoxLayout)

from ..core.belge import Belge, BelgeHatasi, ParolaGerekli, aralik_coz
from .yazdir import sayfalari_yazdir

PDF_FILTRESI = "PDF Belgeleri (*.pdf)"


@dataclass
class DosyaSonucu:
    yol: str
    sayfa: int = 0
    hata: str = ""

    @property
    def tamam(self) -> bool:
        return not self.hata


def toplu_yazdir(yollar: list[str], yazici, aralik: str = "", parola_sor=None, ilerleme=None,
                 her_dosya_icin=None) -> list[DosyaSonucu]:
    """Dosyaları sırayla yazdırır; bir dosyadaki hata diğerlerini durdurmaz.
    `aralik`: boşsa tüm sayfalar, yoksa her dosyaya uygulanan aralık ("1-2, 5"); dosyada olmayan sayfalar yazılmaz.
    `parola_sor(yol)`: parolalı dosya için parola (None/"" = atla). `ilerleme(n, toplam)` True dönerse iptal.
    `her_dosya_icin(yazici, yol)`: her işten önce çağrılır (belge adı vb.)."""
    sonuclar: list[DosyaSonucu] = []
    for n, yol in enumerate(yollar):
        if ilerleme and ilerleme(n, len(yollar)):
            break
        s = DosyaSonucu(str(yol))
        sonuclar.append(s)
        try:
            belge = _ac(yol, parola_sor)
        except BelgeHatasi as h:
            s.hata = str(h)
            continue
        try:
            if aralik.strip():
                tum = belge.sayfa_sayisi
                ilk = [i for i in _aralik_guvenli(aralik) if i < tum]
                if not ilk:
                    s.hata = f"Sayfa aralığı bu belgede yok (belge {tum} sayfa)."
                    continue
                sayfalar = ilk
            else:
                sayfalar = list(range(belge.sayfa_sayisi))
            yazici.setDocName(Path(yol).name)
            if her_dosya_icin:
                her_dosya_icin(yazici, str(yol))
            s.sayfa = sayfalari_yazdir(belge, yazici, sayfalar)
        except (OSError, BelgeHatasi) as h:
            s.hata = str(h)
        finally:
            belge.kapat()
    if ilerleme:
        ilerleme(len(yollar), len(yollar))
    return sonuclar


def _aralik_guvenli(metin: str) -> list[int]:
    """`aralik_coz` belge sayfa sayısına bağlıdır; burada üst sınır yok sayılır, sonra dosyaya göre süzülür."""
    return aralik_coz(metin, 100000)


def _ac(yol, parola_sor) -> Belge:
    try:
        return Belge.ac(yol)
    except ParolaGerekli:
        parola = parola_sor(str(yol)) if parola_sor else None
        if not parola:
            raise BelgeHatasi("Parolalı belge; parola girilmediği için atlandı.") from None
        return Belge.ac(yol, parola)


class TopluYazdirPenceresi(QDialog):
    """Dosya listesini ve sayfa aralığını toplar; yazıcı seçimi ve yazdırma ana pencerede yapılır."""

    def __init__(self, baslangic_klasoru: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Toplu Yazdır")
        self.setMinimumSize(520, 380)
        self._klasor = baslangic_klasoru
        yerlesim = QVBoxLayout(self)
        yerlesim.addWidget(QLabel("Yazdırılacak PDF dosyalarını ekleyin; sürükleyerek sırayı değiştirebilirsiniz. "
                                  "Yazıcı ayarını bir kez seçersiniz, hepsine uygulanır."))
        self.liste = QListWidget()
        self.liste.setDragDropMode(QAbstractItemView.InternalMove)
        self.liste.setSelectionMode(QAbstractItemView.ExtendedSelection)
        yerlesim.addWidget(self.liste)
        satir = QHBoxLayout()
        ekle = QPushButton("Dosya Ekle…")
        ekle.clicked.connect(self._ekle)
        self.kaldir = QPushButton("Seçilileri Kaldır")
        self.kaldir.clicked.connect(self._kaldir)
        satir.addWidget(ekle)
        satir.addWidget(self.kaldir)
        satir.addStretch()
        yerlesim.addLayout(satir)
        aralik = QHBoxLayout()
        aralik.addWidget(QLabel("Sayfa aralığı (her dosyaya):"))
        self.aralik = QLineEdit()
        self.aralik.setPlaceholderText("Boş = tüm sayfalar (örn. 1-2, 5)")
        aralik.addWidget(self.aralik)
        yerlesim.addLayout(aralik)
        self.hata = QLabel()
        self.hata.setStyleSheet("color:#c62828")
        yerlesim.addWidget(self.hata)
        dugmeler = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        dugmeler.button(QDialogButtonBox.Ok).setText("Yazıcı Seç ve Yazdır…")
        dugmeler.button(QDialogButtonBox.Cancel).setText("Vazgeç")
        dugmeler.accepted.connect(self._onayla)
        dugmeler.rejected.connect(self.reject)
        yerlesim.addWidget(dugmeler)

    def dosya_ekle(self, yollar):
        var = set(self.yollar())
        for y in yollar:
            if str(y) not in var:
                self.liste.addItem(str(y))
                var.add(str(y))

    def _ekle(self):
        yollar, _ = QFileDialog.getOpenFileNames(self, "Yazdırılacak PDF'ler", self._klasor, PDF_FILTRESI)
        if yollar:
            self._klasor = str(Path(yollar[0]).parent)
            self.dosya_ekle(yollar)

    def _kaldir(self):
        for oge in self.liste.selectedItems():
            self.liste.takeItem(self.liste.row(oge))

    def yollar(self) -> list[str]:
        return [self.liste.item(i).text() for i in range(self.liste.count())]

    def _onayla(self):
        if not self.yollar():
            self.hata.setText("Önce yazdırılacak dosyaları ekleyin.")
            return
        try:
            if self.aralik.text().strip():
                _aralik_guvenli(self.aralik.text())
        except BelgeHatasi as h:
            self.hata.setText(str(h))
            return
        self.accept()
