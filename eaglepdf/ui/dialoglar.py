"""Ek açıklama pencereleri: metin kutusu/not, bağlantı ve imza oluşturma."""

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QPointF, QRect, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QFontMetrics, QImage, QPainter, QPen
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
    QPushButton, QRadioButton, QSpinBox, QTabWidget, QVBoxLayout, QWidget, QComboBox,
)

from .. import APP_NAME
from . import theme

IMZA_YAZI_TIPLERI = ("Segoe Script", "Lucida Handwriting", "Brush Script MT", "Ink Free", "Segoe Print", "Mistral")
IMZA_RENKLERI = (("Siyah", "#111111"), ("Mavi", "#1a3fa8"), ("Kırmızı", "#c62828"))


def _dugmeler(pencere: QDialog, tamam: str) -> QDialogButtonBox:
    kutu = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    kutu.button(QDialogButtonBox.Ok).setText(tamam)
    kutu.button(QDialogButtonBox.Cancel).setText("Vazgeç")
    kutu.accepted.connect(pencere.accept)
    kutu.rejected.connect(pencere.reject)
    return kutu


def png_baytlari(img: QImage) -> bytes:
    ara = QByteArray()
    tampon = QBuffer(ara)
    tampon.open(QIODevice.WriteOnly)
    img.save(tampon, "PNG")
    return bytes(ara)


class MetinPenceresi(QDialog):
    """Not ya da metin kutusu metni; metin kutusunda yazı boyutu / kalın / italik de sorulur."""

    def __init__(self, parent=None, baslik="Metin", metin="", stil=False, boyut=14, kalin=False, italik=False):
        super().__init__(parent)
        self.setWindowTitle(baslik)
        self.resize(420, 260 if stil else 220)
        duzen = QVBoxLayout(self)
        self.kutu = QPlainTextEdit(metin)
        self.kutu.setPlaceholderText("Metni yazın…")
        duzen.addWidget(self.kutu, 1)
        self.boyut = QSpinBox()
        self.kalin = QCheckBox("Kalın")
        self.italik = QCheckBox("İtalik")
        if stil:
            satir = QHBoxLayout()
            satir.addWidget(QLabel("Yazı boyutu:"))
            self.boyut.setRange(6, 144)
            self.boyut.setValue(int(boyut))
            satir.addWidget(self.boyut)
            self.kalin.setChecked(kalin)
            self.italik.setChecked(italik)
            satir.addWidget(self.kalin)
            satir.addWidget(self.italik)
            satir.addStretch()
            duzen.addLayout(satir)
        duzen.addWidget(_dugmeler(self, "Tamam"))
        self.kutu.setFocus()

    def metin(self) -> str:
        return self.kutu.toPlainText().strip()


class BaglantiPenceresi(QDialog):
    def __init__(self, sayfa_sayisi: int, parent=None, uri="", hedef_sayfa=1):
        super().__init__(parent)
        self.setWindowTitle("Bağlantı Ekle")
        duzen = QVBoxLayout(self)
        self.web = QRadioButton("Web adresi:")
        self.sayfa = QRadioButton("Belgede sayfa:")
        grup = QButtonGroup(self)
        grup.addButton(self.web)
        grup.addButton(self.sayfa)
        self.adres = QLineEdit(uri)
        self.adres.setPlaceholderText("örn. www.ornek.com")
        self.sayfa_no = QSpinBox()
        self.sayfa_no.setRange(1, max(sayfa_sayisi, 1))
        self.sayfa_no.setValue(hedef_sayfa)
        (self.sayfa if not uri and hedef_sayfa != 1 else self.web).setChecked(True)
        duzen.addWidget(self.web)
        duzen.addWidget(self.adres)
        duzen.addWidget(self.sayfa)
        duzen.addWidget(self.sayfa_no)
        self.hata = QLabel()
        self.hata.setStyleSheet("color: #c62828;")
        duzen.addWidget(self.hata)
        kutu = _dugmeler(self, "Ekle")
        kutu.accepted.disconnect()
        kutu.accepted.connect(self._tamam)
        duzen.addWidget(kutu)

    def _tamam(self):
        if self.web.isChecked() and not self.adres.text().strip():
            self.hata.setText("Web adresi boş olamaz.")
            return
        self.accept()

    def sonuc(self) -> tuple[str | None, int | None]:
        """(uri, None) ya da (None, 0 tabanlı sayfa)"""
        if self.web.isChecked():
            return self.adres.text().strip(), None
        return None, self.sayfa_no.value() - 1


class CizimTuvali(QWidget):
    """Fareyle imza çizilen alan; saydam arka plan, çizim sınırları izlenir."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(460, 200)
        self.setCursor(Qt.CrossCursor)
        self.renk = IMZA_RENKLERI[0][1]
        self._cizgiler: list[list[QPointF]] = []
        self._renkler: list[str] = []

    def temizle(self):
        self._cizgiler, self._renkler = [], []
        self.update()

    def bos_mu(self) -> bool:
        return not any(len(c) > 1 for c in self._cizgiler)

    def mousePressEvent(self, olay):
        self._cizgiler.append([olay.position()])
        self._renkler.append(self.renk)

    def mouseMoveEvent(self, olay):
        if self._cizgiler:
            self._cizgiler[-1].append(olay.position())
            self.update()

    def _ciz(self, p: QPainter):
        for cizgi, renk in zip(self._cizgiler, self._renkler):
            p.setPen(QPen(QColor(renk), 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            for a, b in zip(cizgi, cizgi[1:]):
                p.drawLine(a, b)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("#ffffff"))
        p.setPen(QPen(QColor("#d9d9d9"), 1, Qt.DashLine))
        y = self.height() * 0.72
        p.drawLine(16, int(y), self.width() - 16, int(y))
        self._ciz(p)

    def goruntu(self) -> QImage:
        """Çizimi saydam arka planlı, içeriğe göre kırpılmış PNG olarak verir."""
        img = QImage(self.size() * 2, QImage.Format_ARGB32)
        img.fill(Qt.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        p.scale(2, 2)
        self._ciz(p)
        p.end()
        return icerige_kirp(img)


def icerige_kirp(img: QImage, pay: int = 8) -> QImage:
    """Saydam olmayan piksellerin sınırlayıcı kutusuna (pay ile) kırpar."""
    sol, ust, sag, alt = img.width(), img.height(), -1, -1
    for y in range(img.height()):
        for x in range(img.width()):
            if (img.pixel(x, y) >> 24) & 0xFF > 8:
                sol, sag = min(sol, x), max(sag, x)
                ust, alt = min(ust, y), max(alt, y)
    if sag < 0:
        return img
    r = QRect(sol - pay, ust - pay, sag - sol + 1 + 2 * pay, alt - ust + 1 + 2 * pay).intersected(img.rect())
    return img.copy(r)


def beyazi_saydam_yap(img: QImage, en_buyuk: int = 700) -> QImage:
    """Fotoğraf/tarama imzada beyaz zemini saydamlaştırır (koyuluğa göre alfa)."""
    if max(img.width(), img.height()) > en_buyuk:
        img = img.scaled(en_buyuk, en_buyuk, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    img = img.convertToFormat(QImage.Format_ARGB32)
    for y in range(img.height()):
        for x in range(img.width()):
            c = QColor(img.pixel(x, y))
            en_koyu = min(c.red(), c.green(), c.blue())
            alfa = max(0, min(255, int((255 - en_koyu) * 1.4)))
            img.setPixelColor(x, y, QColor(c.red(), c.green(), c.blue(), alfa if en_koyu < 235 else 0))
    return icerige_kirp(img)


class ImzaPenceresi(QDialog):
    """Üç yolla imza oluşturur: çiz, yaz, resimden. `png()` saydam PNG baytlarını verir."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("İmza Oluştur")
        self.setMinimumWidth(500)
        self._png: bytes | None = None
        duzen = QVBoxLayout(self)
        self.sekmeler = QTabWidget()
        duzen.addWidget(self.sekmeler)

        cizim = QWidget()
        cd = QVBoxLayout(cizim)
        self.tuval = CizimTuvali()
        cd.addWidget(self.tuval)
        satir = QHBoxLayout()
        satir.addWidget(QLabel("Renk:"))
        self.renk_kutu = QComboBox()
        for ad, _r in IMZA_RENKLERI:
            self.renk_kutu.addItem(ad)
        self.renk_kutu.currentIndexChanged.connect(lambda i: setattr(self.tuval, "renk", IMZA_RENKLERI[i][1]))
        satir.addWidget(self.renk_kutu)
        temizle = QPushButton("Temizle")
        temizle.setAutoDefault(False)
        temizle.clicked.connect(self.tuval.temizle)
        satir.addStretch()
        satir.addWidget(temizle)
        cd.addLayout(satir)
        self.sekmeler.addTab(cizim, "Çiz")

        yaz = QWidget()
        yd = QVBoxLayout(yaz)
        self.ad_kutu = QLineEdit()
        self.ad_kutu.setPlaceholderText("Adınızı yazın")
        yd.addWidget(self.ad_kutu)
        self.yazi_tipi = QComboBox()
        mevcut = set(QFontDatabase.families())
        for f in IMZA_YAZI_TIPLERI:
            if f in mevcut:
                self.yazi_tipi.addItem(f)
        if not self.yazi_tipi.count():
            self.yazi_tipi.addItem(QFont().family())
        yd.addWidget(self.yazi_tipi)
        self.onizleme = QLabel(" ")
        self.onizleme.setMinimumHeight(90)
        self.onizleme.setAlignment(Qt.AlignCenter)
        self.onizleme.setStyleSheet("background: white; border: 1px solid #d9d9d9;")
        yd.addWidget(self.onizleme)
        self.ad_kutu.textChanged.connect(self._yazi_onizle)
        self.yazi_tipi.currentTextChanged.connect(self._yazi_onizle)
        self.sekmeler.addTab(yaz, "Yaz")

        resim = QWidget()
        rd = QVBoxLayout(resim)
        sec = QPushButton("Resim seç…")
        sec.setAutoDefault(False)
        sec.clicked.connect(self._resim_sec)
        rd.addWidget(sec)
        self.beyaz_kaldir = QCheckBox("Beyaz arka planı kaldır")
        self.beyaz_kaldir.setChecked(True)
        rd.addWidget(self.beyaz_kaldir)
        self.resim_onizleme = QLabel("Henüz resim seçilmedi")
        self.resim_onizleme.setMinimumHeight(120)
        self.resim_onizleme.setAlignment(Qt.AlignCenter)
        self.resim_onizleme.setStyleSheet("background: white; border: 1px solid #d9d9d9;")
        rd.addWidget(self.resim_onizleme)
        self._ham_resim: QImage | None = None
        self.beyaz_kaldir.toggled.connect(self._resim_goster)
        self.sekmeler.addTab(resim, "Resimden")

        self.hata = QLabel()
        self.hata.setStyleSheet("color: #c62828;")
        duzen.addWidget(self.hata)
        kutu = _dugmeler(self, "Kaydet")
        kutu.accepted.disconnect()
        kutu.accepted.connect(self._tamam)
        duzen.addWidget(kutu)

    def _yazi_resmi(self) -> QImage | None:
        metin = self.ad_kutu.text().strip()
        if not metin:
            return None
        yazi = QFont(self.yazi_tipi.currentText())
        yazi.setPixelSize(96)
        olcu = QFontMetrics(yazi).boundingRect(metin)
        img = QImage(olcu.width() + 60, olcu.height() + 60, QImage.Format_ARGB32)
        img.fill(Qt.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        p.setFont(yazi)
        p.setPen(QColor(IMZA_RENKLERI[1][1]))
        p.drawText(30 - olcu.x(), 30 - olcu.y(), metin)
        p.end()
        return icerige_kirp(img)

    def _yazi_onizle(self, *_):
        img = self._yazi_resmi()
        if img is None:
            self.onizleme.setText(" ")
            return
        from PySide6.QtGui import QPixmap
        pix = QPixmap.fromImage(img).scaledToHeight(70, Qt.SmoothTransformation)
        self.onizleme.setPixmap(pix)

    def _resim_sec(self):
        yol, _ = QFileDialog.getOpenFileName(self, "İmza Resmi", "", "Resimler (*.png *.jpg *.jpeg *.bmp)")
        if not yol:
            return
        img = QImage(yol)
        if img.isNull():
            self.hata.setText("Resim açılamadı.")
            return
        self.hata.setText("")
        self._ham_resim = img
        self._resim_goster()

    def _imza_resmi_hazirla(self) -> QImage | None:
        if self._ham_resim is None:
            return None
        if self.beyaz_kaldir.isChecked():
            return beyazi_saydam_yap(self._ham_resim)
        return self._ham_resim.convertToFormat(QImage.Format_ARGB32)

    def _resim_goster(self, *_):
        img = self._imza_resmi_hazirla()
        if img is None:
            return
        from PySide6.QtGui import QPixmap
        self.resim_onizleme.setPixmap(QPixmap.fromImage(img).scaledToHeight(110, Qt.SmoothTransformation))

    def _tamam(self):
        sekme = self.sekmeler.currentIndex()
        if sekme == 0:
            if self.tuval.bos_mu():
                self.hata.setText("Önce imzanızı çizin.")
                return
            img = self.tuval.goruntu()
        elif sekme == 1:
            img = self._yazi_resmi()
            if img is None:
                self.hata.setText("Adınızı yazın.")
                return
        else:
            img = self._imza_resmi_hazirla()
            if img is None:
                self.hata.setText("Bir resim seçin.")
                return
        self._png = png_baytlari(img)
        self.accept()

    def png(self) -> bytes | None:
        return self._png
