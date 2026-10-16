"""PDF görüntüleyici: sürekli/tek sayfa, tek/çift sütun, el ve metin seçme aracı, gece modu.

Yalnızca görünen sayfalar çizilir (tembel yükleme); kelime konumları sayfa ilk seçildiğinde çıkarılır.
"""

from PySide6.QtCore import QPoint, QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QLabel, QScrollArea, QWidget

from ..core.belge import Belge
from . import theme

BOSLUK = 12  # sayfalar arası (px)
ONBELLEK_KOMSU = 1  # görünen satırın üstünde/altında tutulan satır sayısı
EN_AZ_OLCEK, EN_COK_OLCEK = 0.1, 6.0
ARAC_EL, ARAC_SEC = "el", "sec"
MOD_SUREKLI, MOD_TEK = "sureklu", "tek"


def pixmap_den(px, dpr: float, gece: bool = False) -> QPixmap:
    """pymupdf.Pixmap → QPixmap (veriyi kopyalar; pymupdf nesnesi serbest bırakılabilir)."""
    img = QImage(px.samples, px.width, px.height, px.stride, QImage.Format_RGB888).copy()
    if gece:
        img.invertPixels()
    pix = QPixmap.fromImage(img)
    pix.setDevicePixelRatio(dpr)
    return pix


class SayfaEtiketi(QLabel):
    def __init__(self, indeks: int, gor: "Goruntuleyici", parent=None):
        super().__init__(parent)
        self.indeks = indeks
        self.gor = gor
        self.pix: QPixmap | None = None
        self.vurgular: list[tuple[float, float, float, float]] = []  # sayfa noktası (pt)
        self.aktif_vurgu = -1
        self.secim: list[tuple[float, float, float, float]] = []
        self.olcek = 1.0
        self.gece = False

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#1e1e1e" if self.gece else "#ffffff"))
        if self.pix is not None:
            p.drawPixmap(0, 0, self.pix)
        o = self.olcek
        for n, (x0, y0, x1, y1) in enumerate(self.vurgular):
            renk = QColor(theme.ACCENT) if n == self.aktif_vurgu else QColor("#ffd54f")
            renk.setAlpha(110)
            p.fillRect(QRectF(x0 * o, y0 * o, (x1 - x0) * o, (y1 - y0) * o), renk)
        sec = QColor("#1e6fd9")
        sec.setAlpha(80)
        for x0, y0, x1, y1 in self.secim:
            p.fillRect(QRectF(x0 * o, y0 * o, (x1 - x0) * o, (y1 - y0) * o), sec)
        p.setPen(QColor(theme.BORDER))
        p.drawRect(self.rect().adjusted(0, 0, -1, -1))

    def mousePressEvent(self, olay):
        self.gor._fare_bas(self, olay)

    def mouseMoveEvent(self, olay):
        self.gor._fare_hareket(self, olay)

    def mouseReleaseEvent(self, olay):
        self.gor._fare_birak(self, olay)


class Goruntuleyici(QScrollArea):
    sayfaDegisti = Signal(int)  # 0 tabanlı geçerli sayfa
    olcekDegisti = Signal(float)
    secimDegisti = Signal(bool)  # seçili metin var mı

    def __init__(self, parent=None):
        super().__init__(parent)
        self.belge: Belge | None = None
        self._olcek = 1.0
        self._etiketler: list[SayfaEtiketi] = []
        self._satirlar: list[list[int]] = []
        self._gecerli = 0
        self._mod = MOD_SUREKLI
        self._sutun = 1
        self._gece = False
        self._arac = ARAC_EL
        self._vurgu_sayfalari: dict[int, list] = {}
        self._kelimeler: dict[int, list] = {}
        self._secim_bas: tuple[int, int] | None = None  # (sayfa, kelime)
        self._secim_son: tuple[int, int] | None = None
        self._surukle_son: QPoint | None = None
        self.setWidgetResizable(False)
        self.setAlignment(Qt.AlignHCenter)
        self.setFocusPolicy(Qt.StrongFocus)
        self._icerik = QWidget()
        self.setWidget(self._icerik)
        self._gece_boya()
        self._zamanlayici = QTimer(self, singleShot=True, interval=25)
        self._zamanlayici.timeout.connect(self._gorunenleri_ciz)
        self.verticalScrollBar().valueChanged.connect(self._kaydirildi)
        self._imlec_guncelle()

    # --- ayarlar ---
    @property
    def mod(self) -> str:
        return self._mod

    @property
    def sutun(self) -> int:
        return self._sutun

    @property
    def gece(self) -> bool:
        return self._gece

    @property
    def arac(self) -> str:
        return self._arac

    def mod_ata(self, mod: str, sutun: int):
        if (mod, sutun) == (self._mod, self._sutun):
            return
        self._mod, self._sutun = mod, sutun
        if self.belge:
            self.yerlestir(self._gecerli)

    def gece_ata(self, acik: bool):
        if acik == self._gece:
            return
        self._gece = acik
        self._gece_boya()
        for e in self._etiketler:
            e.gece = acik
            e.pix = None
            e.update()
        self._zamanlayici.start()

    def _gece_boya(self):
        self._icerik.setStyleSheet(f"background: {'#2b2b2b' if self._gece else theme.CANVAS};")
        self.viewport().setStyleSheet(f"background: {'#2b2b2b' if self._gece else theme.CANVAS};")

    def arac_ata(self, arac: str):
        self._arac = arac
        self._imlec_guncelle()

    def _imlec_guncelle(self):
        self.viewport().setCursor(Qt.OpenHandCursor if self._arac == ARAC_EL else Qt.IBeamCursor)
        for e in self._etiketler:
            e.setCursor(Qt.OpenHandCursor if self._arac == ARAC_EL else Qt.IBeamCursor)

    # --- belge ---
    def belge_ata(self, belge: Belge | None, sayfaya_git: int = 0):
        self.belge = belge
        self._kelimeler.clear()
        self.secimi_temizle()
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
        self._sigdir(lambda g, y, w, h: (w - BOSLUK * (self._sutun + 1) - 12) / (g * self._sutun))

    def sayfaya_sigdir(self):
        self._sigdir(lambda g, y, w, h: min((w - BOSLUK * (self._sutun + 1) - 12) / (g * self._sutun), (h - 2 * BOSLUK) / y))

    def _sigdir(self, hesap):
        if not self.belge or not self.belge.sayfa_sayisi:
            return
        g, y = self.belge.sayfa_boyutu(self._gecerli)
        vp = self.viewport()
        self.olcek_ata(hesap(g, y, vp.width(), vp.height()))

    # --- yerleşim ---
    def yerlestir(self, sayfaya_git: int = 0):
        """Sayfa kutularını (yeniden) oluşturur; ölçek/mod/sayfa sayısı değişince çağrılır."""
        for e in self._etiketler:
            e.deleteLater()
        self._etiketler = []
        self._satirlar = []
        if not self.belge or not self.belge.sayfa_sayisi:
            self._icerik.resize(0, 0)
            return
        n = self.belge.sayfa_sayisi
        for i in range(n):
            g, h = self.belge.sayfa_boyutu(i)
            e = SayfaEtiketi(i, self, self._icerik)
            e.olcek = self._olcek
            e.gece = self._gece
            e.resize(round(g * self._olcek), round(h * self._olcek))
            e.vurgular = list(self._vurgu_sayfalari.get(i, []))
            e.setCursor(Qt.OpenHandCursor if self._arac == ARAC_EL else Qt.IBeamCursor)
            self._etiketler.append(e)
        self._satirlar = [list(range(i, min(i + self._sutun, n))) for i in range(0, n, self._sutun)]
        self._gecerli = max(0, min(sayfaya_git, n - 1))
        self._diz()
        self._satira_kaydir(self._gecerli)
        if self._secim_bas is not None:
            self._secimi_boya()
        self._zamanlayici.start()

    def _satir_no(self, sayfa: int) -> int:
        return sayfa // self._sutun

    def _diz(self):
        """Satırları konumlandırır; tek sayfa modunda yalnızca geçerli satır görünür."""
        vp_gen = self.viewport().width()
        satir_gen = [sum(self._etiketler[i].width() for i in s) + BOSLUK * (len(s) - 1) for s in self._satirlar]
        toplam_gen = max(max(satir_gen, default=0) + 2 * BOSLUK, vp_gen)
        y = BOSLUK
        gecerli_satir = self._satir_no(self._gecerli)
        for no, s in enumerate(self._satirlar):
            gorunur = self._mod == MOD_SUREKLI or no == gecerli_satir
            yuk = max(self._etiketler[i].height() for i in s)
            x = (toplam_gen - satir_gen[no]) // 2
            for i in s:
                e = self._etiketler[i]
                e.move(x, y + (yuk - e.height()) // 2)
                e.setVisible(gorunur)
                if not gorunur:
                    e.pix = None
                x += e.width() + BOSLUK
            if gorunur:
                y += yuk + BOSLUK
        self._icerik.resize(toplam_gen, max(y, 1))

    def _satira_kaydir(self, sayfa: int):
        e = self._etiketler[sayfa]
        satir_ust = min(self._etiketler[i].y() for i in self._satirlar[self._satir_no(sayfa)])
        self.verticalScrollBar().setValue(max(satir_ust - BOSLUK, 0))

    def resizeEvent(self, olay):
        super().resizeEvent(olay)
        if self.belge and self._etiketler:
            self._diz()

    # --- çizim (tembel) ---
    def _kaydirildi(self, _):
        self._zamanlayici.start()

    def _gorunen_aralik(self) -> tuple[int, int]:
        ust = self.verticalScrollBar().value()
        alt = ust + self.viewport().height()
        gorunen = [e.indeks for e in self._etiketler if e.isVisible() and e.y() + e.height() >= ust and e.y() <= alt]
        return (gorunen[0], gorunen[-1]) if gorunen else (0, -1)

    def _gorunenleri_ciz(self):
        if not self.belge or not self._etiketler:
            return
        ilk, son = self._gorunen_aralik()
        pay = ONBELLEK_KOMSU * self._sutun
        dpr = self.devicePixelRatioF()
        for e in self._etiketler:
            if e.isVisible() and ilk - pay <= e.indeks <= son + pay:
                if e.pix is None:
                    e.pix = pixmap_den(self.belge.render(e.indeks, self._olcek * dpr), dpr, self._gece)
                    e.update()
            elif e.pix is not None:
                e.pix = None
        if self._mod == MOD_SUREKLI:
            ust = self.verticalScrollBar().value() + self.viewport().height() // 3
            yeni = self._gecerli
            for satir in self._satirlar:
                if min(self._etiketler[i].y() for i in satir) <= ust:
                    yeni = satir[0]
            if yeni // self._sutun != self._gecerli // self._sutun:
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
        eski_satir = self._satir_no(self._gecerli)
        self._gecerli = indeks
        if self._mod == MOD_TEK and self._satir_no(indeks) != eski_satir:
            self._diz()
        self._satira_kaydir(indeks)
        if y_pt is not None:
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() + max(round(y_pt * self._olcek) - 40, 0))
        self.sayfaDegisti.emit(indeks)
        self._zamanlayici.start()

    def keyPressEvent(self, olay):
        anahtar = olay.key()
        adim = self._sutun
        if anahtar in (Qt.Key_PageDown, Qt.Key_Right) or (anahtar == Qt.Key_Down and self._mod == MOD_TEK):
            self.git(self._gecerli + adim)
        elif anahtar in (Qt.Key_PageUp, Qt.Key_Left) or (anahtar == Qt.Key_Up and self._mod == MOD_TEK):
            self.git(self._gecerli - adim)
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
            return
        sb = self.verticalScrollBar()
        if self._mod == MOD_TEK and (sb.maximum() == 0 or (olay.angleDelta().y() < 0 and sb.value() == sb.maximum())
                                     or (olay.angleDelta().y() > 0 and sb.value() == sb.minimum())):
            self.git(self._gecerli + (self._sutun if olay.angleDelta().y() < 0 else -self._sutun))
            olay.accept()
            return
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
        if 0 <= aktif < len(sonuclar):
            sayfa, rect = sonuclar[aktif]
            self.git(sayfa, rect[1])

    # --- fare: el aracı ve metin seçme ---
    def _icerik_noktasi(self, etiket: SayfaEtiketi, olay) -> QPoint:
        return etiket.mapTo(self._icerik, olay.position().toPoint())

    def _nokta_sayfasi(self, p: QPoint) -> tuple[int, QPointF] | None:
        """İçerik koordinatındaki noktanın hangi sayfada (ve sayfa noktası cinsinden nerede) olduğu."""
        en_yakin, en_uzak = None, 10 ** 9
        for e in self._etiketler:
            if not e.isVisible():
                continue
            if e.geometry().contains(p):
                en_yakin = e
                break
            r = e.geometry()
            d = abs(p.y() - max(r.top(), min(p.y(), r.bottom()))) + abs(p.x() - max(r.left(), min(p.x(), r.right())))
            if d < en_uzak:
                en_yakin, en_uzak = e, d
        if en_yakin is None:
            return None
        g = en_yakin.geometry()
        return en_yakin.indeks, QPointF((p.x() - g.x()) / self._olcek, (p.y() - g.y()) / self._olcek)

    def _kelime_listesi(self, sayfa: int) -> list:
        if sayfa not in self._kelimeler:
            self._kelimeler[sayfa] = self.belge.kelimeler(sayfa) if self.belge else []
        return self._kelimeler[sayfa]

    def _kelime_bul(self, sayfa: int, nokta: QPointF) -> int:
        """Noktaya en yakın kelimenin sırası (-1: sayfada kelime yok)."""
        en_iyi, en_uzak = -1, 1e18
        for n, (x0, y0, x1, y1, *_r) in enumerate(self._kelime_listesi(sayfa)):
            dx = max(x0 - nokta.x(), 0, nokta.x() - x1)
            dy = max(y0 - nokta.y(), 0, nokta.y() - y1)
            d = dx * dx + dy * dy * 4
            if d < en_uzak:
                en_iyi, en_uzak = n, d
        return en_iyi

    def _fare_bas(self, etiket, olay):
        if olay.button() != Qt.LeftButton:
            return
        if self._arac == ARAC_EL:
            self._surukle_son = olay.globalPosition().toPoint()
            self.viewport().setCursor(Qt.ClosedHandCursor)
            etiket.setCursor(Qt.ClosedHandCursor)
            return
        self.setFocus()
        konum = self._nokta_sayfasi(self._icerik_noktasi(etiket, olay))
        self.secimi_temizle()
        if konum:
            k = self._kelime_bul(konum[0], konum[1])
            if k >= 0:
                self._secim_bas = self._secim_son = (konum[0], k)

    def _fare_hareket(self, etiket, olay):
        if self._arac == ARAC_EL and self._surukle_son is not None:
            simdi = olay.globalPosition().toPoint()
            fark = simdi - self._surukle_son
            self._surukle_son = simdi
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - fark.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - fark.y())
            return
        if self._arac == ARAC_SEC and self._secim_bas is not None:
            konum = self._nokta_sayfasi(self._icerik_noktasi(etiket, olay))
            if konum:
                k = self._kelime_bul(konum[0], konum[1])
                if k >= 0 and (konum[0], k) != self._secim_son:
                    self._secim_son = (konum[0], k)
                    self._secimi_boya()

    def _fare_birak(self, etiket, olay):
        if self._arac == ARAC_EL:
            self._surukle_son = None
            self._imlec_guncelle()
        else:
            self.secimDegisti.emit(bool(self.secili_metin()))

    def _secili_kelimeler(self) -> list[tuple[int, int]]:
        if self._secim_bas is None or self._secim_son is None:
            return []
        bas, son = sorted((self._secim_bas, self._secim_son))
        sonuc = []
        for sayfa in range(bas[0], son[0] + 1):
            adet = len(self._kelime_listesi(sayfa))
            ilk = bas[1] if sayfa == bas[0] else 0
            bit = son[1] if sayfa == son[0] else adet - 1
            sonuc += [(sayfa, k) for k in range(ilk, bit + 1)]
        return sonuc

    def _secimi_boya(self):
        per_sayfa: dict[int, list] = {}
        for sayfa, k in self._secili_kelimeler():
            per_sayfa.setdefault(sayfa, []).append(self._kelime_listesi(sayfa)[k][:4])
        for e in self._etiketler:
            e.secim = per_sayfa.get(e.indeks, [])
            e.update()

    def secimi_temizle(self):
        degisti = self._secim_bas is not None
        self._secim_bas = self._secim_son = None
        for e in self._etiketler:
            if e.secim:
                e.secim = []
                e.update()
        if degisti:
            self.secimDegisti.emit(False)

    def secili_metin(self) -> str:
        parcalar, onceki = [], None
        for sayfa, k in self._secili_kelimeler():
            kel = self._kelime_listesi(sayfa)[k]
            anahtar = (sayfa, kel[5], kel[6])  # sayfa, blok, satır
            if onceki is not None:
                parcalar.append("\n" if anahtar[0] != onceki[0] or anahtar[1:] != onceki[1:] else " ")
            parcalar.append(kel[4])
            onceki = anahtar
        return "".join(parcalar)

    def kopyala(self) -> bool:
        metin = self.secili_metin()
        if metin:
            QApplication.clipboard().setText(metin)
        return bool(metin)

    def sizeHint(self):
        return QSize(800, 600)
