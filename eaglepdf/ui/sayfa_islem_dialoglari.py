"""Faz 3 pencereleri: kırp, sayfa boyutu, filigran, arka plan, üstbilgi/altbilgi, sayfa numarası, düzleştir, mühür.

Her pencere `degerler()` ile çekirdek işlevlerin beklediği değerleri verir; hatalı girişte pencere kapanmaz,
Türkçe uyarı gösterir.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QImage, QPainter, QPen, QPixmap, QTransform
from PySide6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFileDialog, QFormLayout,
    QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QRadioButton, QSlider, QSpinBox, QTabWidget,
    QVBoxLayout, QWidget,
)

from ..core.belge import BelgeHatasi, aralik_coz
from ..core.duzenleme import KONUMLAR, SAYFA_NO_BICIMLERI
from ..core.belge import SAYFA_BOYUTLARI
from .dialoglar import icerige_kirp, png_baytlari

BIRIMLER = {"mm": 72 / 25.4, "cm": 72 / 2.54, "inç": 72.0, "pt": 1.0}
KONUM_ADLARI = {"ust-sol": "Üst sol", "ust-orta": "Üst orta", "ust-sag": "Üst sağ",
                "alt-sol": "Alt sol", "alt-orta": "Alt orta", "alt-sag": "Alt sağ"}
MUHUR_RENKLERI = {"ONAYLANDI": "#2e7d32", "REDDEDİLDİ": "#c62828", "TASLAK": "#e65100", "GİZLİ": "#c62828",
                  "ACİL": "#c62828", "KOPYA": "#1565c0", "FİNAL": "#2e7d32", "İNCELENDİ": "#1565c0",
                  "İMZALANDI": "#2e7d32"}


def _dugmeler(pencere: QDialog, tamam: str, kabul=None) -> QDialogButtonBox:
    kutu = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    kutu.button(QDialogButtonBox.Ok).setText(tamam)
    kutu.button(QDialogButtonBox.Cancel).setText("Vazgeç")
    kutu.accepted.connect(kabul or pencere.accept)
    kutu.rejected.connect(pencere.reject)
    return kutu


def _hata_etiketi() -> QLabel:
    e = QLabel()
    e.setStyleSheet("color: #c62828;")
    e.setWordWrap(True)
    return e


class RenkDugmesi(QPushButton):
    def __init__(self, renk: str = "#000000", parent=None):
        super().__init__(parent)
        self.setAutoDefault(False)
        self.setFixedWidth(60)
        self.renk = renk
        self.clicked.connect(self._sec)
        self._boya()

    def _boya(self):
        self.setStyleSheet(f"QPushButton {{ background: {self.renk}; border: 1px solid #9e9e9e; border-radius: 4px; "
                           f"min-height: 20px; }}")

    def _sec(self):
        r = QColorDialog.getColor(QColor(self.renk), self, "Renk Seç")
        if r.isValid():
            self.renk = r.name()
            self._boya()


class AralikKutusu(QGroupBox):
    """“Hangi sayfalara uygulansın?” seçici: tümü / geçerli / seçili / aralık + tek-çift süzgeci."""

    def __init__(self, sayfa_sayisi: int, gecerli: int, secili: list[int], parent=None):
        super().__init__("Sayfalar", parent)
        self.sayfa_sayisi, self.gecerli, self.secili = sayfa_sayisi, gecerli, sorted(secili)
        duzen = QVBoxLayout(self)
        self.tumu = QRadioButton(f"Tüm sayfalar ({sayfa_sayisi})")
        self.gecerli_rb = QRadioButton(f"Geçerli sayfa ({gecerli + 1})")
        self.secili_rb = QRadioButton(f"Seçili sayfalar ({len(self.secili)})")
        self.aralik_rb = QRadioButton("Aralık:")
        self.aralik_kutu = QLineEdit()
        self.aralik_kutu.setPlaceholderText("örn. 1-3, 7, 10-")
        self.secili_rb.setEnabled(len(self.secili) > 1)
        for rb in (self.tumu, self.gecerli_rb, self.secili_rb):
            duzen.addWidget(rb)
        satir = QHBoxLayout()
        satir.addWidget(self.aralik_rb)
        satir.addWidget(self.aralik_kutu, 1)
        duzen.addLayout(satir)
        self.suzgec = QComboBox()
        self.suzgec.addItems(["Hepsi", "Yalnızca tek numaralı sayfalar", "Yalnızca çift numaralı sayfalar"])
        duzen.addWidget(self.suzgec)
        (self.secili_rb if len(self.secili) > 1 else self.tumu).setChecked(True)
        self.aralik_kutu.textEdited.connect(lambda _: self.aralik_rb.setChecked(True))

    def sayfalar(self) -> list[int]:
        if self.tumu.isChecked():
            s = list(range(self.sayfa_sayisi))
        elif self.gecerli_rb.isChecked():
            s = [self.gecerli]
        elif self.secili_rb.isChecked():
            s = list(self.secili)
        else:
            s = aralik_coz(self.aralik_kutu.text(), self.sayfa_sayisi)
        sira = self.suzgec.currentIndex()
        if sira == 1:
            s = [i for i in s if (i + 1) % 2 == 1]
        elif sira == 2:
            s = [i for i in s if (i + 1) % 2 == 0]
        if not s:
            raise BelgeHatasi("Seçimle eşleşen sayfa yok.")
        return s


class _TemelPencere(QDialog):
    """Ortak iskelet: gövde (form), sayfa aralığı kutusu, hata etiketi ve düğmeler."""

    def __init__(self, baslik: str, tamam: str, sayfa_sayisi: int, gecerli: int, secili: list[int],
                 aralik_goster: bool = True, parent=None):
        super().__init__(parent)
        self.setWindowTitle(baslik)
        self.duzen = QVBoxLayout(self)
        self.govde = QVBoxLayout()
        self.duzen.addLayout(self.govde)
        self.aralik = AralikKutusu(sayfa_sayisi, gecerli, secili) if aralik_goster else None
        if self.aralik:
            self.duzen.addWidget(self.aralik)
        self.hata = _hata_etiketi()
        self.duzen.addWidget(self.hata)
        self.duzen.addWidget(_dugmeler(self, tamam, self._tamam))

    def _kontrol(self):
        """Alt sınıf: geçersiz girişte BelgeHatasi fırlatır."""

    def _tamam(self):
        try:
            self._kontrol()
            if self.aralik:
                self.secilen = self.aralik.sayfalar()
        except BelgeHatasi as h:
            self.hata.setText(str(h))
            return
        self.accept()


class KirpPenceresi(_TemelPencere):
    def __init__(self, sayfa_sayisi, gecerli, secili, otomatik_fn=None, parent=None):
        super().__init__("Sayfaları Kırp", "Kırp", sayfa_sayisi, gecerli, secili, parent=parent)
        self.otomatik = False
        form = QFormLayout()
        self.birim = QComboBox()
        self.birim.addItems(list(BIRIMLER))
        form.addRow("Birim:", self.birim)
        self.kutular = {}
        for ad, etiket in (("sol", "Sol"), ("ust", "Üst"), ("sag", "Sağ"), ("alt", "Alt")):
            k = QDoubleSpinBox()
            k.setRange(0, 5000)
            k.setDecimals(2)
            self.kutular[ad] = k
            form.addRow(f"{etiket} kenardan kırp:", k)
        self.govde.addLayout(form)
        self.oto_kutu = QCheckBox("İçeriğe göre otomatik kırp (kenar boşluklarını kaldır)")
        self.oto_kutu.toggled.connect(lambda v: [k.setEnabled(not v) for k in self.kutular.values()])
        self.govde.addWidget(self.oto_kutu)

    def degerler(self) -> dict:
        f = BIRIMLER[self.birim.currentText()]
        return {"otomatik": self.oto_kutu.isChecked(), "sayfalar": self.secilen,
                **{ad: k.value() * f for ad, k in self.kutular.items()}}

    def _kontrol(self):
        if not self.oto_kutu.isChecked() and not any(k.value() for k in self.kutular.values()):
            raise BelgeHatasi("En az bir kenar için kırpma miktarı girin.")


class BoyutPenceresi(_TemelPencere):
    def __init__(self, sayfa_sayisi, gecerli, secili, parent=None):
        super().__init__("Sayfa Boyutu", "Uygula", sayfa_sayisi, gecerli, secili, parent=parent)
        form = QFormLayout()
        self.hazir = QComboBox()
        self.hazir.addItems(list(SAYFA_BOYUTLARI) + ["Özel"])
        self.hazir.setCurrentText("A4")
        self.yatay = QCheckBox("Yatay")
        self.birim = QComboBox()
        self.birim.addItems(["mm", "cm", "inç", "pt"])
        self.en = QDoubleSpinBox()
        self.boy = QDoubleSpinBox()
        for k in (self.en, self.boy):
            k.setRange(1, 5000)
            k.setDecimals(1)
        form.addRow("Boyut:", self.hazir)
        form.addRow("", self.yatay)
        form.addRow("Birim:", self.birim)
        form.addRow("Genişlik:", self.en)
        form.addRow("Yükseklik:", self.boy)
        self.govde.addLayout(form)
        self.govde.addWidget(QLabel("İçerik yeni boyuta ölçeklenir ve ortalanır. Bu sayfalardaki ek açıklamalar ve\n"
                                    "form alanları sayfaya işlenir (artık düzenlenemez); bağlantılar korunmaz."))
        self.hazir.currentTextChanged.connect(self._doldur)
        self.birim.currentTextChanged.connect(lambda _: self._doldur())
        self.yatay.toggled.connect(lambda _: self._doldur())
        self._doldur()

    def _doldur(self, *_):
        ad = self.hazir.currentText()
        ozel = ad == "Özel"
        self.en.setEnabled(ozel)
        self.boy.setEnabled(ozel)
        self.yatay.setEnabled(not ozel)
        if not ozel:
            g, y = SAYFA_BOYUTLARI[ad]
            if self.yatay.isChecked():
                g, y = y, g
            f = BIRIMLER[self.birim.currentText()]
            self.en.setValue(round(g / f, 1))
            self.boy.setValue(round(y / f, 1))

    def degerler(self) -> dict:
        f = BIRIMLER[self.birim.currentText()]
        return {"sayfalar": self.secilen, "genislik": self.en.value() * f, "yukseklik": self.boy.value() * f}


def filigran_resmi_hazirla(yol: str, opaklik: float, aci: float) -> bytes:
    """Resmi `aci` derece (ters saat yönü) döndürüp `opaklik` ile saydamlaştırır; PNG baytları verir."""
    img = QImage(yol)
    if img.isNull():
        raise BelgeHatasi("Resim açılamadı.")
    if max(img.width(), img.height()) > 1600:
        img = img.scaled(1600, 1600, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    img = img.convertToFormat(QImage.Format_ARGB32)
    if aci % 360:
        img = img.transformed(QTransform().rotate(-aci), Qt.SmoothTransformation)
    sonuc = QImage(img.size(), QImage.Format_ARGB32)
    sonuc.fill(Qt.transparent)
    p = QPainter(sonuc)
    p.setOpacity(opaklik)
    p.drawImage(0, 0, img)
    p.end()
    return png_baytlari(sonuc)


class FiligranPenceresi(_TemelPencere):
    def __init__(self, sayfa_sayisi, gecerli, secili, parent=None):
        super().__init__("Filigran Ekle", "Ekle", sayfa_sayisi, gecerli, secili, parent=parent)
        self.sekmeler = QTabWidget()
        self.govde.addWidget(self.sekmeler)
        metin = QWidget()
        mf = QFormLayout(metin)
        self.metin = QLineEdit()
        self.metin.setPlaceholderText("örn. GİZLİ, TASLAK")
        self.boyut = QSpinBox()
        self.boyut.setRange(8, 400)
        self.boyut.setValue(72)
        self.renk = RenkDugmesi("#808080")
        self.kalin = QCheckBox("Kalın")
        self.kalin.setChecked(True)
        mf.addRow("Metin:", self.metin)
        mf.addRow("Yazı boyutu:", self.boyut)
        mf.addRow("Renk:", self.renk)
        mf.addRow("", self.kalin)
        self.sekmeler.addTab(metin, "Metin")
        resim = QWidget()
        rf = QFormLayout(resim)
        self.resim_yolu = QLineEdit()
        self.resim_yolu.setReadOnly(True)
        sec = QPushButton("Seç…")
        sec.setAutoDefault(False)
        sec.clicked.connect(self._resim_sec)
        satir = QHBoxLayout()
        satir.addWidget(self.resim_yolu, 1)
        satir.addWidget(sec)
        self.genislik = QSpinBox()
        self.genislik.setRange(5, 100)
        self.genislik.setValue(50)
        self.genislik.setSuffix(" % (sayfa genişliği)")
        rf.addRow("Resim:", satir)
        rf.addRow("Boyut:", self.genislik)
        self.sekmeler.addTab(resim, "Resim")
        ortak = QFormLayout()
        self.aci = QSpinBox()
        self.aci.setRange(-180, 180)
        self.aci.setValue(45)
        self.aci.setSuffix("°")
        self.opaklik = QSlider(Qt.Horizontal)
        self.opaklik.setRange(5, 100)
        self.opaklik.setValue(30)
        self.opaklik_etiket = QLabel("%30")
        self.opaklik.valueChanged.connect(lambda v: self.opaklik_etiket.setText(f"%{v}"))
        satir2 = QHBoxLayout()
        satir2.addWidget(self.opaklik, 1)
        satir2.addWidget(self.opaklik_etiket)
        self.on_plan = QComboBox()
        self.on_plan.addItems(["İçeriğin arkasında", "İçeriğin üstünde"])
        ortak.addRow("Eğim (ters saat yönü):", self.aci)
        ortak.addRow("Saydamlık (opaklık):", satir2)
        ortak.addRow("Konum:", self.on_plan)
        self.govde.addLayout(ortak)

    def _resim_sec(self):
        yol, _ = QFileDialog.getOpenFileName(self, "Filigran Resmi", "", "Resimler (*.png *.jpg *.jpeg *.bmp)")
        if yol:
            self.resim_yolu.setText(yol)

    def _kontrol(self):
        if self.sekmeler.currentIndex() == 0 and not self.metin.text().strip():
            raise BelgeHatasi("Filigran metnini yazın.")
        if self.sekmeler.currentIndex() == 1:
            if not self.resim_yolu.text():
                raise BelgeHatasi("Bir resim seçin.")
            filigran_resmi_hazirla(self.resim_yolu.text(), 1.0, 0)  # açılabiliyor mu?

    def degerler(self) -> dict:
        ortak = {"sayfalar": self.secilen, "on_plan": self.on_plan.currentIndex() == 0}
        if self.sekmeler.currentIndex() == 0:
            return {**ortak, "tur": "metin", "metin": self.metin.text().strip(), "boyut": self.boyut.value(),
                    "renk": self.renk.renk, "aci": self.aci.value(), "opaklik": self.opaklik.value() / 100,
                    "kalin": self.kalin.isChecked()}
        png = filigran_resmi_hazirla(self.resim_yolu.text(), self.opaklik.value() / 100, self.aci.value())
        return {**ortak, "tur": "resim", "png": png, "genislik_orani": self.genislik.value() / 100}


class KatmanKaldirPenceresi(_TemelPencere):
    """Bu uygulamayla eklenmiş (kendi katmanında duran) içeriği seçilen sayfalardan kaldırma penceresi."""

    def __init__(self, baslik: str, ne: str, sayfa_sayisi, gecerli, secili, bulunan: list[int], parent=None):
        super().__init__(baslik, "Kaldır", sayfa_sayisi, gecerli, secili, parent=parent)
        if bulunan:
            ozet = ", ".join(str(i + 1) for i in bulunan[:12]) + (" …" if len(bulunan) > 12 else "")
            self.govde.addWidget(QLabel(f"{ne} bulunan sayfalar ({len(bulunan)}): {ozet}"))
        else:
            self.govde.addWidget(QLabel(f"Bu belgede, bu uygulamayla eklenmiş {ne.lower()} görünmüyor."))
        self.govde.addWidget(QLabel(f"Seçilen sayfalardaki tüm {ne.lower()} kaldırılır.\n"
                                    "Başka programlarla eklenenlere dokunulmaz."))

    def degerler(self) -> dict:
        return {"sayfalar": self.secilen}


class FiligranKaldirPenceresi(KatmanKaldirPenceresi):
    def __init__(self, sayfa_sayisi, gecerli, secili, filigranli: list[int], parent=None):
        super().__init__("Filigranı Kaldır", "Filigranlar (metin ve resim)", sayfa_sayisi, gecerli, secili, filigranli, parent)


class ArkaPlanPenceresi(_TemelPencere):
    def __init__(self, sayfa_sayisi, gecerli, secili, parent=None):
        super().__init__("Arka Plan", "Uygula", sayfa_sayisi, gecerli, secili, parent=parent)
        self.renk_rb = QRadioButton("Düz renk:")
        self.resim_rb = QRadioButton("Resim:")
        self.renk = RenkDugmesi("#fff8e1")
        self.resim_yolu = QLineEdit()
        self.resim_yolu.setReadOnly(True)
        sec = QPushButton("Seç…")
        sec.setAutoDefault(False)
        sec.clicked.connect(self._sec)
        izgara = QGridLayout()
        izgara.addWidget(self.renk_rb, 0, 0)
        izgara.addWidget(self.renk, 0, 1)
        izgara.addWidget(self.resim_rb, 1, 0)
        izgara.addWidget(self.resim_yolu, 1, 1)
        izgara.addWidget(sec, 1, 2)
        self.govde.addLayout(izgara)
        self.renk_rb.setChecked(True)

    def _sec(self):
        yol, _ = QFileDialog.getOpenFileName(self, "Arka Plan Resmi", "", "Resimler (*.png *.jpg *.jpeg *.bmp)")
        if yol:
            self.resim_yolu.setText(yol)
            self.resim_rb.setChecked(True)

    def _kontrol(self):
        if self.resim_rb.isChecked():
            if not self.resim_yolu.text():
                raise BelgeHatasi("Bir resim seçin.")
            if QImage(self.resim_yolu.text()).isNull():
                raise BelgeHatasi("Resim açılamadı.")

    def degerler(self) -> dict:
        if self.resim_rb.isChecked():
            img = QImage(self.resim_yolu.text()).convertToFormat(QImage.Format_RGB32)
            if max(img.width(), img.height()) > 2400:
                img = img.scaled(2400, 2400, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            return {"sayfalar": self.secilen, "renk": None, "png": png_baytlari(img)}
        return {"sayfalar": self.secilen, "renk": self.renk.renk, "png": None}


class UstAltBilgiPenceresi(_TemelPencere):
    def __init__(self, sayfa_sayisi, gecerli, secili, parent=None):
        super().__init__("Üstbilgi / Altbilgi", "Ekle", sayfa_sayisi, gecerli, secili, parent=parent)
        izgara = QGridLayout()
        izgara.addWidget(QLabel(""), 0, 0)
        for n, ad in enumerate(("Sol", "Orta", "Sağ"), 1):
            izgara.addWidget(QLabel(ad), 0, n)
        self.ust = [QLineEdit() for _ in range(3)]
        self.alt = [QLineEdit() for _ in range(3)]
        izgara.addWidget(QLabel("Üstbilgi:"), 1, 0)
        izgara.addWidget(QLabel("Altbilgi:"), 2, 0)
        for n in range(3):
            izgara.addWidget(self.ust[n], 1, n + 1)
            izgara.addWidget(self.alt[n], 2, n + 1)
        self.govde.addLayout(izgara)
        self.govde.addWidget(QLabel("Yer tutucular: {sayfa}  {toplam}  {tarih}  {dosya}"))
        form = QFormLayout()
        self.boyut = QSpinBox()
        self.boyut.setRange(6, 48)
        self.boyut.setValue(10)
        self.renk = RenkDugmesi("#000000")
        self.kenar = QDoubleSpinBox()
        self.kenar.setRange(10, 200)
        self.kenar.setValue(36)
        self.kenar.setSuffix(" pt")
        form.addRow("Yazı boyutu:", self.boyut)
        form.addRow("Renk:", self.renk)
        form.addRow("Sayfa kenarından uzaklık:", self.kenar)
        self.govde.addLayout(form)

    def _kontrol(self):
        if not any(k.text().strip() for k in self.ust + self.alt):
            raise BelgeHatasi("Üstbilgi ya da altbilgi metni girin.")

    def degerler(self) -> dict:
        return {"sayfalar": self.secilen, "ust": tuple(k.text() for k in self.ust),
                "alt": tuple(k.text() for k in self.alt), "boyut": self.boyut.value(), "renk": self.renk.renk,
                "kenar": self.kenar.value()}


class SayfaNumarasiPenceresi(_TemelPencere):
    def __init__(self, sayfa_sayisi, gecerli, secili, parent=None):
        super().__init__("Sayfa Numarası Ekle", "Ekle", sayfa_sayisi, gecerli, secili, parent=parent)
        form = QFormLayout()
        self.konum = QComboBox()
        for k in KONUMLAR:
            self.konum.addItem(KONUM_ADLARI[k], k)
        self.konum.setCurrentIndex(KONUMLAR.index("alt-orta"))
        self.bicim = QComboBox()
        self.bicim.setEditable(True)
        self.bicim.addItems(list(SAYFA_NO_BICIMLERI))
        self.baslangic = QSpinBox()
        self.baslangic.setRange(0, 99999)
        self.baslangic.setValue(1)
        self.boyut = QSpinBox()
        self.boyut.setRange(6, 48)
        self.boyut.setValue(11)
        self.renk = RenkDugmesi("#000000")
        form.addRow("Konum:", self.konum)
        form.addRow("Biçim ({n}, {toplam}):", self.bicim)
        form.addRow("İlk sayfanın numarası:", self.baslangic)
        form.addRow("Yazı boyutu:", self.boyut)
        form.addRow("Renk:", self.renk)
        self.govde.addLayout(form)

    def _kontrol(self):
        if "{n}" not in self.bicim.currentText():
            raise BelgeHatasi("Biçimde {n} bulunmalı.")

    def degerler(self) -> dict:
        return {"sayfalar": self.secilen, "konum": self.konum.currentData(), "bicim": self.bicim.currentText(),
                "baslangic": self.baslangic.value(), "boyut": self.boyut.value(), "renk": self.renk.renk}


class DuzlestirPenceresi(_TemelPencere):
    def __init__(self, parent=None):
        super().__init__("Düzleştir", "Düzleştir", 1, 0, [], aralik_goster=False, parent=parent)
        self.govde.addWidget(QLabel("Seçilen öğeler sayfa içeriğine işlenir; artık düzenlenemez ya da silinemez.\n"
                                    "(Geri Al ile dönebilirsiniz; kaydettikten sonra dönüş yoktur.)"))
        self.ek = QCheckBox("Ek açıklamalar (vurgu, çizim, not, metin kutusu, mühür…)")
        self.form = QCheckBox("Form alanları (doldurulan değerler sayfaya yazılır)")
        self.ek.setChecked(True)
        self.form.setChecked(True)
        self.govde.addWidget(self.ek)
        self.govde.addWidget(self.form)

    def _kontrol(self):
        if not self.ek.isChecked() and not self.form.isChecked():
            raise BelgeHatasi("En az bir öğe türü seçin.")

    def degerler(self) -> dict:
        return {"ek_aciklamalar": self.ek.isChecked(), "form_alanlari": self.form.isChecked()}


def muhur_resmi(metin: str, renk: str, alt_metin: str = "", cerceve: bool = True) -> QImage:
    """Saydam zeminli, çerçeveli yazı mührü (yüksek çözünürlüklü PNG olarak kullanılır)."""
    buyuk = QFont("Segoe UI")
    buyuk.setBold(True)
    buyuk.setPixelSize(120)
    kucuk = QFont("Segoe UI")
    kucuk.setPixelSize(52)
    fm1, fm2 = QFontMetrics(buyuk), QFontMetrics(kucuk)
    g1 = fm1.horizontalAdvance(metin)
    g2 = fm2.horizontalAdvance(alt_metin) if alt_metin else 0
    ic_gen = max(g1, g2) + 70
    ic_yuk = fm1.height() + (fm2.height() + 8 if alt_metin else 0) + 40
    pay = 16
    img = QImage(ic_gen + 2 * pay, ic_yuk + 2 * pay, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.TextAntialiasing)
    c = QColor(renk)
    p.setPen(QPen(c, 10))
    if cerceve:
        p.drawRoundedRect(pay, pay, ic_gen, ic_yuk, 22, 22)
    y = pay + 20
    p.setFont(buyuk)
    p.drawText(pay, y, ic_gen, fm1.height(), Qt.AlignHCenter | Qt.AlignVCenter, metin)
    if alt_metin:
        p.setFont(kucuk)
        p.drawText(pay, y + fm1.height() + 4, ic_gen, fm2.height(), Qt.AlignHCenter | Qt.AlignVCenter, alt_metin)
    p.end()
    return img


class MuhurPenceresi(QDialog):
    """Özel yazı mührü oluşturur (metin, ikinci satır, renk); kaydedilip Mühür menüsüne eklenir."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Özel Mühür Oluştur")
        duzen = QVBoxLayout(self)
        form = QFormLayout()
        self.metin = QLineEdit()
        self.metin.setPlaceholderText("örn. KABUL EDİLDİ")
        self.alt = QLineEdit()
        self.alt.setPlaceholderText("İkinci satır (isteğe bağlı, örn. 16.10.2026)")
        self.renk = RenkDugmesi("#1565c0")
        self.cerceve = QCheckBox("Çerçeve")
        self.cerceve.setChecked(True)
        form.addRow("Metin:", self.metin)
        form.addRow("İkinci satır:", self.alt)
        form.addRow("Renk:", self.renk)
        form.addRow("", self.cerceve)
        duzen.addLayout(form)
        self.onizleme = QLabel(" ")
        self.onizleme.setAlignment(Qt.AlignCenter)
        self.onizleme.setMinimumHeight(110)
        self.onizleme.setStyleSheet("background: white; border: 1px solid #d9d9d9;")
        duzen.addWidget(self.onizleme)
        self.hata = _hata_etiketi()
        duzen.addWidget(self.hata)
        duzen.addWidget(_dugmeler(self, "Kaydet", self._tamam))
        for w in (self.metin, self.alt):
            w.textChanged.connect(self._onizle)
        self.cerceve.toggled.connect(self._onizle)
        self.renk.clicked.connect(lambda: self._onizle())

    def _onizle(self, *_):
        if not self.metin.text().strip():
            self.onizleme.setText(" ")
            return
        img = muhur_resmi(self.metin.text().strip(), self.renk.renk, self.alt.text().strip(), self.cerceve.isChecked())
        self.onizleme.setPixmap(QPixmap.fromImage(img).scaledToHeight(90, Qt.SmoothTransformation))

    def _tamam(self):
        if not self.metin.text().strip():
            self.hata.setText("Mühür metnini yazın.")
            return
        self.accept()

    def png(self) -> bytes:
        return png_baytlari(muhur_resmi(self.metin.text().strip(), self.renk.renk, self.alt.text().strip(),
                                        self.cerceve.isChecked()))

    def ad(self) -> str:
        return self.metin.text().strip()
