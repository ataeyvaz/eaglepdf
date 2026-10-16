"""PDF görüntüleyici: sürekli/tek sayfa, tek/çift sütun, gece modu ve fare araçları.

Araçlar: el, metin seçme, metin işaretleme (vurgu/altı/üstü/dalga), çizim, şekil, not, metin kutusu, bağlantı,
imza yerleştirme ve ek açıklama seç/taşı. Görüntüleyici belgeyi değiştirmez; bir iş bittiğinde `aracEylemi`
sinyaliyle (araç, sayfa, veri) ana pencereye bildirir. Yalnızca görünen sayfalar çizilir (tembel yükleme).
"""

from PySide6.QtCore import QPoint, QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox, QLabel, QLineEdit, QScrollArea, QWidget

from ..core.belge import Belge
from ..core.ekaciklama import TASINABILIR, kelimelerden_satirlar
from . import theme

BOSLUK = 12  # sayfalar arası (px)
ONBELLEK_KOMSU = 1  # görünen satırın üstünde/altında tutulan satır sayısı
EN_AZ_OLCEK, EN_COK_OLCEK = 0.1, 6.0
ARAC_EL, ARAC_SEC, ARAC_DUZENLE = "el", "sec", "duzenle"
ISARET_ARACLARI = ("vurgu", "alti", "ustu", "dalga")
SEKIL_ARACLARI = ("cizgi", "ok", "dikdortgen", "elips")
SURUKLE_ARACLARI = SEKIL_ARACLARI + ("metin", "baglanti", "imza")
MOD_SUREKLI, MOD_TEK = "sureklu", "tek"
TIKLAMA_ESIGI = 4  # px: bundan az hareket tıklamadır


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
        self.vurgular: list[tuple[float, float, float, float]] = []  # arama sonucu, sayfa noktası (pt)
        self.aktif_vurgu = -1
        self.secim: list[tuple[float, float, float, float]] = []  # metin seçimi
        self.onizleme: tuple | None = None  # sürüklenen çizim/şekil önizlemesi
        self.secili_ek: tuple[float, float, float, float] | None = None
        self.tasima = (0.0, 0.0)
        self.form_widgetlari: list[QWidget] = []
        self.olcek = 1.0
        self.gece = False

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
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
        if self.secili_ek:
            x0, y0, x1, y1 = self.secili_ek
            dx, dy = self.tasima
            kalem = QPen(QColor(theme.ACCENT), 1.5, Qt.DashLine)
            p.setPen(kalem)
            p.setBrush(Qt.NoBrush)
            p.drawRect(QRectF((x0 + dx) * o - 3, (y0 + dy) * o - 3, (x1 - x0) * o + 6, (y1 - y0) * o + 6))
        if self.onizleme:
            self._onizleme_ciz(p)
        p.setPen(QColor(theme.BORDER))
        p.setBrush(Qt.NoBrush)
        p.drawRect(self.rect().adjusted(0, 0, -1, -1))

    def _onizleme_ciz(self, p: QPainter):
        tur, veri, renk, kalinlik = self.onizleme
        o = self.olcek
        kalem = QPen(QColor(renk), max(kalinlik * o, 1), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        p.setPen(kalem)
        p.setBrush(Qt.NoBrush)
        if tur == "poli":
            for a, b in zip(veri, veri[1:]):
                p.drawLine(QPointF(a[0] * o, a[1] * o), QPointF(b[0] * o, b[1] * o))
            return
        (x0, y0), (x1, y1) = veri
        if tur in ("cizgi", "ok"):
            p.drawLine(QPointF(x0 * o, y0 * o), QPointF(x1 * o, y1 * o))
            return
        r = QRectF(QPointF(x0 * o, y0 * o), QPointF(x1 * o, y1 * o)).normalized()
        if tur == "elips":
            p.drawEllipse(r)
        elif tur == "dikdortgen":
            p.drawRect(r)
        else:  # metin / bağlantı / imza: kesikli kutu
            p.setPen(QPen(QColor(theme.ACCENT), 1.5, Qt.DashLine))
            p.drawRect(r)

    def mousePressEvent(self, olay):
        self.gor._fare_bas(self, olay)

    def mouseMoveEvent(self, olay):
        self.gor._fare_hareket(self, olay)

    def mouseReleaseEvent(self, olay):
        self.gor._fare_birak(self, olay)

    def mouseDoubleClickEvent(self, olay):
        self.gor._cift_tik(self, olay)

    def contextMenuEvent(self, olay):
        self.gor._sag_tik(self, olay)


class Goruntuleyici(QScrollArea):
    sayfaDegisti = Signal(int)  # 0 tabanlı geçerli sayfa
    olcekDegisti = Signal(float)
    secimDegisti = Signal(bool)  # seçili metin var mı
    aracEylemi = Signal(str, int, object)  # araç, sayfa, veri (kalan eylemleri ana pencere uygular)
    ekSecildi = Signal(object)  # EkAciklama ya da None
    baglantiTiklandi = Signal(dict)
    sagTiklandi = Signal(str, int, object, object)  # tür ("ek"|"baglanti"|"sayfa"), sayfa, veri, genel konum
    formDegisti = Signal(int, int, object)  # sayfa, alan xref, yeni değer

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
        self.renk = "#c62828"        # etkin aracın rengi (önizleme için)
        self.kalinlik = 2.0
        self.form_acik = True
        self._vurgu_sayfalari: dict[int, list] = {}
        self._kelimeler: dict[int, list] = {}
        self._baglanti_onbellek: dict[int, list] = {}
        self._form_onbellek: dict[int, list] = {}
        self._secim_bas: tuple[int, int] | None = None  # (sayfa, kelime)
        self._secim_son: tuple[int, int] | None = None
        self._surukle_son: QPoint | None = None
        self._bas_global: QPoint | None = None
        self._bas_nokta: tuple[float, float] | None = None
        self._cizim: list[tuple[float, float]] = []
        self._secili_ek = None
        self._tasinan = None
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

    @property
    def secili_ek(self):
        return self._secili_ek

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
        renk = "#2b2b2b" if self._gece else theme.CANVAS
        self._icerik.setStyleSheet(f"background: {renk};")
        self.viewport().setStyleSheet(f"background: {renk};")

    def arac_ata(self, arac: str):
        self._arac = arac
        if arac != ARAC_DUZENLE:
            self.ek_secimini_kaldir()
        if arac not in (ARAC_SEC,) + ISARET_ARACLARI:
            self.secimi_temizle()
        self._imlec_guncelle()

    def _imlec_guncelle(self):
        if self._arac == ARAC_EL:
            imlec = Qt.OpenHandCursor
        elif self._arac in (ARAC_SEC,) + ISARET_ARACLARI:
            imlec = Qt.IBeamCursor
        elif self._arac == ARAC_DUZENLE:
            imlec = Qt.ArrowCursor
        else:
            imlec = Qt.CrossCursor
        self.viewport().setCursor(imlec)
        for e in self._etiketler:
            e.setCursor(imlec)

    def form_acik_ata(self, acik: bool):
        self.form_acik = acik
        for e in self._etiketler:
            self._form_temizle(e)
        self._zamanlayici.start()

    # --- belge ---
    def belge_ata(self, belge: Belge | None, sayfaya_git: int = 0):
        self.belge = belge
        self._kelimeler.clear()
        self._baglanti_onbellek.clear()
        self._form_onbellek.clear()
        self.secimi_temizle()
        self.ek_secimini_kaldir()
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
            self._etiket_ek_durumu(e)
            self._etiketler.append(e)
        self._imlec_guncelle()
        self._satirlar = [list(range(i, min(i + self._sutun, n))) for i in range(0, n, self._sutun)]
        self._gecerli = max(0, min(sayfaya_git, n - 1))
        self._diz()
        self._satira_kaydir(self._gecerli)
        if self._secim_bas is not None:
            self._secimi_boya()
        self._zamanlayici.start()

    def _etiket_ek_durumu(self, e: SayfaEtiketi):
        if self._secili_ek and self._secili_ek.sayfa == e.indeks:
            e.secili_ek = self._secili_ek.rect

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
                    self._form_temizle(e)
                x += e.width() + BOSLUK
            if gorunur:
                y += yuk + BOSLUK
        self._icerik.resize(toplam_gen, max(y, 1))

    def _satira_kaydir(self, sayfa: int):
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
                    self._form_kur(e)
            elif e.pix is not None:
                e.pix = None
                self._form_temizle(e)
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
        """Sayfanın görüntüsünü ve ek durumlarını yeniden üretir (belge içeriği değişti)."""
        for sozluk in (self._kelimeler, self._baglanti_onbellek, self._form_onbellek):
            sozluk.pop(indeks, None)
        if 0 <= indeks < len(self._etiketler):
            e = self._etiketler[indeks]
            e.pix = None
            self._form_temizle(e)
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

    # --- koordinat yardımcıları ---
    def _icerik_noktasi(self, etiket: SayfaEtiketi, olay) -> QPoint:
        return etiket.mapTo(self._icerik, olay.position().toPoint())

    def _sayfa_noktasi(self, etiket: SayfaEtiketi, olay) -> tuple[float, float]:
        """Etiket içindeki fare konumu → sayfa noktası (pt); sayfa dışına taşarsa kenara kırpılır."""
        g, y = self.belge.sayfa_boyutu(etiket.indeks)
        konum = olay.position()
        return (max(0.0, min(g, konum.x() / self._olcek)), max(0.0, min(y, konum.y() / self._olcek)))

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

    def _baglanti_bul(self, sayfa: int, nokta: tuple[float, float]) -> dict | None:
        if sayfa not in self._baglanti_onbellek:
            self._baglanti_onbellek[sayfa] = self.belge.baglantilar(sayfa)
        for b in self._baglanti_onbellek[sayfa]:
            x0, y0, x1, y1 = b["rect"]
            if x0 <= nokta[0] <= x1 and y0 <= nokta[1] <= y1:
                return b
        return None

    # --- fare ---
    def _fare_bas(self, etiket, olay):
        if olay.button() != Qt.LeftButton or not self.belge:
            return
        arac = self._arac
        self._bas_global = olay.globalPosition().toPoint()
        self._bas_nokta = self._sayfa_noktasi(etiket, olay)
        if arac == ARAC_EL:
            self._surukle_son = self._bas_global
            self.viewport().setCursor(Qt.ClosedHandCursor)
            etiket.setCursor(Qt.ClosedHandCursor)
        elif arac == ARAC_SEC or arac in ISARET_ARACLARI:
            self.setFocus()
            konum = self._nokta_sayfasi(self._icerik_noktasi(etiket, olay))
            self.secimi_temizle()
            if konum:
                k = self._kelime_bul(konum[0], konum[1])
                if k >= 0:
                    self._secim_bas = self._secim_son = (konum[0], k)
        elif arac == "ciz":
            self._cizim = [self._bas_nokta]
            etiket.onizleme = ("poli", self._cizim, self.renk, self.kalinlik)
        elif arac in SURUKLE_ARACLARI:
            etiket.onizleme = (arac, (self._bas_nokta, self._bas_nokta), self.renk, self.kalinlik)
        elif arac == ARAC_DUZENLE:
            self.setFocus()
            ek = self.belge.ek_bul(etiket.indeks, self._bas_nokta)
            self._ek_sec(ek)
            self._tasinan = ek if ek and ek.tur in TASINABILIR else None
        etiket.update()

    def _fare_hareket(self, etiket, olay):
        arac = self._arac
        if arac == ARAC_EL and self._surukle_son is not None:
            simdi = olay.globalPosition().toPoint()
            fark = simdi - self._surukle_son
            self._surukle_son = simdi
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - fark.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - fark.y())
            return
        if (arac == ARAC_SEC or arac in ISARET_ARACLARI) and self._secim_bas is not None:
            konum = self._nokta_sayfasi(self._icerik_noktasi(etiket, olay))
            if konum:
                k = self._kelime_bul(konum[0], konum[1])
                if k >= 0 and (konum[0], k) != self._secim_son:
                    self._secim_son = (konum[0], k)
                    self._secimi_boya()
            return
        if self._bas_nokta is None:
            return
        nokta = self._sayfa_noktasi(etiket, olay)
        if arac == "ciz" and self._cizim:
            if (nokta[0] - self._cizim[-1][0]) ** 2 + (nokta[1] - self._cizim[-1][1]) ** 2 > 0.5:
                self._cizim.append(nokta)
                etiket.update()
        elif arac in SURUKLE_ARACLARI and etiket.onizleme:
            etiket.onizleme = (arac, (self._bas_nokta, nokta), self.renk, self.kalinlik)
            etiket.update()
        elif arac == ARAC_DUZENLE and self._tasinan is not None:
            etiket.tasima = (nokta[0] - self._bas_nokta[0], nokta[1] - self._bas_nokta[1])
            etiket.update()

    def _fare_birak(self, etiket, olay):
        arac = self._arac
        bas_global, self._bas_global = self._bas_global, None
        hareket = (olay.globalPosition().toPoint() - bas_global).manhattanLength() if bas_global else 0
        tiklama = hareket < TIKLAMA_ESIGI
        bas_nokta, self._bas_nokta = self._bas_nokta, None
        if not self.belge or bas_nokta is None:
            return
        nokta = self._sayfa_noktasi(etiket, olay)
        sayfa = etiket.indeks
        if arac == ARAC_EL:
            self._surukle_son = None
            self._imlec_guncelle()
        if arac in (ARAC_EL, ARAC_SEC) and tiklama:
            baglanti = self._baglanti_bul(sayfa, bas_nokta)
            if baglanti:
                self.baglantiTiklandi.emit(baglanti)
                return
        if arac == ARAC_SEC:
            self.secimDegisti.emit(bool(self.secili_metin()))
        elif arac in ISARET_ARACLARI:
            veri = self._secili_satirlar()
            self.secimi_temizle()
            if veri:
                self.aracEylemi.emit(arac, -1, veri)
        elif arac == "ciz":
            etiket.onizleme = None
            cizgi, self._cizim = self._cizim, []
            etiket.update()
            if len(cizgi) >= 2:
                self.aracEylemi.emit("ciz", sayfa, [cizgi])
        elif arac == "not":
            self.aracEylemi.emit("not", sayfa, bas_nokta)
        elif arac in SURUKLE_ARACLARI:
            etiket.onizleme = None
            etiket.update()
            if tiklama and arac in ("metin", "imza"):
                self.aracEylemi.emit(arac, sayfa, (bas_nokta, None))
            elif not tiklama:
                self.aracEylemi.emit(arac, sayfa, (bas_nokta, nokta))
        elif arac == ARAC_DUZENLE and self._tasinan is not None:
            dx, dy = etiket.tasima
            etiket.tasima = (0.0, 0.0)
            tasinan, self._tasinan = self._tasinan, None
            if not tiklama:
                self.aracEylemi.emit("tasi", sayfa, (tasinan.xref, dx, dy))
            etiket.update()

    def _cift_tik(self, etiket, olay):
        if self._arac == ARAC_DUZENLE and self.belge:
            ek = self.belge.ek_bul(etiket.indeks, self._sayfa_noktasi(etiket, olay))
            if ek:
                self._ek_sec(ek)
                self.aracEylemi.emit("ek_duzenle", etiket.indeks, ek)

    def _sag_tik(self, etiket, olay):
        if not self.belge:
            return
        nokta = self._sayfa_noktasi(etiket, olay)
        genel = olay.globalPos()
        if self._arac == ARAC_DUZENLE:
            ek = self.belge.ek_bul(etiket.indeks, nokta)
            if ek:
                self._ek_sec(ek)
                self.sagTiklandi.emit("ek", etiket.indeks, ek, genel)
                return
        baglanti = self._baglanti_bul(etiket.indeks, nokta)
        if baglanti and self._arac == ARAC_DUZENLE:
            self.sagTiklandi.emit("baglanti", etiket.indeks, baglanti, genel)
        else:
            self.sagTiklandi.emit("sayfa", etiket.indeks, nokta, genel)

    # --- ek açıklama seçimi ---
    def _ek_sec(self, ek):
        self.ek_secimini_ayarla(ek)
        self.ekSecildi.emit(ek)

    def ek_secimini_ayarla(self, ek):
        self._secili_ek = ek
        for e in self._etiketler:
            e.secili_ek = ek.rect if ek and ek.sayfa == e.indeks else None
            e.tasima = (0.0, 0.0)
            e.update()

    def ek_secimini_kaldir(self):
        if self._secili_ek is not None:
            self.ek_secimini_ayarla(None)
            self.ekSecildi.emit(None)

    # --- metin seçme ---
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

    def _secili_satirlar(self) -> dict[int, list]:
        """{sayfa: [satır dikdörtgenleri]} — işaretleme araçları için."""
        per_sayfa: dict[int, list] = {}
        for sayfa, k in self._secili_kelimeler():
            per_sayfa.setdefault(sayfa, []).append(self._kelime_listesi(sayfa)[k])
        return {s: kelimelerden_satirlar(k) for s, k in per_sayfa.items()}

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

    # --- form alanları (sayfa üstüne doldurulabilir kutular) ---
    def _form_temizle(self, etiket: SayfaEtiketi):
        for w in etiket.form_widgetlari:
            w.deleteLater()
        etiket.form_widgetlari = []

    def _form_kur(self, etiket: SayfaEtiketi):
        self._form_temizle(etiket)
        if not self.form_acik or not self.belge or not self.belge.form_var_mi():
            return
        if etiket.indeks not in self._form_onbellek:
            self._form_onbellek[etiket.indeks] = self.belge.form_alanlari([etiket.indeks])
        o = self._olcek
        for alan in self._form_onbellek[etiket.indeks]:
            if alan.salt_okunur or alan.tur not in ("metin", "onay", "secenek", "acilir", "liste"):
                continue
            x0, y0, x1, y1 = alan.rect
            w = self._form_widget(alan, etiket)
            w.setGeometry(round(x0 * o), round(y0 * o), max(round((x1 - x0) * o), 8), max(round((y1 - y0) * o), 8))
            w.show()
            etiket.form_widgetlari.append(w)

    def _form_widget(self, alan, etiket: SayfaEtiketi) -> QWidget:
        sayfa, xref = etiket.indeks, alan.xref
        zemin = "background: rgba(255, 244, 150, 0.85); border: 1px solid #e0a800;"
        if alan.tur == "metin":
            w = QLineEdit(str(alan.deger or ""), etiket)
            w.setStyleSheet(f"QLineEdit {{ {zemin} padding: 0 2px; }}")
            son = [str(alan.deger or "")]

            def bitti():
                if w.text() != son[0]:
                    son[0] = w.text()
                    self.formDegisti.emit(sayfa, xref, w.text())
            w.editingFinished.connect(bitti)
        elif alan.tur in ("onay", "secenek"):
            w = QCheckBox(etiket)
            w.setChecked(bool(alan.deger))
            w.setStyleSheet(f"QCheckBox {{ {zemin} }}")
            w.clicked.connect(lambda isaretli: self.formDegisti.emit(sayfa, xref, isaretli))
        else:
            w = QComboBox(etiket)
            w.addItems(alan.secenekler)
            if str(alan.deger) in alan.secenekler:
                w.setCurrentText(str(alan.deger))
            w.setStyleSheet(f"QComboBox {{ {zemin} padding: 0 2px; }}")
            w.textActivated.connect(lambda metin: self.formDegisti.emit(sayfa, xref, metin))
        return w

    def sizeHint(self):
        return QSize(800, 600)
