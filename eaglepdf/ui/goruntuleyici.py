"""Sürekli kaydırmalı PDF görüntüleyici: yalnızca görünen sayfalar çizilir (tembel yükleme)."""

from PySide6.QtCore import QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget

from ..core.belge import Belge
from . import theme

BOSLUK = 12  # sayfalar arası (px)
ONBELLEK_KOMSU = 1  # görünen sayfanın üstünde/altında tutulan sayfa sayısı
EN_AZ_OLCEK, EN_COK_OLCEK = 0.1, 6.0


def pixmap_den(px, dpr: float) -> QPixmap:
    """pymupdf.Pixmap → QPixmap (veriyi kopyalar; pymupdf nesnesi serbest bırakılabilir)."""
    img = QImage(px.samples, px.width, px.height, px.stride, QImage.Format_RGB888).copy()
    pix = QPixmap.fromImage(img)
    pix.setDevicePixelRatio(dpr)
    return pix


class SayfaEtiketi(QLabel):
    def __init__(self, indeks: int, parent=None):
        super().__init__(parent)
        self.indeks = indeks
        self.pix: QPixmap | None = None
        self.vurgular: list[tuple[float, float, float, float]] = []  # sayfa noktası (pt) cinsinden
        self.aktif_vurgu = -1
        self.olcek = 1.0

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#ffffff"))
        if self.pix is not None:
            p.drawPixmap(0, 0, self.pix)
        for n, (x0, y0, x1, y1) in enumerate(self.vurgular):
            renk = QColor(theme.ACCENT) if n == self.aktif_vurgu else QColor("#ffd54f")
            renk.setAlpha(110)
            p.fillRect(QRectF(x0 * self.olcek, y0 * self.olcek, (x1 - x0) * self.olcek, (y1 - y0) * self.olcek), renk)
        p.setPen(QColor(theme.BORDER))
        p.drawRect(self.rect().adjusted(0, 0, -1, -1))


class Goruntuleyici(QScrollArea):
    sayfaDegisti = Signal(int)  # 0 tabanlı geçerli sayfa
    olcekDegisti = Signal(float)
    sayfaTiklandi = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.belge: Belge | None = None
        self._olcek = 1.0
        self._etiketler: list[SayfaEtiketi] = []
        self._gecerli = 0
        self._vurgu_sayfalari: dict[int, list] = {}
        self.setWidgetResizable(False)
        self.setAlignment(Qt.AlignHCenter)
        self.setFocusPolicy(Qt.StrongFocus)
        self._icerik = QWidget()
        self._icerik.setStyleSheet(f"background: {theme.CANVAS};")
        self.setWidget(self._icerik)
        self._zamanlayici = QTimer(self, singleShot=True, interval=25)
        self._zamanlayici.timeout.connect(self._gorunenleri_ciz)
        self.verticalScrollBar().valueChanged.connect(self._kaydirildi)

    # --- belge ---
    def belge_ata(self, belge: Belge | None, sayfaya_git: int = 0):
        self.belge = belge
        self.yerlestir(sayfaya_git)

    @property
    def olcek(self) -> float:
        return self._olcek

    def olcek_ata(self, olcek: float):
        olcek = max(EN_AZ_OLCEK, min(EN_COK_OLCEK, olcek))
        if abs(olcek - self._olcek) < 1e-4:
            return
        self._olcek = olcek
        self.yerlestir(self._gecerli)
        self.olcekDegisti.emit(olcek)

    def genislige_sigdir(self):
        self._sigdir(lambda g, y, w, h: (w - 24) / g)

    def sayfaya_sigdir(self):
        self._sigdir(lambda g, y, w, h: min((w - 24) / g, (h - 24) / y))

    def _sigdir(self, hesap):
        if not self.belge or not self.belge.sayfa_sayisi:
            return
        g, y = self.belge.sayfa_boyutu(self._gecerli)
        vp = self.viewport()
        self.olcek_ata(hesap(g, y, vp.width(), vp.height()))

    # --- yerleşim ---
    def yerlestir(self, sayfaya_git: int = 0):
        """Sayfa kutularını (yeniden) oluşturur; ölçek/sayfa sayısı değişince çağrılır."""
        for e in self._etiketler:
            e.deleteLater()
        self._etiketler = []
        if not self.belge:
            self._icerik.resize(0, 0)
            return
        dpr = self.devicePixelRatioF()
        y = BOSLUK
        genislik = 0
        boyutlar = []
        for i in range(self.belge.sayfa_sayisi):
            g, h = self.belge.sayfa_boyutu(i)
            boyutlar.append((round(g * self._olcek), round(h * self._olcek)))
            genislik = max(genislik, boyutlar[-1][0])
        toplam_gen = max(genislik + 2 * BOSLUK, self.viewport().width())
        for i, (g, h) in enumerate(boyutlar):
            e = SayfaEtiketi(i, self._icerik)
            e.olcek = self._olcek
            e.setGeometry((toplam_gen - g) // 2, y, g, h)
            e.vurgular = list(self._vurgu_sayfalari.get(i, []))
            e.show()
            self._etiketler.append(e)
            y += h + BOSLUK
        self._icerik.resize(toplam_gen, y)
        self._dpr = dpr
        self._gecerli = min(sayfaya_git, len(self._etiketler) - 1)
        if self._etiketler:
            self.verticalScrollBar().setValue(self._etiketler[self._gecerli].y() - BOSLUK)
        self._zamanlayici.start()

    def resizeEvent(self, olay):
        super().resizeEvent(olay)
        if self.belge and self._etiketler:  # sayfalar yatayda ortada kalsın
            toplam = max(self._etiketler[0].width() + 2 * BOSLUK, self.viewport().width())
            for e in self._etiketler:
                toplam = max(toplam, e.width() + 2 * BOSLUK)
            toplam = max(toplam, self.viewport().width())
            for e in self._etiketler:
                e.move((toplam - e.width()) // 2, e.y())
            self._icerik.resize(toplam, self._icerik.height())

    # --- çizim (tembel) ---
    def _kaydirildi(self, _):
        self._zamanlayici.start()

    def _gorunen_aralik(self) -> tuple[int, int]:
        ust = self.verticalScrollBar().value()
        alt = ust + self.viewport().height()
        gorunen = [e.indeks for e in self._etiketler if e.y() + e.height() >= ust and e.y() <= alt]
        if not gorunen:
            return 0, -1
        return gorunen[0], gorunen[-1]

    def _gorunenleri_ciz(self):
        if not self.belge or not self._etiketler:
            return
        ilk, son = self._gorunen_aralik()
        dpr = self.devicePixelRatioF()
        for e in self._etiketler:
            if ilk - ONBELLEK_KOMSU <= e.indeks <= son + ONBELLEK_KOMSU:
                if e.pix is None:
                    e.pix = pixmap_den(self.belge.render(e.indeks, self._olcek * dpr), dpr)
                    e.update()
            elif e.pix is not None:
                e.pix = None
        ust = self.verticalScrollBar().value() + self.viewport().height() // 3
        yeni = self._gecerli
        for e in self._etiketler:
            if e.y() <= ust:
                yeni = e.indeks
        if yeni != self._gecerli:
            self._gecerli = yeni
            self.sayfaDegisti.emit(yeni)

    def yenile_sayfa(self, indeks: int):
        if 0 <= indeks < len(self._etiketler):
            self._etiketler[indeks].pix = None
        self._zamanlayici.start()

    # --- gezinme ---
    @property
    def gecerli_sayfa(self) -> int:
        return self._gecerli

    def git(self, indeks: int, y_pt: float | None = None):
        if not self._etiketler:
            return
        indeks = max(0, min(indeks, len(self._etiketler) - 1))
        e = self._etiketler[indeks]
        ek = round(y_pt * self._olcek) - 40 if y_pt is not None else 0
        self.verticalScrollBar().setValue(max(e.y() - BOSLUK + max(ek, 0), 0))
        self._gecerli = indeks
        self.sayfaDegisti.emit(indeks)
        self._zamanlayici.start()

    def keyPressEvent(self, olay):
        anahtar = olay.key()
        if anahtar in (Qt.Key_PageDown, Qt.Key_Right):
            self.git(self._gecerli + 1)
        elif anahtar in (Qt.Key_PageUp, Qt.Key_Left):
            self.git(self._gecerli - 1)
        elif anahtar == Qt.Key_Home:
            self.git(0)
        elif anahtar == Qt.Key_End:
            self.git(len(self._etiketler) - 1)
        else:
            super().keyPressEvent(olay)

    def wheelEvent(self, olay):
        if olay.modifiers() & Qt.ControlModifier:
            self.olcek_ata(self._olcek * (1.1 if olay.angleDelta().y() > 0 else 1 / 1.1))
            olay.accept()
        else:
            super().wheelEvent(olay)

    # --- arama vurgusu ---
    def vurgulari_ata(self, sonuclar: list, aktif: int = -1):
        """sonuclar: Belge.ara çıktısı; aktif: o sıradaki sonuç daha koyu çizilir."""
        self._vurgu_sayfalari = {}
        aktif_yeri = None
        for n, (sayfa, rect) in enumerate(sonuclar):
            liste = self._vurgu_sayfalari.setdefault(sayfa, [])
            if n == aktif:
                aktif_yeri = (sayfa, len(liste))
            liste.append(rect)
        for e in self._etiketler:
            e.vurgular = list(self._vurgu_sayfalari.get(e.indeks, []))
            e.aktif_vurgu = aktif_yeri[1] if aktif_yeri and aktif_yeri[0] == e.indeks else -1
            e.update()
        if aktif >= 0 and aktif < len(sonuclar):
            sayfa, rect = sonuclar[aktif]
            self.git(sayfa, rect[1])

    def sizeHint(self):
        return QSize(800, 600)
