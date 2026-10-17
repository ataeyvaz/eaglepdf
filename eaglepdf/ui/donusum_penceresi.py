"""Dönüştürme / sıkıştırma penceresi: dosya listesi, seçenekler, çıktı klasörü; işlem arka planda çalışır,
ilerleme gösterilir, iptal edilebilir. Aynı pencere tüm dönüştürme türlerini karşılar (bkz. TURLER).
"""

import os
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QThread, QUrl, Qt, Signal
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDoubleSpinBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QProgressBar, QPushButton, QRadioButton, QSpinBox, QVBoxLayout, QWidget, QAbstractItemView,
)

from .. import APP_NAME
from ..core import donustur
from ..core.belge import SAYFA_BOYUTLARI, Belge, BelgeHatasi, aralik_coz
from .dialoglar import dosya_boyutu_metni


@dataclass(frozen=True)
class Tur:
    anahtar: str
    baslik: str
    girdi_filtresi: str
    girdi_uzantilari: tuple[str, ...]
    birlesik: bool = False        # True: tüm dosyalar tek çıktıda birleşir (resimlerden PDF)
    cikti_pdf: bool = False       # çıktı PDF mi (bitince açma önerilir)
    sayfa_secimi: bool = False    # "sayfa aralığı" seçeneği var mı
    parola: bool = False          # PDF girdisi parolalı olabilir


PDF = ("PDF belgeleri (*.pdf)", (".pdf",))
TURLER = {t.anahtar: t for t in (
    Tur("pdf-word", "PDF → Word", *PDF, sayfa_secimi=True, parola=True),
    Tur("pdf-excel", "PDF → Excel", *PDF, sayfa_secimi=True, parola=True),
    Tur("pdf-pptx", "PDF → PowerPoint", *PDF, sayfa_secimi=True, parola=True),
    Tur("pdf-resim", "PDF → Resim", *PDF, sayfa_secimi=True, parola=True),
    Tur("pdf-metin", "PDF → Metin", *PDF, sayfa_secimi=True, parola=True),
    Tur("pdf-html", "PDF → HTML", *PDF, sayfa_secimi=True, parola=True),
    Tur("resim-pdf", "Resimlerden PDF", "Resimler (*.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff *.webp)",
        donustur.GIRDI_RESIM_UZANTILARI, birlesik=True, cikti_pdf=True),
    Tur("word-pdf", "Word → PDF", "Word belgeleri (*.docx)", (".docx",), cikti_pdf=True),
    Tur("excel-pdf", "Excel → PDF", "Excel çalışma kitapları (*.xlsx)", (".xlsx",), cikti_pdf=True),
    Tur("metin-pdf", "Metin → PDF", "Metin dosyaları (*.txt)", (".txt",), cikti_pdf=True),
    Tur("html-pdf", "HTML → PDF", "HTML dosyaları (*.html *.htm)", (".html", ".htm"), cikti_pdf=True),
    Tur("sikistir", "PDF Sıkıştır", *PDF, cikti_pdf=True, parola=True),
)}


class IsParcacigi(QThread):
    """Görevleri sırayla çalıştırır. Görev: `fn(ilerleme_cb) -> (çıktı_yolları, özet)`; iptal edilince `Iptal`."""

    ilerledi = Signal(int, int, str)          # tamamlanan, toplam, şu anki ad
    yuzde = Signal(int)
    dosyaBitti = Signal(int, bool, str, list)  # sıra, başarı, mesaj, çıktılar

    def __init__(self, gorevler: list, parent=None):
        super().__init__(parent)
        self.gorevler = gorevler
        self.iptal_istendi = False

    def iptal(self):
        self.iptal_istendi = True

    def run(self):
        toplam = len(self.gorevler)
        for sira, (ad, fn) in enumerate(self.gorevler):
            if self.iptal_istendi:
                break
            self.ilerledi.emit(sira, toplam, ad)

            def cb(n, t, sira=sira):
                self.yuzde.emit(round((sira + (n / t if t else 1)) / toplam * 100))
                return self.iptal_istendi
            try:
                ciktilar, ozet = fn(cb)
            except donustur.Iptal:
                self.dosyaBitti.emit(sira, False, "İptal edildi.", [])
                break
            except BelgeHatasi as h:
                self.dosyaBitti.emit(sira, False, str(h), [])
            except Exception as h:  # beklenmeyen: kullanıcıya Türkçe, ayrıntıyla göster; diğer dosyalar sürsün
                self.dosyaBitti.emit(sira, False, f"Beklenmeyen hata: {h}", [])
            else:
                self.dosyaBitti.emit(sira, True, ozet, [str(c) for c in ciktilar])
        self.yuzde.emit(100 if not self.iptal_istendi else 0)


class DonusumPenceresi(QDialog):
    def __init__(self, tur: str, dosyalar: list | None = None, klasor: str = "", parent=None, ofis: bool = True):
        super().__init__(parent)
        self._ofis_baslangic = ofis   # Word/Excel → PDF: Office/LibreOffice varsa onu kullan
        self.tur = TURLER[tur]
        self.setWindowTitle(self.tur.baslik)
        self.resize(640, 640)
        self.setAcceptDrops(True)
        self._klasor_baslangic = klasor
        self.ciktilar: list[str] = []
        self.bitti = False
        self.is_parcacigi: IsParcacigi | None = None
        self.acilacak: list[str] = []
        duzen = QVBoxLayout(self)

        self.liste = QListWidget()
        self.liste.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.liste.setDragDropMode(QAbstractItemView.InternalMove)
        duzen.addWidget(QLabel("Dosyalar" + (" (sırayla birleştirilir)" if self.tur.birlesik else "") + ":"))
        duzen.addWidget(self.liste, 1)
        dugme_satiri = QHBoxLayout()
        self.dugmeler_giris: list[QPushButton] = []
        for ad, fn in (("Ekle…", self.dosya_ekle_sor), ("Kaldır", self._kaldir), ("Yukarı", lambda: self._tasi(-1)),
                       ("Aşağı", lambda: self._tasi(1))):
            d = QPushButton(ad)
            d.setAutoDefault(False)
            d.clicked.connect(lambda _=False, f=fn: f())
            dugme_satiri.addWidget(d)
            self.dugmeler_giris.append(d)
        dugme_satiri.addStretch()
        duzen.addLayout(dugme_satiri)

        self.secenekler_kutusu = QGroupBox("Seçenekler")
        self.form = QFormLayout(self.secenekler_kutusu)
        self._secenekleri_kur()
        duzen.addWidget(self.secenekler_kutusu)

        cikti = QGroupBox("Çıktı")
        cd = QVBoxLayout(cikti)
        self.kaynak_klasoru = QRadioButton("Kaynak dosyanın bulunduğu klasör")
        self.secili_klasor = QRadioButton("Şu klasör:")
        self.klasor_kutu = QLineEdit(klasor)
        sec = QPushButton("Seç…")
        sec.setAutoDefault(False)
        sec.clicked.connect(self._klasor_sec)
        satir = QHBoxLayout()
        satir.addWidget(self.secili_klasor)
        satir.addWidget(self.klasor_kutu, 1)
        satir.addWidget(sec)
        cd.addWidget(self.kaynak_klasoru)
        cd.addLayout(satir)
        (self.secili_klasor if klasor else self.kaynak_klasoru).setChecked(True)
        self.klasor_kutu.textEdited.connect(lambda _: self.secili_klasor.setChecked(True))
        self.ac_kutu = QCheckBox("Bitince sonucu aç" if self.tur.cikti_pdf else "Bitince klasörü göster")
        self.ac_kutu.setChecked(self.tur.anahtar != "sikistir")
        cd.addWidget(self.ac_kutu)
        duzen.addWidget(cikti)

        self.sonuclar = QListWidget()
        self.sonuclar.setMaximumHeight(110)
        self.sonuclar.hide()
        duzen.addWidget(self.sonuclar)
        self.ilerleme = QProgressBar()
        self.ilerleme.hide()
        self.durum = QLabel("")
        self.durum.setWordWrap(True)
        duzen.addWidget(self.ilerleme)
        duzen.addWidget(self.durum)
        alt = QHBoxLayout()
        self.klasoru_ac = QPushButton("Klasörü Aç")
        self.klasoru_ac.setAutoDefault(False)
        self.klasoru_ac.hide()
        self.klasoru_ac.clicked.connect(self._klasoru_ac)
        self.baslat_dugme = QPushButton("Dönüştür" if self.tur.anahtar != "sikistir" else "Sıkıştır")
        self.baslat_dugme.setDefault(True)
        self.baslat_dugme.clicked.connect(self.basla)
        self.kapat_dugme = QPushButton("Kapat")
        self.kapat_dugme.setAutoDefault(False)
        self.kapat_dugme.clicked.connect(self._kapat)
        alt.addWidget(self.klasoru_ac)
        alt.addStretch()
        alt.addWidget(self.baslat_dugme)
        alt.addWidget(self.kapat_dugme)
        duzen.addLayout(alt)
        for yol in dosyalar or []:
            self.dosya_ekle(yol)

    # --- dosya listesi ---
    def dosya_ekle(self, yol) -> bool:
        yol = Path(yol)
        if yol.suffix.lower() not in self.tur.girdi_uzantilari or not yol.is_file():
            return False
        for i in range(self.liste.count()):
            if self.liste.item(i).data(Qt.UserRole) == str(yol):
                return False
        oge = QListWidgetItem(f"{yol.name}    ({dosya_boyutu_metni(yol.stat().st_size)})")
        oge.setData(Qt.UserRole, str(yol))
        oge.setToolTip(str(yol))
        self.liste.addItem(oge)
        return True

    def dosya_ekle_sor(self):
        yollar, _ = QFileDialog.getOpenFileNames(self, "Dosya Ekle", self._klasor_baslangic, self.tur.girdi_filtresi)
        for y in yollar:
            self.dosya_ekle(y)

    def dosyalar(self) -> list[Path]:
        return [Path(self.liste.item(i).data(Qt.UserRole)) for i in range(self.liste.count())]

    def _kaldir(self):
        for o in self.liste.selectedItems():
            self.liste.takeItem(self.liste.row(o))

    def _tasi(self, yon: int):
        satirlar = sorted((self.liste.row(o) for o in self.liste.selectedItems()), reverse=yon > 0)
        for r in satirlar:
            h = r + yon
            if 0 <= h < self.liste.count() and not self.liste.item(h).isSelected():
                oge = self.liste.takeItem(r)
                self.liste.insertItem(h, oge)
                oge.setSelected(True)

    def dragEnterEvent(self, olay):
        if olay.mimeData().hasUrls():
            olay.acceptProposedAction()

    def dropEvent(self, olay):
        for u in olay.mimeData().urls():
            self.dosya_ekle(u.toLocalFile())

    def _klasor_sec(self):
        k = QFileDialog.getExistingDirectory(self, "Çıktı Klasörü", self.klasor_kutu.text() or self._klasor_baslangic)
        if k:
            self.klasor_kutu.setText(k)
            self.secili_klasor.setChecked(True)

    # --- seçenekler ---
    def _secenekleri_kur(self):
        t = self.tur.anahtar
        f = self.form
        self.sayfalar_kutu = QLineEdit()
        self.sayfalar_kutu.setPlaceholderText("Boş = tüm sayfalar; örn. 1-3, 7, 10-")
        self.parola_kutu = QLineEdit()
        self.parola_kutu.setEchoMode(QLineEdit.Password)
        self.parola_kutu.setPlaceholderText("Yalnızca parolalı dosyalar için")
        if self.tur.sayfa_secimi:
            f.addRow("Sayfalar:", self.sayfalar_kutu)
        if self.tur.parola:
            f.addRow("Parola:", self.parola_kutu)
        if t == "pdf-excel":
            self.sayi_kutu = QCheckBox("Sayıları algıla (1.234,50 → sayı olarak yaz)")
            self.sayi_kutu.setChecked(True)
            f.addRow("", self.sayi_kutu)
            f.addRow("", QLabel("Sayfalardaki tablolar ayrı çalışma sayfalarına yazılır; tablo yoksa metin satırları alınır."))
        elif t == "pdf-pptx":
            self.pptx_mod = QComboBox()
            self.pptx_mod.addItem("Düzenlenebilir (metin kutuları + arka plan görüntüsü)", "duzenlenebilir")
            self.pptx_mod.addItem("Yalnızca resim (her sayfa bir resim)", "resim")
            f.addRow("Biçim:", self.pptx_mod)
        elif t == "pdf-resim":
            self.bicim_kutu = QComboBox()
            self.bicim_kutu.addItems(["png", "jpg", "bmp", "tiff"])
            self.dpi_kutu = QSpinBox()
            self.dpi_kutu.setRange(36, 600)
            self.dpi_kutu.setValue(150)
            self.dpi_kutu.setSuffix(" DPI")
            self.renk_kutu = QComboBox()
            self.renk_kutu.addItem("Renkli", "renkli")
            self.renk_kutu.addItem("Gri tonlama", "gri")
            self.renk_kutu.addItem("Siyah-beyaz", "siyahbeyaz")
            self.tek_kutu = QCheckBox("Tüm sayfaları alt alta tek uzun resimde birleştir")
            f.addRow("Resim biçimi:", self.bicim_kutu)
            f.addRow("Çözünürlük:", self.dpi_kutu)
            f.addRow("Renk:", self.renk_kutu)
            f.addRow("", self.tek_kutu)
        elif t == "pdf-metin":
            self.ayrac_kutu = QCheckBox("Sayfalar arasına “— Sayfa N —” başlığı koy")
            self.ayrac_kutu.setChecked(True)
            f.addRow("", self.ayrac_kutu)
        elif t == "resim-pdf":
            self.boyut_kutu = QComboBox()
            for ad in SAYFA_BOYUTLARI:
                self.boyut_kutu.addItem(ad, ad)
            self.boyut_kutu.addItem("Resim boyutunda", "resim")
            self.yon_kutu = QComboBox()
            self.yon_kutu.addItem("Otomatik (resme göre)", "otomatik")
            self.yon_kutu.addItem("Dikey", "dikey")
            self.yon_kutu.addItem("Yatay", "yatay")
            self.kenar_kutu = QDoubleSpinBox()
            self.kenar_kutu.setRange(0, 100)
            self.kenar_kutu.setSuffix(" mm")
            self.ayri_kutu = QCheckBox("Her resim için ayrı PDF oluştur")
            self.ad_kutu = QLineEdit()
            self.ad_kutu.setPlaceholderText("Boş = ilk resmin adı / “Resimler”")
            f.addRow("Sayfa boyutu:", self.boyut_kutu)
            f.addRow("Yön:", self.yon_kutu)
            f.addRow("Kenar boşluğu:", self.kenar_kutu)
            f.addRow("PDF adı:", self.ad_kutu)
            f.addRow("", self.ayri_kutu)
            self.ayri_kutu.toggled.connect(lambda v: self.ad_kutu.setEnabled(not v))
        elif t == "sikistir":
            self.seviye_kutu = QComboBox()
            self.seviye_kutu.addItem("Düşük — kalite kaybı yok (yalnızca gereksiz veriyi atar)", "dusuk")
            self.seviye_kutu.addItem("Orta — resimler 130 dpi'ye indirilir (önerilen)", "orta")
            self.seviye_kutu.addItem("Yüksek — resimler 80 dpi'ye indirilir (en küçük dosya)", "yuksek")
            self.seviye_kutu.setCurrentIndex(1)
            f.addRow("Sıkıştırma:", self.seviye_kutu)
            f.addRow("", QLabel("Özgün dosyanız değişmez; sonuç “…_sikistirilmis.pdf” olarak yeni dosyaya yazılır."))
        elif t in ("word-pdf", "excel-pdf"):
            from ..core import ofis
            motorlar = ofis.durum().motorlar("word" if t == "word-pdf" else "excel")
            self.ofis_kutu = QCheckBox("Bilgisayardaki Office/LibreOffice ile dönüştür (sayfa düzeni birebir)")
            self.ofis_kutu.setChecked(self._ofis_baslangic and bool(motorlar))
            self.ofis_kutu.setEnabled(bool(motorlar))
            f.addRow("", self.ofis_kutu)
            f.addRow("", QLabel(("Bulundu: " + ", ".join(motorlar) + ". Dosya yalnızca bu bilgisayarda, salt okunur açılıp çevrilir; "
                                 "ağa gönderilmez.") if motorlar else
                                "Microsoft Office ya da LibreOffice bulunamadı; yerleşik dönüştürücü kullanılacak."))
            if t == "word-pdf":
                f.addRow("", QLabel("Yerleşik dönüştürücü: başlık, paragraf, liste, tablo, resim ve temel biçim korunur;\n"
                                    "sayfa düzeni (üst/alt bilgi, sütun, metin kutusu) birebir gelmeyebilir."))
            else:
                f.addRow("", QLabel("Yerleşik dönüştürücü: her çalışma sayfası bir tablo olarak yazılır; formüller son\n"
                                    "hesaplanan değerleriyle gelir. Çok sütunlu sayfalar yatay basılır."))
        if f.rowCount() == 0:
            self.secenekler_kutusu.hide()

    # --- çalıştırma ---
    def _cikti_klasoru(self, kaynak: Path) -> Path:
        if self.secili_klasor.isChecked() and self.klasor_kutu.text().strip():
            return Path(self.klasor_kutu.text().strip())
        return kaynak.parent

    def _sayfa_secimi(self, yol: Path, parola: str | None):
        metin = self.sayfalar_kutu.text().strip() if self.tur.sayfa_secimi else ""
        if not metin:
            return None
        b = Belge.ac(yol, parola)
        try:
            return aralik_coz(metin, b.sayfa_sayisi)
        finally:
            b.kapat()

    def gorevleri_olustur(self) -> list:
        """Pencere değerlerinden görev listesi üretir: [(ad, fn(ilerleme) -> (çıktılar, özet))] (ana iş parçacığında)."""
        t = self.tur.anahtar
        dosyalar = self.dosyalar()
        if not dosyalar:
            raise BelgeHatasi("Önce en az bir dosya ekleyin.")
        parola = self.parola_kutu.text() or None if self.tur.parola else None
        if t == "resim-pdf":
            klasor = self._cikti_klasoru(dosyalar[0])
            ad = self.ad_kutu.text().strip() or None
            return [(f"{len(dosyalar)} resim", lambda il: (donustur.resimlerden_pdf(
                dosyalar, klasor, ad, self.boyut_kutu.currentData(), self.yon_kutu.currentData(),
                self.kenar_kutu.value() * 72 / 25.4, self.ayri_kutu.isChecked(), il), ""))]
        sayfa_metni = self.sayfalar_kutu.text().strip() if self.tur.sayfa_secimi else ""
        if sayfa_metni:  # sayfa aralığı hatasını işlem başlamadan göster
            self._sayfa_secimi(dosyalar[0], parola)
        secenek = self._secenek_degerleri()
        gorevler = []
        for yol in dosyalar:
            klasor = self._cikti_klasoru(yol)
            gorevler.append((yol.name, self._gorev(t, yol, klasor, parola, sayfa_metni, secenek)))
        return gorevler

    def _secenek_degerleri(self) -> dict:
        t = self.tur.anahtar
        if t == "pdf-excel":
            return {"sayi": self.sayi_kutu.isChecked()}
        if t == "pdf-pptx":
            return {"mod": self.pptx_mod.currentData()}
        if t == "pdf-resim":
            return {"bicim": self.bicim_kutu.currentText(), "dpi": self.dpi_kutu.value(),
                    "renk": self.renk_kutu.currentData(), "tek": self.tek_kutu.isChecked()}
        if t == "pdf-metin":
            return {"ayrac": self.ayrac_kutu.isChecked()}
        if t == "sikistir":
            return {"seviye": self.seviye_kutu.currentData()}
        if t in ("word-pdf", "excel-pdf"):
            return {"ofis": self.ofis_kutu.isChecked()}
        return {}

    def _gorev(self, t: str, yol: Path, klasor: Path, parola, sayfa_metni: str, s: dict):
        def sayfalar():
            if not sayfa_metni:
                return None
            b = Belge.ac(yol, parola)
            try:
                return aralik_coz(sayfa_metni, b.sayfa_sayisi)
            finally:
                b.kapat()

        def gorev(il):
            if t == "pdf-word":
                return [donustur.pdf_word(yol, klasor, sayfalar(), parola, il)], ""
            if t == "pdf-excel":
                dosya, adet = donustur.pdf_excel(yol, klasor, sayfalar(), s["sayi"], parola, il)
                return [dosya], (f"{adet} tablo" if adet else "tablo bulunamadı; metin satırları alındı")
            if t == "pdf-pptx":
                return [donustur.pdf_pptx(yol, klasor, sayfalar(), s["mod"], 150, parola, il)], ""
            if t == "pdf-resim":
                c = donustur.pdf_resim(yol, klasor, s["bicim"], s["dpi"], s["renk"], sayfalar(), s["tek"], parola, 90, il)
                return c, f"{len(c)} resim"
            if t == "pdf-metin":
                return [donustur.pdf_metin(yol, klasor, sayfalar(), s["ayrac"], parola, il)], ""
            if t == "pdf-html":
                return [donustur.pdf_html(yol, klasor, sayfalar(), parola, il)], ""
            if t in ("word-pdf", "excel-pdf"):
                hedef, ileti = donustur.ofisle_pdf("word" if t == "word-pdf" else "excel", yol, klasor, il, s.get("ofis", True))
                return [hedef], ileti
            if t == "metin-pdf":
                return [donustur.metinden_pdf(yol, klasor, il)], ""
            if t == "html-pdf":
                return [donustur.html_dosyasindan_pdf(yol, klasor, il)], ""
            if t == "sikistir":
                hedef, r = donustur.sikistir(yol, klasor, s["seviye"], parola, il)
                if r.kucultuldu:
                    return [hedef], f"{dosya_boyutu_metni(r.eski_boyut)} → {dosya_boyutu_metni(r.yeni_boyut)} (%{round(r.kazanc_orani * 100)} küçüldü)"
                return [hedef], "dosya zaten en küçük hâlinde; özgün kopyalandı"
            raise BelgeHatasi(f"Bilinmeyen tür: {t}")
        return gorev

    def _girisleri_kilitle(self, kilitli: bool):
        for w in (self.liste, self.secenekler_kutusu, self.baslat_dugme, *self.dugmeler_giris):
            w.setEnabled(not kilitli)

    def basla(self):
        if self.is_parcacigi is not None:
            return
        try:
            gorevler = self.gorevleri_olustur()
        except BelgeHatasi as h:
            self.durum.setText(f"⚠ {h}")
            self.durum.setStyleSheet("color: #c62828;")
            return
        self.durum.setStyleSheet("")
        self.sonuclar.clear()
        self.sonuclar.show()
        self.ilerleme.show()
        self.ilerleme.setValue(0)
        self.ciktilar = []
        self.bitti = False
        self.klasoru_ac.hide()
        self._girisleri_kilitle(True)
        self.baslat_dugme.hide()
        self.kapat_dugme.setText("İptal")
        self.is_parcacigi = IsParcacigi(gorevler, self)
        self.is_parcacigi.ilerledi.connect(lambda n, t, ad: self.durum.setText(f"İşleniyor ({n + 1}/{t}): {ad}"))
        self.is_parcacigi.yuzde.connect(self.ilerleme.setValue)
        self.is_parcacigi.dosyaBitti.connect(self._dosya_bitti)
        self.is_parcacigi.finished.connect(self._hepsi_bitti)
        self._gorev_adlari = [ad for ad, _ in gorevler]
        self.is_parcacigi.start()

    def _dosya_bitti(self, sira: int, basarili: bool, mesaj: str, ciktilar: list):
        ad = self._gorev_adlari[sira]
        oge = QListWidgetItem(("✓ " if basarili else "✗ ") + ad + (f" — {mesaj}" if mesaj else ""))
        oge.setForeground(QColor("#2e7d32" if basarili else "#c62828"))
        if ciktilar:
            oge.setToolTip("\n".join(ciktilar))
        self.sonuclar.addItem(oge)
        self.sonuclar.scrollToBottom()
        self.ciktilar += ciktilar

    def _hepsi_bitti(self):
        iptal = self.is_parcacigi.iptal_istendi if self.is_parcacigi else False
        self.is_parcacigi = None
        self.bitti = True
        self._girisleri_kilitle(False)
        self.baslat_dugme.show()
        self.baslat_dugme.setText("Yeniden Dönüştür" if self.tur.anahtar != "sikistir" else "Yeniden Sıkıştır")
        self.kapat_dugme.setText("Kapat")
        basarili = sum(1 for i in range(self.sonuclar.count()) if self.sonuclar.item(i).text().startswith("✓"))
        toplam = len(self._gorev_adlari)
        if iptal:
            self.durum.setText(f"İptal edildi. {basarili} işlem tamamlanmıştı.")
        elif basarili == toplam:
            self.durum.setText(f"Tamamlandı: {basarili} işlem başarılı.")
        else:
            self.durum.setText(f"Bitti: {basarili}/{toplam} başarılı, {toplam - basarili} hata (ayrıntı yukarıda).")
        if self.ciktilar:
            self.klasoru_ac.show()
            if self.ac_kutu.isChecked():
                self.acilacak = list(self.ciktilar)

    def _klasoru_ac(self):
        if self.ciktilar:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(self.ciktilar[-1]).parent)))

    def _kapat(self):
        if self.is_parcacigi is not None:
            self.is_parcacigi.iptal()
            self.durum.setText("İptal ediliyor…")
            self.kapat_dugme.setEnabled(False)
            self.is_parcacigi.finished.connect(lambda: self.kapat_dugme.setEnabled(True))
            return
        self.accept() if self.ciktilar else self.reject()

    def reject(self):
        if self.is_parcacigi is not None:  # Esc/çarpı ile kapatırken önce iptal
            self._kapat()
            return
        super().reject()

    def closeEvent(self, olay):
        if self.is_parcacigi is not None:
            self.is_parcacigi.iptal()
            self.is_parcacigi.wait(5000)
        super().closeEvent(olay)
