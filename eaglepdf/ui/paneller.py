"""Sol paneller: küçük resimler (sürükle-bırak sıralama, çoklu seçim), yer imleri (düzenlenebilir) ve açıklamalar."""

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QHBoxLayout, QInputDialog, QLabel, QListView, QListWidget, QListWidgetItem,
    QPushButton, QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from ..core.belge import Belge
from .goruntuleyici import pixmap_den

KUCUK_GENISLIK = 120


class KucukResimler(QListWidget):
    sayfaSecildi = Signal(int)
    siraDegisti = Signal(list)  # yeni sıra: eski indekslerin listesi

    def __init__(self, parent=None):
        super().__init__(parent)
        self.belge: Belge | None = None
        self._bekleyen: list[int] = []
        self.setViewMode(QListView.IconMode)
        self.setFlow(QListView.TopToBottom)
        self.setWrapping(False)
        self.setMovement(QListView.Snap)
        self.setResizeMode(QListView.Adjust)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setSpacing(6)
        self.setIconSize(QSize(KUCUK_GENISLIK, round(KUCUK_GENISLIK * 1.42)))
        self._zaman = QTimer(self, interval=15)
        self._zaman.timeout.connect(self._sonrakini_ciz)
        self._sira_kilit = False
        self.currentRowChanged.connect(self._satir)
        self.model().rowsMoved.connect(self._tasindi)

    def belge_ata(self, belge: Belge | None):
        self.belge = belge
        self._sira_kilit = True
        self.clear()
        self._zaman.stop()
        if belge:
            for i in range(belge.sayfa_sayisi):
                g, y = belge.sayfa_boyutu(i)
                oran = y / g if g else 1.42
                oge = QListWidgetItem(QIcon(), str(i + 1))
                oge.setData(Qt.UserRole, i)
                oge.setTextAlignment(Qt.AlignHCenter)
                oge.setSizeHint(QSize(KUCUK_GENISLIK + 16, round(KUCUK_GENISLIK * oran) + 34))
                self.addItem(oge)
            self._bekleyen = list(range(belge.sayfa_sayisi))
            self._zaman.start()
        self._sira_kilit = False

    def yenile(self, indeks: int):
        """Tek sayfanın küçük resmini yeniden çizdirir (içerik değişti, sıra/sayı aynı)."""
        if self.belge and 0 <= indeks < self.count() and indeks not in self._bekleyen:
            self._bekleyen.insert(0, indeks)
            self._zaman.start()

    def _sonrakini_ciz(self):
        for _ in range(3):
            if not self._bekleyen or not self.belge:
                self._zaman.stop()
                return
            i = self._bekleyen.pop(0)
            oge = self._oge_bul(i)
            if oge is None or i >= self.belge.sayfa_sayisi:
                continue
            g, _y = self.belge.sayfa_boyutu(i)
            oge.setIcon(QIcon(pixmap_den(self.belge.render(i, KUCUK_GENISLIK / g), 1.0)))

    def _oge_bul(self, indeks: int):
        for r in range(self.count()):
            if self.item(r).data(Qt.UserRole) == indeks:
                return self.item(r)
        return None

    def _satir(self, satir: int):
        if not self._sira_kilit and satir >= 0:
            self.sayfaSecildi.emit(satir)

    def secili_sayfalar(self) -> list[int]:
        return sorted(self.row(o) for o in self.selectedItems())

    def vurgula(self, indeks: int):
        """Görüntüleyicideki geçerli sayfayı (sinyal göndermeden) işaretler."""
        if not 0 <= indeks < self.count():
            return
        self._sira_kilit = True
        self.setCurrentRow(indeks)
        self.scrollToItem(self.item(indeks))
        self._sira_kilit = False

    def _tasindi(self, *_):
        if self._sira_kilit:
            return
        yeni = [self.item(r).data(Qt.UserRole) for r in range(self.count())]
        if yeni != list(range(len(yeni))):
            self.siraDegisti.emit(yeni)


class YerImleri(QWidget):
    """Yer imi ağacı + düzenleme düğmeleri. Her değişiklik `degisti(liste)` sinyaliyle bildirilir;
    liste: [(düzey 1'den, başlık, 0 tabanlı sayfa)]."""

    sayfaSecildi = Signal(int)
    degisti = Signal(list)

    def __init__(self, gecerli_sayfa=lambda: 0, parent=None):
        super().__init__(parent)
        self._gecerli_sayfa = gecerli_sayfa
        duzen = QVBoxLayout(self)
        duzen.setContentsMargins(0, 0, 0, 0)
        duzen.setSpacing(0)
        satir = QHBoxLayout()
        satir.setContentsMargins(4, 4, 4, 4)
        satir.setSpacing(2)
        self._dugmeler: list[QToolButton] = []
        for metin, ipucu, fn in (
            ("＋", "Geçerli sayfaya yer imi ekle", self._ekle), ("✎", "Yeniden adlandır", self._adlandir),
            ("🗑", "Sil", self._sil), ("⇤", "Düzeyi azalt", self._cikar), ("⇥", "Düzeyi artır", self._gir),
            ("▲", "Yukarı taşı", lambda: self._tasi(-1)), ("▼", "Aşağı taşı", lambda: self._tasi(1)),
        ):
            d = QToolButton()
            d.setText(metin)
            d.setToolTip(ipucu)
            d.clicked.connect(lambda _=False, f=fn: f())
            satir.addWidget(d)
            self._dugmeler.append(d)
        satir.addStretch()
        duzen.addLayout(satir)
        self.agac = QTreeWidget()
        self.agac.setHeaderHidden(True)
        self.agac.itemClicked.connect(lambda o, _: self.sayfaSecildi.emit(o.data(0, Qt.UserRole)))
        duzen.addWidget(self.agac, 1)
        self.etkin(False)

    def etkin(self, acik: bool):
        for d in self._dugmeler:
            d.setEnabled(acik)
        self.agac.setEnabled(acik)

    def belge_ata(self, belge: Belge | None):
        self.agac.clear()
        self.etkin(belge is not None)
        if not belge:
            return
        yigin: list[tuple[int, QTreeWidgetItem]] = []
        for duzey, baslik, sayfa in belge.icindekiler():
            oge = QTreeWidgetItem([baslik])
            oge.setData(0, Qt.UserRole, sayfa)
            while yigin and yigin[-1][0] >= duzey:
                yigin.pop()
            (yigin[-1][1].addChild if yigin else self.agac.addTopLevelItem)(oge)
            yigin.append((duzey, oge))
        self.agac.expandAll()

    def liste(self) -> list[tuple[int, str, int]]:
        sonuc = []

        def gez(oge: QTreeWidgetItem, duzey: int):
            sonuc.append((duzey, oge.text(0), oge.data(0, Qt.UserRole)))
            for i in range(oge.childCount()):
                gez(oge.child(i), duzey + 1)

        for i in range(self.agac.topLevelItemCount()):
            gez(self.agac.topLevelItem(i), 1)
        return sonuc

    def _bildir(self):
        self.degisti.emit(self.liste())

    def _secili(self):
        return self.agac.currentItem()

    def _kardesler(self, oge):
        ust = oge.parent()
        return (ust, ust.childCount()) if ust else (None, self.agac.topLevelItemCount())

    def _ekle(self):
        sayfa = self._gecerli_sayfa()
        baslik, tamam = QInputDialog.getText(self, "Yer İmi Ekle", "Başlık:", text=f"Sayfa {sayfa + 1}")
        if not tamam or not baslik.strip():
            return
        oge = QTreeWidgetItem([baslik.strip()])
        oge.setData(0, Qt.UserRole, sayfa)
        sec = self._secili()
        if sec and sec.parent():
            sec.parent().insertChild(sec.parent().indexOfChild(sec) + 1, oge)
        elif sec:
            self.agac.insertTopLevelItem(self.agac.indexOfTopLevelItem(sec) + 1, oge)
        else:
            self.agac.addTopLevelItem(oge)
        self.agac.setCurrentItem(oge)
        self._bildir()

    def _adlandir(self):
        oge = self._secili()
        if not oge:
            return
        baslik, tamam = QInputDialog.getText(self, "Yeniden Adlandır", "Başlık:", text=oge.text(0))
        if tamam and baslik.strip():
            oge.setText(0, baslik.strip())
            self._bildir()

    def _sil(self):
        oge = self._secili()
        if not oge:
            return
        (oge.parent() or self.agac.invisibleRootItem()).removeChild(oge)
        self._bildir()

    def _tasi(self, yon: int):
        oge = self._secili()
        if not oge:
            return
        ust = oge.parent() or self.agac.invisibleRootItem()
        i = ust.indexOfChild(oge)
        j = i + yon
        if not 0 <= j < ust.childCount():
            return
        ust.removeChild(oge)
        ust.insertChild(j, oge)
        self.agac.setCurrentItem(oge)
        oge.setExpanded(True)
        self._bildir()

    def _gir(self):
        """Önceki kardeşin altına alır (düzeyi artırır)."""
        oge = self._secili()
        if not oge:
            return
        ust = oge.parent() or self.agac.invisibleRootItem()
        i = ust.indexOfChild(oge)
        if i == 0:
            return
        onceki = ust.child(i - 1)
        ust.removeChild(oge)
        onceki.addChild(oge)
        onceki.setExpanded(True)
        self.agac.setCurrentItem(oge)
        self._bildir()

    def _cikar(self):
        """Üst öğenin kardeşi yapar (düzeyi azaltır)."""
        oge = self._secili()
        if not oge or not oge.parent():
            return
        ust = oge.parent()
        buyuk = ust.parent() or self.agac.invisibleRootItem()
        ust.removeChild(oge)
        buyuk.insertChild(buyuk.indexOfChild(ust) + 1, oge)
        self.agac.setCurrentItem(oge)
        self._bildir()


class AciklamaPaneli(QWidget):
    """Belgedeki ek açıklamaların listesi: türe/yazara göre süzme, gitme ve toplu silme."""

    ekSecildi = Signal(object)
    silmeIstendi = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tum: list = []
        duzen = QVBoxLayout(self)
        duzen.setContentsMargins(4, 4, 4, 4)
        suz = QHBoxLayout()
        self.tur_kutu = QComboBox()
        self.yazar_kutu = QComboBox()
        suz.addWidget(self.tur_kutu, 1)
        suz.addWidget(self.yazar_kutu, 1)
        duzen.addLayout(suz)
        self.agac = QTreeWidget()
        self.agac.setColumnCount(3)
        self.agac.setHeaderLabels(["Sayfa", "Tür", "Metin"])
        self.agac.setRootIsDecorated(False)
        self.agac.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.agac.setColumnWidth(0, 44)
        self.agac.setColumnWidth(1, 90)
        duzen.addWidget(self.agac, 1)
        alt = QHBoxLayout()
        self.sayac = QLabel("")
        self.sil_dugme = QPushButton("Seçilileri Sil")
        self.sil_dugme.setAutoDefault(False)
        alt.addWidget(self.sayac, 1)
        alt.addWidget(self.sil_dugme)
        duzen.addLayout(alt)
        self.tur_kutu.currentIndexChanged.connect(self._suz)
        self.yazar_kutu.currentIndexChanged.connect(self._suz)
        self.agac.itemClicked.connect(lambda o, _: self.ekSecildi.emit(o.data(0, Qt.UserRole)))
        self.sil_dugme.clicked.connect(self._sil)

    def doldur(self, liste: list):
        self._tum = liste
        for kutu, alan, hepsi in ((self.tur_kutu, "etiket", "Tüm türler"), (self.yazar_kutu, "yazar", "Tüm yazarlar")):
            onceki = kutu.currentText()
            kutu.blockSignals(True)
            kutu.clear()
            kutu.addItem(hepsi)
            for d in sorted({getattr(e, alan) or "(adsız)" for e in liste}):
                kutu.addItem(d)
            kutu.setCurrentIndex(max(kutu.findText(onceki), 0))
            kutu.blockSignals(False)
        self._suz()

    def _suz(self, *_):
        tur = self.tur_kutu.currentIndex()
        yazar = self.yazar_kutu.currentIndex()
        self.agac.clear()
        n = 0
        for e in self._tum:
            if tur > 0 and e.etiket != self.tur_kutu.currentText():
                continue
            if yazar > 0 and (e.yazar or "(adsız)") != self.yazar_kutu.currentText():
                continue
            oge = QTreeWidgetItem([str(e.sayfa + 1), e.etiket, e.metin.replace("\n", " ")])
            oge.setData(0, Qt.UserRole, e)
            self.agac.addTopLevelItem(oge)
            n += 1
        self.sayac.setText(f"{n} açıklama" if n else "Açıklama yok")
        self.sil_dugme.setEnabled(n > 0)

    def _sil(self):
        secili = [o.data(0, Qt.UserRole) for o in self.agac.selectedItems()]
        if secili:
            self.silmeIstendi.emit(secili)
