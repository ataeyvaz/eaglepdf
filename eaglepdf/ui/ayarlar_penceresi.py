"""Ayarlar penceresi: genel, görünüm, klasörler, OCR ve dosya ilişkilendirme.

Pencere yalnızca `QSettings`e yazar (`uygula`); ana pencere sonra `ayarlari_uygula()` ile değişiklikleri canlı uygular.
Dosya ilişkilendirme düğmeleri anında çalışır (Windows kayıt defterinde yalnızca kullanıcı düzeyi).
"""
from __future__ import annotations

import os

from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QGroupBox,
                               QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QTabWidget, QVBoxLayout, QWidget)

from .. import APP_NAME
from ..core import iliskilendirme
from ..core.belge import BelgeHatasi
from .goruntuleyici import ARAC_EL, ARAC_SEC, MOD_SUREKLI, MOD_TEK
from .ocr_arayuzu import dil_secenekleri

ACILIS_YAKINLASTIRMA = (("genislik", "Sayfa genişliğine sığdır"), ("sayfa", "Tam sayfayı sığdır"), ("yuzde100", "%100"))
ARAC_SECENEKLERI = ((ARAC_EL, "El aracı (kaydır)"), (ARAC_SEC, "Metin seçme aracı"))


def _dogru_mu(deger) -> bool:
    return str(deger).lower() in ("true", "1")


def _kutu_sec(kutu: QComboBox, veri):
    i = kutu.findData(veri)
    kutu.setCurrentIndex(i if i >= 0 else 0)


class AyarlarPenceresi(QDialog):
    def __init__(self, ayarlar, parent=None):
        super().__init__(parent)
        self.ayarlar = ayarlar
        self.son_listesini_temizle = False
        self.setWindowTitle("Ayarlar")
        self.setMinimumWidth(520)
        yerlesim = QVBoxLayout(self)
        sekmeler = QTabWidget()
        yerlesim.addWidget(sekmeler)
        sekmeler.addTab(self._genel_sekmesi(), "Genel")
        sekmeler.addTab(self._klasor_sekmesi(), "Klasörler ve OCR")
        sekmeler.addTab(self._iliski_sekmesi(), "Dosya İlişkisi")
        dugmeler = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        dugmeler.button(QDialogButtonBox.Ok).setText("Tamam")
        dugmeler.button(QDialogButtonBox.Cancel).setText("Vazgeç")
        dugmeler.accepted.connect(self._tamam)
        dugmeler.rejected.connect(self.reject)
        yerlesim.addWidget(dugmeler)

    # --- sekmeler ---
    def _genel_sekmesi(self) -> QWidget:
        a = self.ayarlar
        w = QWidget()
        form = QFormLayout(w)
        self.yazar = QLineEdit(str(a.value("yazar", "") or os.environ.get("USERNAME", "")))
        form.addRow("Açıklamalarda yazar adı:", self.yazar)
        self.acilis = QComboBox()
        for kod, ad in ACILIS_YAKINLASTIRMA:
            self.acilis.addItem(ad, kod)
        _kutu_sec(self.acilis, str(a.value("acilis_yakinlastirma", "genislik")))
        form.addRow("Belge açılırken:", self.acilis)
        self.mod = QComboBox()
        self.mod.addItem("Sürekli kaydırma", "surekli")
        self.mod.addItem("Tek sayfa", "tek")
        self._mod_kodlari = {"surekli": MOD_SUREKLI, "tek": MOD_TEK}
        _kutu_sec(self.mod, "tek" if a.value("gorunum_mod", MOD_SUREKLI) == MOD_TEK else "surekli")
        form.addRow("Sayfa düzeni:", self.mod)
        self.cift = QCheckBox("Çift sayfa (yan yana)")
        self.cift.setChecked(str(a.value("gorunum_sutun", 1)) == "2")
        form.addRow("", self.cift)
        self.gece = QCheckBox("Gece modu (koyu sayfa)")
        self.gece.setChecked(_dogru_mu(a.value("gece", False)))
        form.addRow("", self.gece)
        self.arac = QComboBox()
        for kod, ad in ARAC_SECENEKLERI:
            self.arac.addItem(ad, kod)
        _kutu_sec(self.arac, str(a.value("arac", ARAC_EL)))
        form.addRow("Varsayılan araç:", self.arac)
        self.tek_ornek = QCheckBox("Dosyaları çalışan pencerede sekme olarak aç (tek pencere)")
        self.tek_ornek.setChecked(_dogru_mu(a.value("tek_ornek", True)))
        self.tek_ornek.setToolTip("Açıksa, bir PDF'e çift tıklayınca ya da “Birlikte aç” deyince yeni pencere yerine "
                                  "çalışan pencerede yeni sekme açılır.")
        form.addRow("", self.tek_ornek)
        self.oturum_geri = QCheckBox("Açılışta son oturumdaki sekmeleri geri yükle")
        self.oturum_geri.setChecked(_dogru_mu(a.value("oturumu_geri_yukle", False)))
        self.oturum_geri.setToolTip("Kapattığınızda açık olan belgeler bir sonraki açılışta yeniden açılır "
                                    "(bulunamayan ve parolalı belgeler atlanır).")
        form.addRow("", self.oturum_geri)
        temizle = QPushButton("Son kullanılanlar listesini temizle")
        temizle.clicked.connect(self._temizle_isaretle)
        self.temizle_etiketi = QLabel("")
        form.addRow("", temizle)
        form.addRow("", self.temizle_etiketi)
        form.addRow(QLabel("Arayüz dili Türkçedir; başka dil seçeneği şimdilik yok."))
        return w

    def _klasor_sekmesi(self) -> QWidget:
        a = self.ayarlar
        w = QWidget()
        form = QFormLayout(w)
        satir = QHBoxLayout()
        self.donusum = QLineEdit(str(a.value("donusum_klasoru", "")))
        self.donusum.setPlaceholderText("Boş = dönüştürülen dosyanın yanı")
        goz = QPushButton("Seç…")
        goz.clicked.connect(self._klasor_sec)
        satir.addWidget(self.donusum)
        satir.addWidget(goz)
        form.addRow("Dönüştürme çıktı klasörü:", satir)
        self.ocr_dil = QComboBox()
        secenekler = dil_secenekleri()
        for kod, ad in secenekler:
            self.ocr_dil.addItem(ad, kod)
        if not secenekler:
            self.ocr_dil.addItem("Dil verisi kurulu değil", "")
            self.ocr_dil.setEnabled(False)
        else:
            _kutu_sec(self.ocr_dil, str(a.value("ocr_dil", "tur+eng")))
        form.addRow("OCR dili:", self.ocr_dil)
        return w

    def _iliski_sekmesi(self) -> QWidget:
        w = QWidget()
        yerlesim = QVBoxLayout(w)
        yerlesim.addWidget(QLabel(
            f"{APP_NAME}'i PDF dosyalarının sağ tık → “Birlikte aç” listesine ekleyebilirsiniz. Bu yalnızca sizin kullanıcı "
            "hesabınızı etkiler, yönetici izni gerekmez ve geri alınabilir."))
        self.iliski_durum = QLabel()
        yerlesim.addWidget(self.iliski_durum)
        kutu = QGroupBox("İşlemler")
        kl = QVBoxLayout(kutu)
        self.btn_ekle = QPushButton("“Birlikte aç” listesine ekle")
        self.btn_kaldir = QPushButton("Listeden kaldır")
        self.btn_varsayilan = QPushButton("Windows “Varsayılan uygulamalar” ekranını aç…")
        self.btn_ekle.clicked.connect(self._iliski_ekle)
        self.btn_kaldir.clicked.connect(self._iliski_kaldir)
        self.btn_varsayilan.clicked.connect(iliskilendirme.varsayilan_uygulamalari_ac)
        for b in (self.btn_ekle, self.btn_kaldir, self.btn_varsayilan):
            kl.addWidget(b)
        yerlesim.addWidget(kutu)
        yerlesim.addWidget(QLabel("Windows, varsayılan PDF uygulamasını programdan değiştirmeye izin vermez; ekledikten sonra "
                                  "yukarıdaki ekranda “.pdf” için bu uygulamayı kendiniz seçin."))
        yerlesim.addStretch()
        self._iliski_tazele()
        return w

    # --- olaylar ---
    def _temizle_isaretle(self):
        self.son_listesini_temizle = True
        self.temizle_etiketi.setText("Tamam'a basınca temizlenecek.")

    def _klasor_sec(self):
        yol = QFileDialog.getExistingDirectory(self, "Çıktı Klasörü", self.donusum.text())
        if yol:
            self.donusum.setText(yol)

    def _iliski_tazele(self):
        kayitli = iliskilendirme.kayitli_mi()
        self.iliski_durum.setText("Durum: ✔ “Birlikte aç” listesinde" if kayitli else "Durum: listede değil")
        self.btn_ekle.setEnabled(not kayitli and iliskilendirme.winreg is not None)
        self.btn_kaldir.setEnabled(kayitli)

    def _iliski_ekle(self):
        try:
            iliskilendirme.kaydet()
        except BelgeHatasi as h:
            QMessageBox.warning(self, APP_NAME, str(h))
        self._iliski_tazele()

    def _iliski_kaldir(self):
        try:
            iliskilendirme.kaldir()
        except BelgeHatasi as h:
            QMessageBox.warning(self, APP_NAME, str(h))
        self._iliski_tazele()

    def _tamam(self):
        klasor = self.donusum.text().strip()
        if klasor and not os.path.isdir(klasor):
            QMessageBox.warning(self, APP_NAME, "Seçilen çıktı klasörü bulunamadı.")
            return
        self.uygula()
        self.accept()

    def uygula(self):
        """Pencere değerlerini `QSettings`e yazar."""
        a = self.ayarlar
        a.setValue("yazar", self.yazar.text().strip())
        a.setValue("acilis_yakinlastirma", self.acilis.currentData())
        a.setValue("gorunum_mod", self._mod_kodlari[self.mod.currentData()])
        a.setValue("gorunum_sutun", 2 if self.cift.isChecked() else 1)
        a.setValue("gece", self.gece.isChecked())
        a.setValue("arac", self.arac.currentData())
        a.setValue("tek_ornek", self.tek_ornek.isChecked())
        a.setValue("oturumu_geri_yukle", self.oturum_geri.isChecked())
        a.setValue("donusum_klasoru", self.donusum.text().strip())
        if self.ocr_dil.currentData():
            a.setValue("ocr_dil", self.ocr_dil.currentData())
        if self.son_listesini_temizle:
            a.setValue("son_dosyalar", [])
