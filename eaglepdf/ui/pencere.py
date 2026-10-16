"""Ana pencere: başlık şeridi, menüler, araç çubuğu, paneller ve görüntüleyici."""

from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMainWindow, QMessageBox, QSpinBox, QSplitter,
    QStatusBar, QTabWidget, QToolBar, QVBoxLayout, QWidget, QLineEdit,
)

from .. import APP_NAME, PAKET_ADI
from ..core import belge as belge_modulu
from ..core.belge import Belge, BelgeHatasi, ParolaGerekli
from . import theme
from .goruntuleyici import Goruntuleyici
from .hakkinda import HakkindaPenceresi
from .paneller import KucukResimler, YerImleri
from .sayfa_dialoglari import BirlestirPenceresi, BolPenceresi
from .yardim import YardimPenceresi

PDF_FILTRESI = "PDF belgeleri (*.pdf)"
SON_KULLANILAN_SAYISI = 8


class AnaPencere(QMainWindow):
    def __init__(self):
        super().__init__()
        self.belge: Belge | None = None
        self.ayarlar = QSettings(QSettings.IniFormat, QSettings.UserScope, APP_NAME, APP_NAME)
        self._sonuclar: list = []
        self._sonuc_no = -1
        self.setAcceptDrops(True)
        self.resize(1200, 800)
        self._arayuz_kur()
        self._menuleri_kur()
        self._durumu_guncelle()

    # --- kurulum ---
    def _arayuz_kur(self):
        merkez = QWidget()
        merkez.setObjectName("central")
        self.setCentralWidget(merkez)
        dikey = QVBoxLayout(merkez)
        dikey.setContentsMargins(0, 0, 0, 0)
        dikey.setSpacing(0)

        baslik = QWidget()
        baslik.setObjectName("header")
        satir = QHBoxLayout(baslik)
        satir.setContentsMargins(14, 7, 14, 7)
        self.belge_adi = QLabel(APP_NAME)
        self.belge_adi.setObjectName("belgeAdi")
        self.belge_durum = QLabel("")
        self.belge_durum.setObjectName("belgeDurum")
        satir.addWidget(self.belge_adi)
        satir.addWidget(self.belge_durum)
        satir.addStretch()
        satir.addWidget(QLabel(PAKET_ADI))
        dikey.addWidget(baslik)

        self.arac = QToolBar()
        self.arac.setMovable(False)
        dikey.addWidget(self.arac)

        self.bul_cubugu = QWidget()
        bul = QHBoxLayout(self.bul_cubugu)
        bul.setContentsMargins(8, 4, 8, 4)
        self.bul_kutu = QLineEdit()
        self.bul_kutu.setPlaceholderText("Belgede ara…")
        self.bul_kutu.setClearButtonEnabled(True)
        self.bul_kutu.returnPressed.connect(self._bul_enter)
        self.bul_kutu.textChanged.connect(self._bul_degisti)
        self.bul_bilgi = QLabel("")
        bul.addWidget(self.bul_kutu, 1)
        bul.addWidget(self.bul_bilgi)
        self.bul_cubugu.hide()
        dikey.addWidget(self.bul_cubugu)

        self.kucuk = KucukResimler()
        self.yer_imleri = YerImleri()
        self.paneller = QTabWidget()
        self.paneller.addTab(self.kucuk, "Küçük Resimler")
        self.paneller.addTab(self.yer_imleri, "Yer İmleri")
        self.goruntuleyici = Goruntuleyici()
        self.ayirac = QSplitter(Qt.Horizontal)
        self.ayirac.addWidget(self.paneller)
        self.ayirac.addWidget(self.goruntuleyici)
        self.ayirac.setStretchFactor(1, 1)
        self.ayirac.setSizes([210, 990])
        dikey.addWidget(self.ayirac, 1)

        self.setStatusBar(QStatusBar())
        self.sayfa_bilgi = QLabel("")
        self.olcek_bilgi = QLabel("")
        self.statusBar().addPermanentWidget(self.sayfa_bilgi)
        self.statusBar().addPermanentWidget(self.olcek_bilgi)

        self.kucuk.sayfaSecildi.connect(self.goruntuleyici.git)
        self.yer_imleri.sayfaSecildi.connect(self.goruntuleyici.git)
        self.kucuk.siraDegisti.connect(self._sira_degisti)
        self.goruntuleyici.sayfaDegisti.connect(self._sayfa_degisti)
        self.goruntuleyici.olcekDegisti.connect(lambda o: self.olcek_bilgi.setText(f"%{round(o * 100)}"))

    def _eylem(self, metin, fn, kisayol=None, ipucu=None):
        e = QAction(metin, self)
        if kisayol:
            e.setShortcut(QKeySequence(kisayol))
        if ipucu:
            e.setStatusTip(ipucu)
        e.triggered.connect(lambda *_: fn())
        self.addAction(e)
        return e

    def _menuleri_kur(self):
        mb = self.menuBar()
        # Dosya
        self.e_ac = self._eylem("Aç…", self.ac_sor, "Ctrl+O")
        self.e_kaydet = self._eylem("Kaydet", self.kaydet, "Ctrl+S", "Açık dosyanın üzerine yazar (onay ister)")
        self.e_farkli = self._eylem("Farklı Kaydet…", self.farkli_kaydet, "Ctrl+Shift+S")
        self.e_ozellik = self._eylem("Belge Özellikleri…", self.ozellikleri_goster)
        self.e_kapat = self._eylem("Kapat", self.kapat, "Ctrl+W")
        self.e_cik = self._eylem("Çıkış", self.close, "Alt+F4")
        dosya = mb.addMenu("&Dosya")
        dosya.addAction(self.e_ac)
        self.son_menu = dosya.addMenu("Son Kullanılanlar")
        dosya.addSeparator()
        for e in (self.e_kaydet, self.e_farkli):
            dosya.addAction(e)
        dosya.addSeparator()
        dosya.addAction(self.e_ozellik)
        dosya.addSeparator()
        dosya.addAction(self.e_kapat)
        dosya.addAction(self.e_cik)
        self._son_menusu_doldur()

        # Düzen
        self.e_ara = self._eylem("Ara…", self.ara_ac, "Ctrl+F")
        self.e_sonraki = self._eylem("Sonraki Sonuç", lambda: self._sonuca_git(1), "F3")
        self.e_onceki = self._eylem("Önceki Sonuç", lambda: self._sonuca_git(-1), "Shift+F3")
        duzen = mb.addMenu("&Düzen")
        for e in (self.e_ara, self.e_sonraki, self.e_onceki):
            duzen.addAction(e)

        # Görünüm
        self.e_yakin = self._eylem("Yakınlaştır", lambda: self.goruntuleyici.olcek_ata(self.goruntuleyici.olcek * 1.25), "Ctrl++")
        self.e_uzak = self._eylem("Uzaklaştır", lambda: self.goruntuleyici.olcek_ata(self.goruntuleyici.olcek / 1.25), "Ctrl+-")
        self.e_yuzde100 = self._eylem("%100", lambda: self.goruntuleyici.olcek_ata(1.0), "Ctrl+0")
        self.e_genislik = self._eylem("Genişliğe Sığdır", self.goruntuleyici.genislige_sigdir, "Ctrl+1")
        self.e_sayfaya = self._eylem("Sayfaya Sığdır", self.goruntuleyici.sayfaya_sigdir, "Ctrl+2")
        self.e_panel = self._eylem("Sol Paneli Göster/Gizle", lambda: self.paneller.setVisible(not self.paneller.isVisible()), "F4")
        self.e_tam = self._eylem("Tam Ekran", self._tam_ekran, "F11")
        gorunum = mb.addMenu("&Görünüm")
        for e in (self.e_yakin, self.e_uzak, self.e_yuzde100, self.e_genislik, self.e_sayfaya):
            gorunum.addAction(e)
        gorunum.addSeparator()
        gorunum.addAction(self.e_panel)
        gorunum.addAction(self.e_tam)

        # Sayfa
        self.e_sil = self._eylem("Sayfaları Sil", self.sayfalari_sil, "Del")
        self.e_cikar = self._eylem("Sayfaları Çıkar…", self.sayfalari_cikar)
        self.e_sol = self._eylem("Sola Döndür", lambda: self.dondur(-90), "Ctrl+[")
        self.e_sag = self._eylem("Sağa Döndür", lambda: self.dondur(90), "Ctrl+]")
        self.e_bos = self._eylem("Boş Sayfa Ekle", self.bos_sayfa_ekle)
        self.e_ekle = self._eylem("PDF Ekle (Sona)…", self.pdf_ekle)
        self.e_birlestir = self._eylem("Birleştir…", self.birlestir)
        self.e_bol = self._eylem("Böl…", self.bol)
        sayfa = mb.addMenu("&Sayfa")
        for e in (self.e_sil, self.e_cikar):
            sayfa.addAction(e)
        sayfa.addSeparator()
        for e in (self.e_sol, self.e_sag, self.e_bos, self.e_ekle):
            sayfa.addAction(e)
        sayfa.addSeparator()
        sayfa.addAction(self.e_birlestir)
        sayfa.addAction(self.e_bol)

        # Yardım
        self.e_yardim = self._eylem("Nasıl Kullanılır", lambda: self.yardim(), "F1")
        self.e_kisayol = self._eylem("Klavye Kısayolları", lambda: self.yardim("kisayollar"))
        self.e_hakkinda = self._eylem(f"{APP_NAME} Hakkında", lambda: HakkindaPenceresi(self).exec())
        yardim = mb.addMenu("&Yardım")
        for e in (self.e_yardim, self.e_kisayol):
            yardim.addAction(e)
        yardim.addSeparator()
        yardim.addAction(self.e_hakkinda)

        # Araç çubuğu
        for e in (self.e_ac, self.e_farkli):
            self.arac.addAction(e)
        self.arac.addSeparator()
        for e in (self.e_uzak, self.e_yakin, self.e_genislik, self.e_sayfaya):
            self.arac.addAction(e)
        self.arac.addSeparator()
        self.arac.addWidget(QLabel("Sayfa "))
        self.sayfa_kutu = QSpinBox()
        self.sayfa_kutu.setMinimum(1)
        self.sayfa_kutu.setKeyboardTracking(False)
        self.sayfa_kutu.valueChanged.connect(lambda v: self.goruntuleyici.git(v - 1))
        self.arac.addWidget(self.sayfa_kutu)
        self.toplam_etiket = QLabel(" / 0")
        self.arac.addWidget(self.toplam_etiket)
        self.arac.addSeparator()
        for e in (self.e_sol, self.e_sag, self.e_sil):
            self.arac.addAction(e)
        self.arac.addAction(self.e_ara)

        self._belge_eylemleri = [self.e_kaydet, self.e_farkli, self.e_ozellik, self.e_kapat, self.e_ara, self.e_sonraki,
                                 self.e_onceki, self.e_yakin, self.e_uzak, self.e_yuzde100, self.e_genislik,
                                 self.e_sayfaya, self.e_sil, self.e_cikar, self.e_sol, self.e_sag, self.e_bos,
                                 self.e_ekle, self.e_bol]

    # --- belge açma/kapama ---
    def ac_sor(self):
        if not self._kapatmaya_izin():
            return
        yol, _ = QFileDialog.getOpenFileName(self, "PDF Aç", self.ayarlar.value("son_klasor", ""), PDF_FILTRESI)
        if yol:
            self.ac(yol, kontrol_edildi=True)

    def ac(self, yol, kontrol_edildi=False):
        if not kontrol_edildi and not self._kapatmaya_izin():
            return
        parola = None
        while True:
            try:
                yeni = Belge.ac(yol, parola)
                break
            except ParolaGerekli as h:
                parola, tamam = QInputDialog.getText(self, "Parola Gerekli", f"{h}\nParolayı girin:", QLineEdit.Password)
                if not tamam:
                    return
            except BelgeHatasi as h:
                QMessageBox.warning(self, APP_NAME, str(h))
                return
        self._belgeyi_kapat_sessiz()
        self.belge = yeni
        self.ayarlar.setValue("son_klasor", str(Path(yol).parent))
        self._son_ekle(str(Path(yol)))
        self._belge_goster(0)
        self.goruntuleyici.genislige_sigdir()

    def _belgeyi_kapat_sessiz(self):
        if self.belge:
            self.goruntuleyici.belge_ata(None)
            self.kucuk.belge_ata(None)
            self.yer_imleri.belge_ata(None)
            self.belge.kapat()
            self.belge = None
        self._sonuclar, self._sonuc_no = [], -1

    def kapat(self):
        if self._kapatmaya_izin():
            self._belgeyi_kapat_sessiz()
            self._durumu_guncelle()

    def _belge_goster(self, sayfa: int):
        """Belge değiştiğinde (açılış, sayfa işlemi) tüm görünümleri tazeler."""
        self.goruntuleyici.belge_ata(self.belge, sayfa)
        self.kucuk.belge_ata(self.belge)
        self.yer_imleri.belge_ata(self.belge)
        self.kucuk.vurgula(min(sayfa, self.belge.sayfa_sayisi - 1))
        self._sonuclar, self._sonuc_no = [], -1
        self._durumu_guncelle()

    def _durumu_guncelle(self):
        var = self.belge is not None
        for e in self._belge_eylemleri:
            e.setEnabled(var)
        for w in (self.sayfa_kutu, self.paneller):
            w.setEnabled(var)
        if not var:
            self.belge_adi.setText(APP_NAME)
            self.belge_durum.setText("")
            self.setWindowTitle(APP_NAME)
            self.sayfa_bilgi.setText("")
            self.toplam_etiket.setText(" / 0")
            self.bul_cubugu.hide()
            self.statusBar().showMessage("Bir PDF açmak için Ctrl+O ya da dosyayı buraya sürükleyin.")
            return
        if self.statusBar().currentMessage().startswith("Bir PDF açmak"):
            self.statusBar().clearMessage()
        ad = self.belge.yol.name if self.belge.yol else "Adsız"
        self.belge_adi.setText(ad)
        self.belge_durum.setText("· değişti" if self.belge.degisti else "")
        self.setWindowTitle(f"{'* ' if self.belge.degisti else ''}{ad} — {APP_NAME}")
        n = self.belge.sayfa_sayisi
        self.sayfa_kutu.setMaximum(n)
        self.toplam_etiket.setText(f" / {n}")
        self.sayfa_bilgi.setText(f"{self.goruntuleyici.gecerli_sayfa + 1} / {n}  ")
        self.olcek_bilgi.setText(f"%{round(self.goruntuleyici.olcek * 100)}")

    def _sayfa_degisti(self, i: int):
        self.sayfa_kutu.blockSignals(True)
        self.sayfa_kutu.setValue(i + 1)
        self.sayfa_kutu.blockSignals(False)
        self.kucuk.vurgula(i)
        if self.belge:
            self.sayfa_bilgi.setText(f"{i + 1} / {self.belge.sayfa_sayisi}  ")

    # --- kayıt ---
    def kaydet(self) -> bool:
        if not self.belge:
            return False
        if not self.belge.yol:
            return self.farkli_kaydet()
        if QMessageBox.question(
            self, "Üzerine Yaz", f"“{self.belge.yol.name}” dosyasının üzerine yazılsın mı?\nOrijinal dosya değişecek.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        ) != QMessageBox.Yes:
            return False
        return self._yaz(self.belge.yol, uzerine_yaz=True)

    def farkli_kaydet(self) -> bool:
        if not self.belge:
            return False
        varsayilan = Path(self.ayarlar.value("son_klasor", "")) / (
            (self.belge.yol.stem + " (düzenlendi).pdf") if self.belge.yol else "Adsız.pdf")
        yol, _ = QFileDialog.getSaveFileName(self, "Farklı Kaydet", str(varsayilan), PDF_FILTRESI)
        if not yol:
            return False
        yol = Path(yol if yol.lower().endswith(".pdf") else yol + ".pdf")
        # Seçilen yer açık dosyaysa kullanıcı Windows'un üzerine-yaz sorusunu zaten onayladı
        return self._yaz(yol, uzerine_yaz=bool(self.belge.yol and yol.resolve() == self.belge.yol.resolve()))

    def _yaz(self, yol: Path, uzerine_yaz: bool) -> bool:
        try:
            self.belge.kaydet(yol, uzerine_yaz=uzerine_yaz)
        except (BelgeHatasi, OSError) as h:
            QMessageBox.warning(self, APP_NAME, f"Kaydedilemedi:\n{h}")
            return False
        self.statusBar().showMessage(f"Kaydedildi: {yol}", 5000)
        self._son_ekle(str(yol))
        self._durumu_guncelle()
        return True

    def _kapatmaya_izin(self) -> bool:
        if not self.belge or not self.belge.degisti:
            return True
        kutu = QMessageBox(QMessageBox.Question, APP_NAME, "Belgede kaydedilmemiş değişiklikler var.", parent=self)
        farkli = kutu.addButton("Farklı Kaydet…", QMessageBox.AcceptRole)
        atla = kutu.addButton("Kaydetmeden Kapat", QMessageBox.DestructiveRole)
        kutu.addButton("Vazgeç", QMessageBox.RejectRole)
        kutu.exec()
        if kutu.clickedButton() is farkli:
            return self.farkli_kaydet()
        return kutu.clickedButton() is atla

    def closeEvent(self, olay):
        if self._kapatmaya_izin():
            self._belgeyi_kapat_sessiz()
            olay.accept()
        else:
            olay.ignore()

    # --- son kullanılanlar ---
    def _son_liste(self) -> list[str]:
        v = self.ayarlar.value("son_dosyalar", [])
        return [v] if isinstance(v, str) else list(v or [])

    def _son_ekle(self, yol: str):
        liste = [yol] + [y for y in self._son_liste() if y != yol]
        self.ayarlar.setValue("son_dosyalar", liste[:SON_KULLANILAN_SAYISI])
        self._son_menusu_doldur()

    def _son_menusu_doldur(self):
        self.son_menu.clear()
        liste = [y for y in self._son_liste() if Path(y).exists()]
        for y in liste:
            self.son_menu.addAction(Path(y).name, lambda y=y: self.ac(y)).setStatusTip(y)
        self.son_menu.setEnabled(bool(liste))

    # --- sürükle-bırak ---
    def dragEnterEvent(self, olay):
        if olay.mimeData().hasUrls() and any(u.toLocalFile().lower().endswith(".pdf") for u in olay.mimeData().urls()):
            olay.acceptProposedAction()

    def dropEvent(self, olay):
        for u in olay.mimeData().urls():
            if u.toLocalFile().lower().endswith(".pdf"):
                self.ac(u.toLocalFile())
                break

    # --- sayfa işlemleri ---
    def _hedef_sayfalar(self) -> list[int]:
        sec = self.kucuk.secili_sayfalar()
        return sec or [self.goruntuleyici.gecerli_sayfa]

    def _islem(self, fn, *argumanlar, sayfa: int | None = None) -> bool:
        """Bellekteki belgeye bir işlem uygular, görünümleri tazeler."""
        try:
            fn(*argumanlar)
        except BelgeHatasi as h:
            QMessageBox.warning(self, APP_NAME, str(h))
            return False
        gidilecek = self.goruntuleyici.gecerli_sayfa if sayfa is None else sayfa
        self._belge_goster(max(0, min(gidilecek, self.belge.sayfa_sayisi - 1)))
        return True

    def sayfalari_sil(self):
        if not self.belge:
            return
        sayfalar = self._hedef_sayfalar()
        if QMessageBox.question(
            self, "Sayfaları Sil", f"{len(sayfalar)} sayfa silinsin mi? (Kaydedene dek dosya değişmez.)",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        ) == QMessageBox.Yes:
            self._islem(self.belge.sayfa_sil, sayfalar, sayfa=sayfalar[0])

    def sayfalari_cikar(self):
        if not self.belge:
            return
        sayfalar = self._hedef_sayfalar()
        yol, _ = QFileDialog.getSaveFileName(
            self, "Sayfaları Çıkar", str(Path(self.ayarlar.value("son_klasor", "")) / "cikarilan.pdf"), PDF_FILTRESI)
        if not yol:
            return
        try:
            self.belge.sayfalari_kaydet(sayfalar, yol if yol.lower().endswith(".pdf") else yol + ".pdf")
        except (BelgeHatasi, OSError) as h:
            QMessageBox.warning(self, APP_NAME, str(h))
            return
        self.statusBar().showMessage(f"{len(sayfalar)} sayfa çıkarıldı: {yol}", 5000)

    def dondur(self, aci: int):
        if self.belge:
            self._islem(self.belge.sayfa_dondur, self._hedef_sayfalar(), aci)

    def bos_sayfa_ekle(self):
        if self.belge:
            g = self.goruntuleyici.gecerli_sayfa
            self._islem(self.belge.bos_sayfa_ekle, g, "A4", sayfa=g + 1)

    def pdf_ekle(self):
        if not self.belge:
            return
        yol, _ = QFileDialog.getOpenFileName(self, "Eklenecek PDF", self.ayarlar.value("son_klasor", ""), PDF_FILTRESI)
        if yol:
            self._islem(self.belge.sona_ekle, yol, sayfa=self.belge.sayfa_sayisi)

    def _sira_degisti(self, yeni_sira: list):
        if self.belge:
            self._islem(self.belge.sirala, yeni_sira, sayfa=0)

    def birlestir(self):
        baslangic = [str(self.belge.yol)] if self.belge and self.belge.yol else []
        pencere = BirlestirPenceresi(self, baslangic, self.ayarlar.value("son_klasor", ""))
        if not pencere.exec():
            return
        yollar = pencere.yollar()
        yol, _ = QFileDialog.getSaveFileName(
            self, "Birleştirilmiş PDF", str(Path(self.ayarlar.value("son_klasor", "")) / "birlesik.pdf"), PDF_FILTRESI)
        if not yol:
            return
        try:
            n = belge_modulu.birlestir(yollar, yol if yol.lower().endswith(".pdf") else yol + ".pdf")
        except (BelgeHatasi, OSError) as h:
            QMessageBox.warning(self, APP_NAME, str(h))
            return
        self.statusBar().showMessage(f"{len(yollar)} dosya birleştirildi ({n} sayfa): {yol}", 8000)

    def bol(self):
        if not self.belge:
            return
        if not self.belge.yol:
            QMessageBox.information(self, APP_NAME, "Bölmek için önce belgeyi kaydedin.")
            return
        if self.belge.degisti:
            QMessageBox.information(self, APP_NAME, "Bölme, kayıtlı dosya üzerinde çalışır. Önce değişiklikleri kaydedin.")
            return
        pencere = BolPenceresi(self.belge.sayfa_sayisi, self)
        if not pencere.exec():
            return
        klasor = QFileDialog.getExistingDirectory(self, "Parçaların yazılacağı klasör", str(self.belge.yol.parent))
        if not klasor:
            return
        try:
            yazilan = belge_modulu.bol(self.belge.yol, klasor, parcalar=pencere.parcalar)
        except (BelgeHatasi, OSError) as h:
            QMessageBox.warning(self, APP_NAME, str(h))
            return
        self.statusBar().showMessage(f"{len(yazilan)} dosya yazıldı: {klasor}", 8000)

    # --- arama ---
    def ara_ac(self):
        if not self.belge:
            return
        self.bul_cubugu.show()
        self.bul_kutu.setFocus()
        self.bul_kutu.selectAll()

    def _bul_enter(self):
        if self._sonuclar:
            self._sonuca_git(1)
        else:
            self._bul_degisti(self.bul_kutu.text())

    def _bul_degisti(self, metin: str):
        if not self.belge:
            return
        self._sonuclar = self.belge.ara(metin)
        self._sonuc_no = 0 if self._sonuclar else -1
        self.goruntuleyici.vurgulari_ata(self._sonuclar, self._sonuc_no)
        self._bul_bilgi_yaz(bool(metin.strip()))

    def _sonuca_git(self, yon: int):
        if not self._sonuclar:
            return
        self._sonuc_no = (self._sonuc_no + yon) % len(self._sonuclar)
        self.goruntuleyici.vurgulari_ata(self._sonuclar, self._sonuc_no)
        self._bul_bilgi_yaz(True)

    def _bul_bilgi_yaz(self, arandi: bool):
        if self._sonuclar:
            self.bul_bilgi.setText(f"{self._sonuc_no + 1} / {len(self._sonuclar)}")
        else:
            self.bul_bilgi.setText("Sonuç yok" if arandi else "")

    def keyPressEvent(self, olay):
        if olay.key() == Qt.Key_Escape and self.bul_cubugu.isVisible():
            self.bul_cubugu.hide()
            self.goruntuleyici.vurgulari_ata([])
            self.goruntuleyici.setFocus()
        else:
            super().keyPressEvent(olay)

    # --- diğer ---
    def ozellikleri_goster(self):
        if not self.belge:
            return
        satirlar = "\n".join(f"{k}: {v}" for k, v in self.belge.ozellikler().items() if v)
        QMessageBox.information(self, "Belge Özellikleri", satirlar or "Bilgi yok.")

    def _tam_ekran(self):
        self.showNormal() if self.isFullScreen() else self.showFullScreen()

    def yardim(self, konu: str | None = None):
        YardimPenceresi(self, konu).exec()

    def showEvent(self, olay):
        super().showEvent(olay)
        if not getattr(self, "_baslik_boyandi", False):
            self._baslik_boyandi = True
            theme.color_title_bar(self)
