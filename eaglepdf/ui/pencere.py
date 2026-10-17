"""Ana pencere: başlık şeridi, menüler, araç çubuğu, paneller ve görüntüleyici."""

import os
import subprocess
from contextlib import contextmanager
from pathlib import Path

from PySide6.QtCore import QSettings, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QActionGroup, QDesktopServices, QIcon, QIntValidator, QKeySequence
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMainWindow, QMessageBox, QSpinBox, QSplitter,
    QStatusBar, QTabWidget, QToolBar, QVBoxLayout, QWidget, QLineEdit, QApplication, QProgressDialog, QTabBar, QToolButton, QMenu,
)

from .. import APP_NAME, PAKET_ADI
from ..core import belge as belge_modulu
from ..core.belge import Belge, BelgeHatasi, ParolaGerekli
from . import simgeler, theme
from .aciklama_arayuzu import AciklamaArayuzu
from .donusum_arayuzu import DonusumArayuzu
from .koruma_arayuzu import KorumaArayuzu
from .ayarlar_penceresi import AyarlarPenceresi, _dogru_mu
from .imza_arayuzu import ImzaArayuzu
from .sekme_cubugu import SekmeCubugu
from .tek_ornek import TekOrnekSunucu
from ..core import gecmis as gecmis_modulu
from .oturum import BUYUK_BELGE_BAYT, EN_COK_SEKME, BelgeOturumu, sekme_basligi, sekme_ipucu
from .ozellikler_penceresi import OzelliklerPenceresi
from .toplu_yazdir import TopluYazdirPenceresi, toplu_yazdir
from .ocr_arayuzu import OcrArayuzu
from .duzenleme_arayuzu import DuzenlemeArayuzu
from .goruntuleyici import ARAC_EL, ARAC_SEC, MOD_SUREKLI, MOD_TEK, Goruntuleyici
from .hakkinda import HakkindaPenceresi
from .paneller import KucukResimler, YerImleri
from .sayfa_dialoglari import BirlestirPenceresi, BolPenceresi
from .yazdir import sayfalari_yazdir
from .yardim import YardimPenceresi

PDF_FILTRESI = "PDF belgeleri (*.pdf)"
SON_KULLANILAN_SAYISI = 8


class SayfaKutusu(QLineEdit):
    """Araç çubuğundaki sayfa numarası kutusu (QSpinBox'ın düz biçimi Fusion'da boş kalıyor)."""

    valueChanged = Signal(int)

    def __init__(self):
        super().__init__("1")
        self._en_cok = 1
        self.setFixedWidth(52)
        self.setAlignment(Qt.AlignCenter)
        self.setValidator(QIntValidator(1, 999999, self))
        self.editingFinished.connect(self._bitti)

    def setMaximum(self, n: int):
        self._en_cok = max(1, n)

    def setValue(self, v: int):
        self.setText(str(v))

    def value(self) -> int:
        return int(self.text() or 1)

    def _bitti(self):
        v = max(1, min(self.value(), self._en_cok))
        self.setText(str(v))
        self.valueChanged.emit(v)


def ayarlari_ac(ayar_dosyasi: str | None = None) -> QSettings:
    """Uygulama ayarları (INI). Başlatıcı (`main.py`) ve pencere aynı dosyayı kullanır."""
    return (QSettings(ayar_dosyasi, QSettings.IniFormat) if ayar_dosyasi
            else QSettings(QSettings.IniFormat, QSettings.UserScope, APP_NAME, APP_NAME))


class AnaPencere(ImzaArayuzu, OcrArayuzu, KorumaArayuzu, DonusumArayuzu, DuzenlemeArayuzu, AciklamaArayuzu, QMainWindow):
    def __init__(self, ayar_dosyasi: str | None = None):
        super().__init__()
        self._oturumlar: list[BelgeOturumu] = []   # açık belgeler (sekmeler); şimdilik en çok 1
        self._etkin = -1                           # etkin oturumun sırası, yoksa -1
        self._mesgul = 0                           # >0: uzun işlem sürüyor, sekme değişimi yok sayılır
        self._geciste = False                      # sekme geçişi sürerken tekrar girişi önler
        self.ayarlar = ayarlari_ac(ayar_dosyasi)
        self.tek_ornek: TekOrnekSunucu | None = None   # çalışan örnek sunucusu (başlatıcı atar)
        self.tek_ornek_destegi = False                 # True: ayar değişince sunucu açılıp kapanır (yalnızca main.py açar)
        self._bekleyen_yollar: list[str] = []          # işlem sürerken gelen açma istekleri
        self._sonuclar: list = []
        self._sonuc_no = -1
        self.setAcceptDrops(True)
        self.resize(1200, 800)
        self._arayuz_kur()
        self._menuleri_kur()
        self.gorunumu_yukle()
        self._durumu_guncelle()

    # --- belge oturumları ---
    @property
    def belge(self) -> Belge | None:
        """Etkin oturumun belgesi (yoksa None). Pencere ve karışımlardaki tüm okumalar bunu kullanır."""
        return self._oturumlar[self._etkin].belge if 0 <= self._etkin < len(self._oturumlar) else None

    @belge.setter
    def belge(self, deger: Belge | None):
        """None → tüm oturumları bırakır; Belge → etkin oturumun belgesini değiştirir (yoksa yeni oturum açar).
        Belgeleri kapatmaz (çağıran kapatır)."""
        if deger is None:
            self._oturumlar, self._etkin = [], -1
        elif self._etkin >= 0:
            self._oturumlar[self._etkin] = BelgeOturumu(deger)
        else:
            self._oturumlar, self._etkin = [BelgeOturumu(deger)], 0

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
        self.arac.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.arac.setIconSize(QSize(20, 20))
        dikey.addWidget(self.arac)

        self.sekmeler = SekmeCubugu()   # açık belgeler; belge yokken gizli
        self.sekmeler.setObjectName("belgeSekmeleri")
        self.sekmeler.setTabsClosable(False)   # ✕ düğmesini kendimiz koyarız (temaya uygun, düz simge)
        self.sekmeler.setMovable(True)
        self.sekmeler.setExpanding(False)
        self.sekmeler.setDocumentMode(True)
        self.sekmeler.setElideMode(Qt.ElideRight)
        self.sekmeler.setUsesScrollButtons(True)
        self.sekmeler.tabMoved.connect(self._sekme_tasindi)
        self.sekmeler.currentChanged.connect(self._sekme_secildi)
        self.sekmeler.tabCloseRequested.connect(self._sekme_kapat)
        self.sekmeler.ortaTiklandi.connect(self._sekme_kapat)
        self.sekmeler.setContextMenuPolicy(Qt.CustomContextMenu)
        self.sekmeler.customContextMenuRequested.connect(self._sekme_sag_tik)
        self.sekmeler.hide()
        dikey.addWidget(self.sekmeler)

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
        self.yer_imleri = YerImleri(lambda: self.goruntuleyici.gecerli_sayfa)
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

    def _eylem(self, metin, fn, kisayol=None, ipucu=None, simge=None, isaretli=None):
        e = QAction(metin, self)
        if simge:
            e.setIcon(simgeler.simge(simge))
        if isaretli is not None:
            e.setCheckable(True)
            e.setChecked(isaretli)
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
        self.e_ac = self._eylem("Aç…", self.ac_sor, "Ctrl+O", simge="ac")
        self.e_kaydet = self._eylem("Kaydet", self.kaydet, "Ctrl+S", "Açık dosyanın üzerine yazar (onay ister)")
        self.e_farkli = self._eylem("Farklı Kaydet…", self.farkli_kaydet, "Ctrl+Shift+S", simge="kaydet")
        self.e_yazdir = self._eylem("Yazdır…", self.yazdir, "Ctrl+P", simge="yazdir")
        self.e_toplu_yazdir = self._eylem("Toplu Yazdır…", self.toplu_yazdir_ac, simge="yazdir")
        self.e_ozellik = self._eylem("Belge Özellikleri…", self.ozellikleri_goster)
        self.e_ayarlar = self._eylem("Ayarlar…", self.ayarlar_ac, "Ctrl+,")
        self.e_kapat = self._eylem("Kapat", self.kapat, "Ctrl+W")
        self.e_tumunu_kapat = self._eylem("Tümünü Kapat", self.tum_sekmeleri_kapat, "Ctrl+Shift+W")
        self.e_cik = self._eylem("Çıkış", self.close, "Alt+F4")
        dosya = mb.addMenu("&Dosya")
        dosya.addAction(self.e_ac)
        self.son_menu = dosya.addMenu("Son Kullanılanlar")
        dosya.addSeparator()
        for e in (self.e_kaydet, self.e_farkli):
            dosya.addAction(e)
        dosya.addSeparator()
        dosya.addAction(self.e_yazdir)
        dosya.addAction(self.e_toplu_yazdir)
        dosya.addAction(self.e_ozellik)
        dosya.addSeparator()
        dosya.addAction(self.e_ayarlar)
        dosya.addAction(self.e_kapat)
        dosya.addAction(self.e_tumunu_kapat)
        dosya.addAction(self.e_cik)
        self._son_menusu_doldur()

        # Düzen
        self.e_ara = self._eylem("Ara…", self.ara_ac, "Ctrl+F", simge="ara")
        self.e_sonraki = self._eylem("Sonraki Sonuç", lambda: self._sonuca_git(1), "F3")
        self.e_onceki = self._eylem("Önceki Sonuç", lambda: self._sonuca_git(-1), "Shift+F3")
        self.e_kopyala = self._eylem("Seçili Metni Kopyala", self.kopyala, "Ctrl+C", simge="kopyala")
        duzen = self.m_duzen = mb.addMenu("&Düzen")
        duzen.addAction(self.e_kopyala)
        duzen.addSeparator()
        for e in (self.e_ara, self.e_sonraki, self.e_onceki):
            duzen.addAction(e)

        # Görünüm
        self.e_yakin = self._eylem("Yakınlaştır", lambda: self.goruntuleyici.olcek_ata(self.goruntuleyici.olcek * 1.25), "Ctrl++", simge="yakinlastir")
        self.e_uzak = self._eylem("Uzaklaştır", lambda: self.goruntuleyici.olcek_ata(self.goruntuleyici.olcek / 1.25), "Ctrl+-", simge="uzaklastir")
        self.e_yuzde100 = self._eylem("%100", lambda: self.goruntuleyici.olcek_ata(1.0), "Ctrl+0")
        self.e_genislik = self._eylem("Genişliğe Sığdır", self.goruntuleyici.genislige_sigdir, "Ctrl+1", simge="genislik")
        self.e_sayfaya = self._eylem("Sayfaya Sığdır", self.goruntuleyici.sayfaya_sigdir, "Ctrl+2", simge="sayfa")
        self.e_panel = self._eylem("Sol Paneli Göster/Gizle", lambda: self.paneller.setVisible(not self.paneller.isVisible()), "F4")
        self.e_tam = self._eylem("Tam Ekran", self._tam_ekran, "F11")
        g = self.goruntuleyici
        self.e_surekli = self._eylem("Sürekli Kaydırma", self._gorunum_uygula, simge="sureklu", isaretli=g.mod == MOD_SUREKLI)
        self.e_tek = self._eylem("Tek Sayfa", self._gorunum_uygula, simge="tek", isaretli=g.mod == MOD_TEK)
        self.e_cift = self._eylem("Çift Sayfa (yan yana)", self._gorunum_uygula, simge="cift", isaretli=g.sutun == 2)
        mod_grup = QActionGroup(self)
        for e in (self.e_surekli, self.e_tek):
            mod_grup.addAction(e)
        self.e_el = self._eylem("El Aracı", self._arac_uygula, simge="el", isaretli=True)
        self.e_sec = self._eylem("Metin Seçme Aracı", self._arac_uygula, simge="imlec", isaretli=False)
        arac_grup = self._arac_grubu = QActionGroup(self)
        for e in (self.e_el, self.e_sec):
            arac_grup.addAction(e)
        self._arac_eylemleri = {"el": self.e_el, "sec": self.e_sec}
        self.e_gece = self._eylem("Gece Modu", self._gece_uygula, simge="gece", isaretli=False)
        gorunum = self.m_gorunum = mb.addMenu("&Görünüm")
        for e in (self.e_yakin, self.e_uzak, self.e_yuzde100, self.e_genislik, self.e_sayfaya):
            gorunum.addAction(e)
        gorunum.addSeparator()
        for e in (self.e_surekli, self.e_tek, self.e_cift):
            gorunum.addAction(e)
        gorunum.addSeparator()
        for e in (self.e_el, self.e_sec):
            gorunum.addAction(e)
        gorunum.addSeparator()
        gorunum.addAction(self.e_gece)
        gorunum.addAction(self.e_panel)
        gorunum.addSeparator()
        self.e_sonraki_sekme = self._eylem("Sonraki Sekme", lambda: self.sekme_gez(1))
        self.e_sonraki_sekme.setShortcuts([QKeySequence("Ctrl+Tab"), QKeySequence("Ctrl+PgDown")])
        self.e_onceki_sekme = self._eylem("Önceki Sekme", lambda: self.sekme_gez(-1))
        self.e_onceki_sekme.setShortcuts([QKeySequence("Ctrl+Shift+Tab"), QKeySequence("Ctrl+PgUp")])
        gorunum.addAction(self.e_sonraki_sekme)
        gorunum.addAction(self.e_onceki_sekme)
        gorunum.addAction(self.e_tam)

        # Sayfa
        self.e_sil = self._eylem("Sayfaları Sil", self.sayfalari_sil, "Del", simge="sil")
        self.e_cikar = self._eylem("Sayfaları Çıkar…", self.sayfalari_cikar)
        self.e_sol = self._eylem("Sola Döndür", lambda: self.dondur(-90), "Ctrl+[", simge="sola")
        self.e_sag = self._eylem("Sağa Döndür", lambda: self.dondur(90), "Ctrl+]", simge="saga")
        self.e_bos = self._eylem("Boş Sayfa Ekle", self.bos_sayfa_ekle, simge="boslu")
        self.e_ekle = self._eylem("PDF Ekle (Sona)…", self.pdf_ekle)
        self.e_birlestir = self._eylem("Birleştir…", self.birlestir, simge="birlestir")
        self.e_bol = self._eylem("Böl…", self.bol, simge="bol")
        sayfa = self.m_sayfa = mb.addMenu("&Sayfa")
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
        for e in (self.e_ac, self.e_farkli, self.e_yazdir):
            self.arac.addAction(e)
        self.arac.addSeparator()
        for e in (self.e_el, self.e_sec):
            self.arac.addAction(e)
        self.arac.addSeparator()
        for e in (self.e_uzak, self.e_yakin, self.e_genislik, self.e_sayfaya):
            self.arac.addAction(e)
        self.arac.addSeparator()
        self.arac.addWidget(QLabel("Sayfa "))
        self.sayfa_kutu = SayfaKutusu()
        self.sayfa_kutu.valueChanged.connect(lambda v: self.goruntuleyici.git(v - 1))
        self.arac.addWidget(self.sayfa_kutu)
        self.toplam_etiket = QLabel(" / 0")
        self.arac.addWidget(self.toplam_etiket)
        self.arac.addSeparator()
        for e in (self.e_sol, self.e_sag, self.e_sil):
            self.arac.addAction(e)
        self.arac.addSeparator()
        for e in (self.e_gece, self.e_ara):
            self.arac.addAction(e)

        self._belge_eylemleri = [self.e_yazdir, self.e_kopyala, self.e_kaydet, self.e_farkli, self.e_ozellik, self.e_kapat, self.e_tumunu_kapat, self.e_ara, self.e_sonraki,
                                 self.e_onceki, self.e_yakin, self.e_uzak, self.e_yuzde100, self.e_genislik,
                                 self.e_sayfaya, self.e_sil, self.e_cikar, self.e_sol, self.e_sag, self.e_bos,
                                 self.e_ekle, self.e_bol]
        self._aciklama_kur()
        self._duzenleme_kur()
        self._donusum_kur()
        self._ocr_kur()
        self._koruma_kur()
        self._imza_kur()

    # --- belge açma/kapama ---
    def ac_sor(self):
        yollar, _ = QFileDialog.getOpenFileNames(self, "PDF Aç", self.ayarlar.value("son_klasor", ""), PDF_FILTRESI)
        self.ac_coklu(yollar)

    def ac_coklu(self, yollar) -> int:
        """Birden çok dosyayı sekmelerde açar. Sınır aşılırsa kalanlar *tek* uyarıyla atlanır. Açılan/öne alınan sayıyı döndürür."""
        acilan = atlanan = 0
        for yol in yollar:
            if self._oturum_bul(yol) < 0 and len(self._oturumlar) >= EN_COK_SEKME:
                atlanan += 1
                continue
            self.ac(yol)
            acilan += 1 if self._oturum_bul(yol) >= 0 else 0   # açılamayan (bozuk/yok) sayılmaz
        if atlanan:
            QMessageBox.information(self, APP_NAME, f"En çok {EN_COK_SEKME} belge aynı anda açık olabilir; {atlanan} dosya "
                                                    "açılmadı. Sekme kapatıp yeniden deneyin.")
        return acilan

    # --- tek örnek ---
    def tek_ornek_istegi(self, yollar: list):
        """Başka bir başlatma (çift tık, “Birlikte aç”) dosyalarını bu pencereye yolladı: öne getir, sekmelerde aç."""
        self.setWindowState((self.windowState() & ~Qt.WindowMinimized) | Qt.WindowActive)
        self.raise_()
        self.activateWindow()
        QApplication.alert(self)
        if yollar:
            self.ac_coklu(yollar)

    def _tek_ornek_ayarla(self):
        """Ayardaki tek pencere tercihini çalışan uygulamaya uygular (yalnızca başlatıcı destek bayrağını açtıysa)."""
        if not self.tek_ornek_destegi:
            return
        acik = _dogru_mu(self.ayarlar.value("tek_ornek", True))
        if acik and self.tek_ornek is None:
            sunucu = TekOrnekSunucu()
            if sunucu.baslat():
                sunucu.istekGeldi.connect(self.tek_ornek_istegi)
                self.tek_ornek = sunucu
        elif not acik and self.tek_ornek is not None:
            self.tek_ornek.durdur()
            self.tek_ornek = None

    # --- oturum (açık sekmelerin hatırlanması) ---
    def oturumu_kaydet(self):
        """Açık sekmelerin yollarını ve etkin olanı ayarlara yazar (pencere kapanırken)."""
        self.ayarlar.setValue("son_oturum", [str(o.belge.yol) for o in self._oturumlar if o.belge.yol])
        self.ayarlar.setValue("son_oturum_etkin", str(self.belge.yol) if self.belge and self.belge.yol else "")

    def oturumu_geri_yukle(self) -> int:
        """Son oturumdaki sekmeleri sessizce açar (bulunamayan, parolalı ya da bozuk dosyalar atlanır). Açık sekme sayısını döndürür."""
        v = self.ayarlar.value("son_oturum", [])
        yollar = [v] if isinstance(v, str) else list(v or [])
        for y in yollar:
            if y and Path(y).is_file():
                self.ac(y, sessiz=True)
        etkin = str(self.ayarlar.value("son_oturum_etkin", "") or "")
        if etkin and self._oturum_bul(etkin) >= 0:
            self._etkinlestir(self._oturum_bul(etkin))
        return len(self._oturumlar)

    def _acik_dosya_engeli(self, yol, kendisi_serbest: bool = False) -> bool:
        """`yol` bir sekmede açıksa kullanıcıyı uyarır ve True döner (üzerine yazmak Windows kilidi/bayat belge yaratır).
        `kendisi_serbest`: etkin sekmenin kendi dosyası engel sayılmaz (Farklı Kaydet aynı yola onayla yazabilir)."""
        sira = self._oturum_bul(yol)
        if sira < 0 or (kendisi_serbest and sira == self._etkin):
            return False
        QMessageBox.warning(self, APP_NAME, f"“{Path(yol).name}” bir sekmede açık. Önce o sekmeyi kapatın ya da başka bir ad seçin.")
        return True

    def _oturum_bul(self, yol) -> int:
        """`yol` zaten bir sekmede açıksa sırası, değilse -1."""
        return next((i for i, o in enumerate(self._oturumlar) if o.ayni_dosya_mi(yol)), -1)

    def ac(self, yol, yeniden=False, sessiz=False):
        """Dosyayı yeni sekmede açar; zaten açıksa o sekmeye geçer.
        `yeniden=True`: açık sekmedeki belge diskten yeniden yüklenir (kayıttan sonra gibi). Açmak mevcut belgeyi kapatmaz.
        `sessiz=True` (oturum geri yükleme): parola sorulmaz, hata/sınır uyarısı gösterilmez, sorunlu dosya atlanır.
        Uzun bir işlem sürerken (OCR, toplu yazdırma) açma isteği kuyruğa alınır; işlem bitince açılır."""
        if self._mesgul:
            self._bekleyen_yollar.append(str(yol))
            self.statusBar().showMessage("Bir işlem sürüyor; dosya işlem bitince açılacak.", 4000)
            return
        sira = self._oturum_bul(yol)
        if sira >= 0 and not yeniden:
            self._etkinlestir(sira)
            self.statusBar().showMessage(f"{Path(yol).name} zaten açık; o sekmeye geçildi.", 4000)
            return
        if sira < 0 and len(self._oturumlar) >= EN_COK_SEKME:
            if not sessiz:
                QMessageBox.information(self, APP_NAME, f"En çok {EN_COK_SEKME} belge aynı anda açık olabilir. "
                                                        "Yeni belge açmadan önce bir sekmeyi kapatın.")
            return
        parola = None
        while True:
            try:
                yeni = Belge.ac(yol, parola)
                break
            except ParolaGerekli as h:
                if sessiz:
                    return
                parola, tamam = QInputDialog.getText(self, "Parola Gerekli", f"{h}\nParolayı girin:", QLineEdit.Password)
                if not tamam:
                    return
            except BelgeHatasi as h:
                if not sessiz:
                    QMessageBox.warning(self, APP_NAME, str(h))
                return
        self._durum_kaydet()
        if sira >= 0:   # yeniden yükleme: aynı sekmenin belgesi değişir
            self._etkin = sira
            self.goruntuleyici.belge_ata(None)
            self.kucuk.belge_ata(None)
            self.yer_imleri.belge_ata(None)
            self._oturumlar[sira].belge.kapat()
            self._oturumlar[sira] = BelgeOturumu(yeni, olcek=self.goruntuleyici.olcek)
        else:
            self._oturumlar.append(BelgeOturumu(yeni, olcek=self.goruntuleyici.olcek))
            self._etkin = len(self._oturumlar) - 1
        self.ayarlar.setValue("son_klasor", str(Path(yol).parent))
        self._son_ekle(str(Path(yol)))
        self._oturumu_goster(self._oturumlar[self._etkin])
        self._acilis_yakinlastirma()
        self.statusBar().clearMessage()   # önceki belgenin bilgi mesajı (ör. büyük belge) yenisinde kalmasın
        boyut = Path(yol).stat().st_size
        if boyut > BUYUK_BELGE_BAYT:
            self.statusBar().showMessage(f"Büyük belge ({boyut // (1024 * 1024)} MB): bellek için geri al adımları sınırlanabilir.", 8000)

    # --- sekme geçişi ---
    def _durum_kaydet(self):
        """Etkin oturumun belgeye özgü görünüm durumunu (sayfa, ölçek, arama, panel sekmesi) oturuma yazar;
        sekme değişmeden hemen önce çağrılır."""
        if 0 <= self._etkin < len(self._oturumlar):
            o = self._oturumlar[self._etkin]
            o.gecerli_sayfa = self.goruntuleyici.gecerli_sayfa
            o.olcek = self.goruntuleyici.olcek
            o.kaydirma = self.goruntuleyici.verticalScrollBar().value()
            o.duzen = self.goruntuleyici.duzen_anahtari
            o.arama_metni = self.bul_kutu.text()
            o.arama_sonuclari, o.arama_no = list(self._sonuclar), self._sonuc_no
            o.arama_acik = self.bul_cubugu.isVisible()
            o.panel_sekmesi = self.paneller.currentIndex()

    def _bekleyen_islemi_iptal_et(self):
        """Belgeye bağlı yarım işlemler sekme değişince bırakılır: bekleyen resim/mühür yerleştirme iptal, araç El'e döner."""
        if getattr(self, "_bekleyen_png", None) is not None:
            self._bekleyen_png = None
            if self._etkin_arac() in ("resim", "muhur"):
                self.e_el.setChecked(True)
                self._arac_uygula()

    def _oturumu_goster(self, o: BelgeOturumu):
        """`o` oturumunu (zaten `_etkin`) görüntüleyici ve panellere bağlar; saklı sayfa/ölçek/arama/panel durumunu geri yükler."""
        self._bekleyen_islemi_iptal_et()
        gecmis_modulu.etkin_ata(o.belge._gecmis)   # genel geri al bütçesi aşılınca önce diğer sekmelerden budanır
        self._geciste = True
        try:
            self._belge_goster(o.gecerli_sayfa)
            if abs(self.goruntuleyici.olcek - o.olcek) > 1e-4:
                self.goruntuleyici.olcek_ata(o.olcek)
            if o.duzen and o.duzen == self.goruntuleyici.duzen_anahtari:   # düzen aynıysa sayfa içi konumu da döndür
                self.goruntuleyici.verticalScrollBar().setValue(o.kaydirma)
            self.bul_kutu.blockSignals(True)   # metni geri yazmak yeni arama başlatmasın
            self.bul_kutu.setText(o.arama_metni)
            self.bul_kutu.blockSignals(False)
            self._sonuclar, self._sonuc_no = list(o.arama_sonuclari), o.arama_no
            self.goruntuleyici.vurgulari_ata(self._sonuclar, self._sonuc_no)
            self.bul_cubugu.setVisible(o.arama_acik)
            self._bul_bilgi_yaz(bool(o.arama_metni.strip()))
            self.paneller.setCurrentIndex(o.panel_sekmesi)
            self._durumu_guncelle()
        finally:
            self._geciste = False

    @contextmanager
    def _mesgul_blok(self):
        """Uzun işlem (OCR, toplu yazdırma…) sürerken sekme değişimi yok sayılır; işlem başladığı belgeye yazar."""
        self._mesgul += 1
        try:
            yield
        finally:
            self._mesgul -= 1
            if self._mesgul == 0 and self._bekleyen_yollar:
                QTimer.singleShot(0, self._bekleyenleri_ac)

    def _bekleyenleri_ac(self):
        """İşlem sürerken gelen açma isteklerini (tek örnek, sürükle-bırak) şimdi açar."""
        if self._mesgul or not self._bekleyen_yollar:
            return
        yollar, self._bekleyen_yollar = self._bekleyen_yollar, []
        self.ac_coklu(yollar)

    def _etkinlestir(self, sira: int):
        """`sira`daki sekmeyi etkin yapar: eskinin durumunu saklar, yeni belgeyi görüntüleyiciye bağlar."""
        if not 0 <= sira < len(self._oturumlar) or sira == self._etkin:
            return
        if self._mesgul:
            self._sekmeleri_tazele()   # çubuk eski sekmede kalsın
            self.statusBar().showMessage("Bir işlem sürüyor; bitince sekme değiştirebilirsiniz.", 3000)
            return
        self._durum_kaydet()
        self._etkin = sira
        self._oturumu_goster(self._oturumlar[sira])

    def _sekme_secildi(self, sira: int):
        """Kullanıcı sekme çubuğundan başka sekmeyi seçti."""
        if sira != self._etkin and not self._geciste:
            self._etkinlestir(sira)

    def _acilis_yakinlastirma(self):
        secim = str(self.ayarlar.value("acilis_yakinlastirma", "genislik"))
        if secim == "sayfa":
            self.goruntuleyici.sayfaya_sigdir()
        elif secim == "yuzde100":
            self.goruntuleyici.olcek_ata(1.0)
        else:
            self.goruntuleyici.genislige_sigdir()

    def ayarlar_ac(self):
        d = AyarlarPenceresi(self.ayarlar, self)
        if d.exec():
            self.ayarlari_uygula()

    def ayarlari_uygula(self):
        """Ayarlar penceresinden sonra değişiklikleri canlı uygular."""
        self._yazar = str(self.ayarlar.value("yazar", "") or os.environ.get("USERNAME", ""))
        self.gorunumu_yukle()
        self._son_menusu_doldur()
        self._tek_ornek_ayarla()
        self.statusBar().showMessage("Ayarlar kaydedildi.", 3000)

    def _oturumu_sessiz_kapat(self, sira: int | None = None):
        """Sekmeyi sormadan kapatır (belge kapanır); son sekmeyse boş duruma, değilse komşu sekmeye geçer."""
        sira = self._etkin if sira is None else sira
        if not 0 <= sira < len(self._oturumlar):
            return
        etkin_miydi = sira == self._etkin
        if etkin_miydi:   # görüntüleyici belgeyi bırakmadan belge kapatılmaz
            self.goruntuleyici.belge_ata(None)
            self.kucuk.belge_ata(None)
            self.yer_imleri.belge_ata(None)
            self.aciklama_paneli.doldur([])
            self._sonuclar, self._sonuc_no = [], -1   # komşu sekme geri yüklenirken kendi sonuçlarını getirir
        self._oturumlar.pop(sira).belge.kapat()
        if not self._oturumlar:
            self._etkin = -1
        elif etkin_miydi:
            self._etkin = min(sira, len(self._oturumlar) - 1)   # sağdaki, yoksa soldaki komşu
            self._oturumu_goster(self._oturumlar[self._etkin])
        elif sira < self._etkin:
            self._etkin -= 1

    def kapat(self):
        self._sekme_kapat(self._etkin)

    def _sekme_kapat(self, sira: int) -> bool:
        """Sekmeyi (değişmişse kaydetme sorarak) kapatır. False: vazgeçildi, işlem sürüyor ya da sekme yok."""
        if not 0 <= sira < len(self._oturumlar):
            return False
        if self._mesgul:
            self.statusBar().showMessage("Bir işlem sürüyor; bitince sekmeyi kapatabilirsiniz.", 3000)
            return False
        if not self._kapatmaya_izin(sira):
            return False
        self._oturumu_sessiz_kapat(sira)
        self._durumu_guncelle()
        return True

    def _sira_of(self, oturum: BelgeOturumu) -> int:
        return next((i for i, o in enumerate(self._oturumlar) if o is oturum), -1)

    def diger_sekmeleri_kapat(self, sira: int):
        """`sira` dışındaki tüm sekmeleri kapatır (her biri için gerekirse sorar; Vazgeç hepsini durdurur)."""
        if not 0 <= sira < len(self._oturumlar):
            return
        hedef = self._oturumlar[sira]
        for o in list(self._oturumlar):
            if o is not hedef and not self._sekme_kapat(self._sira_of(o)):
                return
        if self._sira_of(hedef) >= 0:
            self._etkinlestir(self._sira_of(hedef))

    def tum_sekmeleri_kapat(self):
        """Tüm sekmeleri sırayla kapatır; birinde Vazgeç denirse orada durur (kapananlar kapalı kalır)."""
        for o in list(self._oturumlar):
            if not self._sekme_kapat(self._sira_of(o)):
                return

    def sekme_gez(self, yon: int):
        """Sonraki (+1) / önceki (-1) sekmeye döngüsel geçiş."""
        n = len(self._oturumlar)
        if n > 1:
            self._etkinlestir((self._etkin + yon) % n)

    def _sekme_menusu(self, oturum: BelgeOturumu) -> QMenu:
        menu = QMenu(self)
        menu.addAction("Kapat", lambda: self._sekme_kapat(self._sira_of(oturum)))
        diger = menu.addAction("Diğerlerini Kapat", lambda: self.diger_sekmeleri_kapat(self._sira_of(oturum)))
        diger.setEnabled(len(self._oturumlar) > 1)
        menu.addAction("Tümünü Kapat", self.tum_sekmeleri_kapat)
        menu.addSeparator()
        yol = oturum.belge.yol
        kopya = menu.addAction("Yolu Kopyala", lambda: QApplication.clipboard().setText(str(yol)))
        kopya.setEnabled(yol is not None)
        goster = menu.addAction("Klasörde Göster", lambda: self._klasorde_goster(yol))
        goster.setEnabled(yol is not None and Path(yol).exists())
        return menu

    def _sekme_sag_tik(self, nokta):
        sira = self.sekmeler.tabAt(nokta)
        if sira >= 0:
            self._sekme_menusu(self._oturumlar[sira]).exec(self.sekmeler.mapToGlobal(nokta))

    @staticmethod
    def _klasorde_goster(yol):
        """Dosyayı Windows Gezgini'nde seçili gösterir."""
        subprocess.Popen(["explorer", f"/select,{Path(yol)}"])

    def _belge_goster(self, sayfa: int):
        """Belge değiştiğinde (açılış, sayfa işlemi) tüm görünümleri tazeler."""
        self.goruntuleyici.belge_ata(self.belge, sayfa)
        self.kucuk.belge_ata(self.belge)
        self.yer_imleri.belge_ata(self.belge)
        self.aciklamalari_tazele()
        self.kucuk.vurgula(min(sayfa, self.belge.sayfa_sayisi - 1))
        self._sonuclar, self._sonuc_no = [], -1
        self.goruntuleyici.vurgulari_ata([])   # önceki belgenin/içeriğin arama vurguları kalmasın
        self.bul_bilgi.setText("")
        self._durumu_guncelle()

    def _sekmeleri_tazele(self):
        """Sekme çubuğunu oturum listesine uydurur (sayı, yazı, ipucu, kilit simgesi, etkin sekme, görünürlük)."""
        cubuk = self.sekmeler
        cubuk.blockSignals(True)
        try:
            while cubuk.count() > len(self._oturumlar):
                cubuk.removeTab(cubuk.count() - 1)
            while cubuk.count() < len(self._oturumlar):
                i = cubuk.addTab("")
                cubuk.setTabButton(i, QTabBar.RightSide, self._sekme_kapat_dugmesi())
            for i, o in enumerate(self._oturumlar):
                cubuk.setTabText(i, sekme_basligi(o))
                cubuk.setTabToolTip(i, sekme_ipucu(o))
                cubuk.setTabIcon(i, simgeler.simge("kilit") if o.belge.parola_korunur else QIcon())
            if 0 <= self._etkin < cubuk.count():
                cubuk.setCurrentIndex(self._etkin)
        finally:
            cubuk.blockSignals(False)
        cubuk.setVisible(bool(self._oturumlar))

    def _sekme_kapat_dugmesi(self) -> QToolButton:
        d = QToolButton()
        d.setAutoRaise(True)
        d.setIcon(simgeler.simge("kapat"))
        d.setIconSize(QSize(12, 12))
        d.setToolTip("Sekmeyi kapat")
        d.setCursor(Qt.ArrowCursor)
        d.clicked.connect(lambda *_, dugme=d: self._sekme_dugmesi_tiklandi(dugme))
        return d

    def _sekme_dugmesi_tiklandi(self, dugme: QToolButton):
        for i in range(self.sekmeler.count()):
            if self.sekmeler.tabButton(i, QTabBar.RightSide) is dugme:
                self.sekmeler.tabCloseRequested.emit(i)
                return

    def _sekme_tasindi(self, eski: int, yeni: int):
        """Kullanıcı sekmeyi sürükleyip sırasını değiştirdi: oturum listesi aynı sıraya gelir, etkin oturum izlenir."""
        etkin = self._oturumlar[self._etkin] if 0 <= self._etkin < len(self._oturumlar) else None
        self._oturumlar.insert(yeni, self._oturumlar.pop(eski))
        self._etkin = self._oturumlar.index(etkin) if etkin else -1

    def _durumu_guncelle(self):
        self._sekmeleri_tazele()
        var = self.belge is not None
        for e in (self.e_sonraki_sekme, self.e_onceki_sekme):
            e.setEnabled(len(self._oturumlar) > 1)
        for e in self._belge_eylemleri:
            e.setEnabled(var)
        for w in (self.sayfa_kutu, self.paneller):
            w.setEnabled(var)
        self._aciklama_durumu()
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
        if self._acik_dosya_engeli(yol, kendisi_serbest=True):   # başka sekmede açık dosyanın üzerine yazılmaz
            return False
        # Seçilen yer bu belgenin kendisiyse kullanıcı Windows'un üzerine-yaz sorusunu zaten onayladı
        return self._yaz(yol, uzerine_yaz=bool(self.belge.yol and yol.resolve() == self.belge.yol.resolve()))

    def _yaz(self, yol: Path, uzerine_yaz: bool) -> bool:
        if not self._imzali_kayit_onayi() or not self._koruma_dusme_onayi():
            return False
        try:
            self.belge.kaydet(yol, uzerine_yaz=uzerine_yaz)
        except (BelgeHatasi, OSError) as h:
            QMessageBox.warning(self, APP_NAME, f"Kaydedilemedi:\n{h}")
            return False
        ek = ""
        if self.belge.parola_korunur:
            ek = " (parola" + (" ve izin kısıtları" if self.belge.izinler_kilitli else "") + " korundu)"
        self.statusBar().showMessage(f"Kaydedildi: {yol}{ek}", 5000)
        self._son_ekle(str(yol))
        self._durumu_guncelle()
        return True

    def _koruma_dusme_onayi(self) -> bool:
        """Parolası bilinmeyen (yalnızca sahip kısıtlı) belgede kısıtlar kayıtta kalkar; kullanıcıya sorulur."""
        if not self.belge or not self.belge.koruma_dusecek:
            return True
        return QMessageBox.question(
            self, APP_NAME, "Bu belgede sahip parolasıyla konmuş kısıtlar (yazdırma, kopyalama, düzenleme…) var. Sahip parolası "
                            "bilinmediği için kaydedilen dosyada bu kısıtlar kalkacak.\nDevam edilsin mi?",
            QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel) == QMessageBox.Yes

    def _kapatmaya_izin(self, sira: int | None = None) -> bool:
        """Sekme kapatılabilir mi? Değişmişse Farklı Kaydet / Kaydetmeden Kapat / Vazgeç sorar (sekme önce etkinleştirilir,
        kullanıcı hangi belge olduğunu görsün)."""
        sira = self._etkin if sira is None else sira
        if not 0 <= sira < len(self._oturumlar) or not self._oturumlar[sira].belge.degisti:
            return True
        self._etkinlestir(sira)
        kutu = QMessageBox(QMessageBox.Question, APP_NAME, f"“{sekme_basligi(self._oturumlar[sira]).lstrip('● ')}” belgesinde "
                           "kaydedilmemiş değişiklikler var.", parent=self)
        farkli = kutu.addButton("Farklı Kaydet…", QMessageBox.AcceptRole)
        atla = kutu.addButton("Kaydetmeden Kapat", QMessageBox.DestructiveRole)
        kutu.addButton("Vazgeç", QMessageBox.RejectRole)
        kutu.exec()
        if kutu.clickedButton() is farkli:
            return self.farkli_kaydet()
        return kutu.clickedButton() is atla

    def closeEvent(self, olay):
        """Değişmiş sekmeleri sırayla sorar; biri 'Vazgeç' derse (ya da bir işlem sürüyorsa) pencere kapanmaz."""
        if self._mesgul:
            self.statusBar().showMessage("Bir işlem sürüyor; bitince pencereyi kapatabilirsiniz.", 3000)
            olay.ignore()
            return
        for sira in range(len(self._oturumlar)):
            if not self._kapatmaya_izin(sira):
                olay.ignore()
                return
        self.oturumu_kaydet()
        while self._oturumlar:
            self._oturumu_sessiz_kapat(len(self._oturumlar) - 1)
        if self.tek_ornek is not None:
            self.tek_ornek.durdur()
        olay.accept()

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
        self.ac_coklu([u.toLocalFile() for u in olay.mimeData().urls() if u.toLocalFile().lower().endswith(".pdf")])
        olay.acceptProposedAction()

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
        if self.ek_sil_secili():  # seçili bir ek açıklama varsa Del onu siler
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
        yol = yol if yol.lower().endswith(".pdf") else yol + ".pdf"
        if self._acik_dosya_engeli(yol):
            return
        try:
            self.belge.sayfalari_kaydet(sayfalar, yol)
        except (BelgeHatasi, OSError) as h:
            QMessageBox.warning(self, APP_NAME, str(h))
            return
        self._kopyayi_ac_sor(Path(yol), f"{len(sayfalar)} sayfa çıkarıldı: {yol}")

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
        yol = yol if yol.lower().endswith(".pdf") else yol + ".pdf"
        if self._acik_dosya_engeli(yol):
            return
        try:
            n = belge_modulu.birlestir(yollar, yol)
        except (BelgeHatasi, OSError) as h:
            QMessageBox.warning(self, APP_NAME, str(h))
            return
        self._kopyayi_ac_sor(Path(yol), f"{len(yollar)} dosya birleştirildi ({n} sayfa): {yol}")

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
        for n in range(1, len(pencere.parcalar) + 1):   # çıktı adları <ad>_1.pdf …: açık bir sekmenin dosyasını ezmesin
            if self._acik_dosya_engeli(Path(klasor) / f"{self.belge.yol.stem}_{n}.pdf"):
                return
        try:
            yazilan = belge_modulu.bol(self.belge.yol, klasor, parcalar=pencere.parcalar)
        except (BelgeHatasi, OSError) as h:
            QMessageBox.warning(self, APP_NAME, str(h))
            return
        self._parcalari_ac_sor(yazilan, klasor)

    def _parcalari_ac_sor(self, yazilan: list, klasor):
        """Bölme bitti: parçaları sekmelerde açmayı, klasörü göstermeyi ya da hiçbirini seçtirir."""
        ileti = f"{len(yazilan)} dosya yazıldı: {klasor}"
        self.statusBar().showMessage(ileti, 8000)
        kutu = QMessageBox(QMessageBox.Question, APP_NAME, ileti + "\n\nNe yapmak istersiniz?", parent=self)
        ac = kutu.addButton("Hepsini Aç", QMessageBox.AcceptRole)
        klasor_dugme = kutu.addButton("Klasörü Göster", QMessageBox.ActionRole)
        kutu.addButton("Kapat", QMessageBox.RejectRole)
        kutu.exec()
        secilen = kutu.clickedButton()
        if secilen is ac:
            self.ac_coklu([str(y) for y in yazilan])   # sekme sınırı aşılırsa kalanlar tek uyarıyla atlanır
        elif secilen is klasor_dugme:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(klasor)))

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
        if olay.key() == Qt.Key_Escape and not self.bul_cubugu.isVisible():
            self.goruntuleyici.secimi_temizle()
        elif olay.key() == Qt.Key_Escape and self.bul_cubugu.isVisible():
            self.bul_cubugu.hide()
            self.goruntuleyici.vurgulari_ata([])
            self.goruntuleyici.setFocus()
        else:
            super().keyPressEvent(olay)

    # --- görünüm ---
    def _gorunum_uygula(self, *_):
        mod = MOD_TEK if self.e_tek.isChecked() else MOD_SUREKLI
        sutun = 2 if self.e_cift.isChecked() else 1
        self.goruntuleyici.mod_ata(mod, sutun)
        self.ayarlar.setValue("gorunum_mod", mod)
        self.ayarlar.setValue("gorunum_sutun", sutun)

    def _arac_uygula(self, *_):
        arac = ARAC_EL
        for kimlik, e in self._arac_eylemleri.items():
            if e.isChecked():
                arac = kimlik
                break
        self.goruntuleyici.arac_ata(arac)
        if arac in (ARAC_EL, ARAC_SEC):
            self.ayarlar.setValue("arac", arac)
        if hasattr(self, "renk_dugme"):
            self._arac_degisti(arac)

    def _gece_uygula(self, *_):
        self.goruntuleyici.gece_ata(self.e_gece.isChecked())
        self.ayarlar.setValue("gece", self.e_gece.isChecked())

    def gorunumu_yukle(self):
        """Kayıtlı görünüm ayarlarını (mod, sütun, araç, gece) menüye ve görüntüleyiciye uygular."""
        a = self.ayarlar
        (self.e_tek if a.value("gorunum_mod", MOD_SUREKLI) == MOD_TEK else self.e_surekli).setChecked(True)
        self.e_cift.setChecked(str(a.value("gorunum_sutun", 1)) == "2")
        (self.e_sec if a.value("arac", ARAC_EL) == ARAC_SEC else self.e_el).setChecked(True)
        self.e_gece.setChecked(str(a.value("gece", False)).lower() in ("true", "1"))
        self._gorunum_uygula()
        self._arac_uygula()
        self._gece_uygula()

    def kopyala(self):
        if self.goruntuleyici.kopyala():
            self.statusBar().showMessage("Seçili metin panoya kopyalandı.", 3000)
        else:
            self.statusBar().showMessage("Kopyalanacak seçili metin yok (Metin Seçme Aracı ile seçin).", 4000)

    def yazdir(self):
        if not self.belge:
            return
        yazici = QPrinter(QPrinter.HighResolution)
        n = self.belge.sayfa_sayisi
        pencere = QPrintDialog(yazici, self)
        pencere.setWindowTitle("Yazdır")
        pencere.setOption(QPrintDialog.PrintPageRange, True)
        pencere.setOption(QPrintDialog.PrintCurrentPage, True)
        secili = self.kucuk.secili_sayfalar()
        pencere.setOption(QPrintDialog.PrintSelection, len(secili) > 1)
        pencere.setMinMax(1, n)
        if not pencere.exec():
            return
        self.yazici_ile_yazdir(yazici, secili)

    def yazici_ile_yazdir(self, yazici, secili=None):
        """Yazıcı ayarındaki sayfa aralığına göre yazdırır (pencere ve testler ortak kullanır)."""
        n = self.belge.sayfa_sayisi
        aralik = yazici.printRange()
        if aralik == QPrinter.PageRange:
            sayfalar = list(range(yazici.fromPage() - 1, yazici.toPage()))
        elif aralik == QPrinter.CurrentPage:
            sayfalar = [self.goruntuleyici.gecerli_sayfa]
        elif aralik == QPrinter.Selection and secili:
            sayfalar = secili
        else:
            sayfalar = list(range(n))
        try:
            adet = sayfalari_yazdir(self.belge, yazici, sayfalar)
        except OSError as h:
            QMessageBox.warning(self, APP_NAME, str(h))
            return 0
        self.statusBar().showMessage(f"{adet} sayfa yazıcıya gönderildi.", 5000)
        return adet

    def toplu_yazdir_ac(self):
        d = TopluYazdirPenceresi(str(self.ayarlar.value("son_klasor", "")), self)
        if self.belge and self.belge.yol:
            d.dosya_ekle([str(self.belge.yol)])
        if not d.exec():
            return
        yazici = QPrinter(QPrinter.HighResolution)
        pencere = QPrintDialog(yazici, self)
        pencere.setWindowTitle("Toplu Yazdır — yazıcı ve ayarlar (tüm dosyalara uygulanır)")
        if not pencere.exec():
            return
        self.toplu_yazdir_calistir(d.yollar(), yazici, d.aralik.text())

    def toplu_yazdir_calistir(self, yollar, yazici, aralik="", parola_sor=None):
        """Dosyaları yazdırır, ilerleme gösterir, sonucu özetler (pencere ve testler ortak kullanır)."""
        ilerleme = QProgressDialog("Dosyalar yazıcıya gönderiliyor…", "İptal", 0, len(yollar), self)
        ilerleme.setWindowTitle("Toplu Yazdır")
        ilerleme.setMinimumDuration(0)
        ilerleme.setAutoClose(False)
        ilerleme.setAutoReset(False)

        def geri(n, toplam):
            ilerleme.setValue(n)
            ilerleme.setLabelText(f"Dosyalar yazıcıya gönderiliyor… ({min(n + 1, toplam)}/{toplam})")
            QApplication.processEvents()
            return ilerleme.wasCanceled()

        def parola(yol):
            p, tamam = QInputDialog.getText(self, "Parola Gerekli", f"{Path(yol).name} parolayla korunuyor.\nParolayı girin "
                                            "(boş bırakırsanız dosya atlanır):", QLineEdit.Password)
            return p if tamam else None

        try:
            with self._mesgul_blok():
                sonuc = toplu_yazdir(yollar, yazici, aralik, parola_sor or parola, geri)
        finally:
            ilerleme.close()
        tamam = [s for s in sonuc if s.tamam]
        sayfa = sum(s.sayfa for s in tamam)
        atlanan = len(yollar) - len(sonuc)
        satir = f"{len(tamam)} dosya, {sayfa} sayfa yazıcıya gönderildi."
        sorunlu = [s for s in sonuc if not s.tamam]
        if sorunlu or atlanan:
            ayrinti = "\n".join(f"• {Path(s.yol).name}: {s.hata}" for s in sorunlu)
            if atlanan:
                ayrinti += f"\n• {atlanan} dosya iptal nedeniyle yazdırılmadı."
            QMessageBox.warning(self, "Toplu Yazdır", f"{satir}\n\nSorun olanlar:\n{ayrinti}")
        else:
            self.statusBar().showMessage(satir, 6000)
        return sonuc

    # --- diğer ---
    def ozellikleri_goster(self):
        if not self.belge:
            return
        d = OzelliklerPenceresi(self.belge.ozellikler(), self)
        if not d.exec():
            return
        try:
            if d.temizle_istendi:
                self.belge.ozellikleri_temizle()
            elif d.degisenler():
                self.belge.ozellikleri_ata(**d.degisenler())
            else:
                return
        except BelgeHatasi as h:
            QMessageBox.warning(self, APP_NAME, str(h))
            return
        self._durumu_guncelle()
        self.statusBar().showMessage("Belge özellikleri güncellendi (kaydedince dosyaya yazılır).", 5000)

    def _tam_ekran(self):
        self.showNormal() if self.isFullScreen() else self.showFullScreen()

    def yardim(self, konu: str | None = None):
        YardimPenceresi(self, konu).exec()

    def showEvent(self, olay):
        super().showEvent(olay)
        if not getattr(self, "_baslik_boyandi", False):
            self._baslik_boyandi = True
            theme.color_title_bar(self)
