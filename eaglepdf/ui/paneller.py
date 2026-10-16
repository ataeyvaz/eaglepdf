"""Sol paneller: küçük resimler (sürükle-bırak sıralama, çoklu seçim) ve yer imleri."""

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QAbstractItemView, QListView, QListWidget, QListWidgetItem, QTreeWidget, QTreeWidgetItem

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

    def _sonrakini_ciz(self):
        for _ in range(3):
            if not self._bekleyen or not self.belge:
                self._zaman.stop()
                return
            i = self._bekleyen.pop(0)
            oge = self._oge_bul(i)
            if oge is None:
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


class YerImleri(QTreeWidget):
    sayfaSecildi = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.itemClicked.connect(lambda o, _: self.sayfaSecildi.emit(o.data(0, Qt.UserRole)))

    def belge_ata(self, belge: Belge | None):
        self.clear()
        if not belge:
            return
        yigin: list[tuple[int, QTreeWidgetItem]] = []
        for duzey, baslik, sayfa in belge.icindekiler():
            oge = QTreeWidgetItem([baslik])
            oge.setData(0, Qt.UserRole, sayfa)
            while yigin and yigin[-1][0] >= duzey:
                yigin.pop()
            (yigin[-1][1].addChild if yigin else self.addTopLevelItem)(oge)
            yigin.append((duzey, oge))
        self.expandToDepth(0)
