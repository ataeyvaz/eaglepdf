"""Ana pencerenin Faz 3 bölümü: düzenleme menüsü ve araç çubuğu, sayfa işlemleri (kırp, boyut, filigran, arka plan,
üstbilgi/altbilgi, sayfa numarası), kalıcı silme, düzleştirme, mühür/resim yerleştirme ve metin düzenleme.

`AnaPencere`ye karışım olarak eklenir; `AciklamaArayuzu` ile aynı üyeleri kullanır.
"""

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QImage, QPixmap
from PySide6.QtWidgets import QFileDialog, QInputDialog, QMenu, QMessageBox, QToolBar, QToolButton

from .. import APP_NAME
from ..core import imzalar
from ..core.belge import BelgeHatasi
from ..core.duzenleme import MUHUR_METINLERI
from . import simgeler
from .dialoglar import MetinPenceresi, png_baytlari
from .goruntuleyici import ARAC_DUZENLE
from .sayfa_islem_dialoglari import (
    MUHUR_RENKLERI, ArkaPlanPenceresi, BoyutPenceresi, DuzlestirPenceresi, FiligranPenceresi, KirpPenceresi,
    FiligranKaldirPenceresi, KatmanKaldirPenceresi, MuhurPenceresi, SayfaNumarasiPenceresi, UstAltBilgiPenceresi, muhur_resmi,
)

VARSAYILAN_MUHUR_GENISLIK = 160.0   # pt
VARSAYILAN_RESIM_GENISLIK = 220.0   # pt
EN_BUYUK_RESIM_KENARI = 2400        # px: daha büyük resimler küçültülür (dosya şişmesin)
IPUCLARI = {
    "metin_duzenle": "Düzenlenecek metin paragrafına tıklayın. (Yazı tipi Noto Sans olarak yeniden yazılır.)",
    "resim": "Resmin yerini sürükleyin (ya da tıklayın); sonra seçip taşıyabilir, köşesinden boyutlandırabilirsiniz.",
    "muhur": "Mührün yerini sürükleyin (ya da tıklayın); sonra seçip taşıyabilir, köşesinden boyutlandırabilirsiniz.",
    "redaction": "Kalıcı silinecek alanı sürükleyerek seçin; onaydan sonra içerik geri getirilemez.",
}


def muhur_adi(yol: Path) -> str:
    """Kayıtlı mühür dosya adı `YYYYMMDD-HHMMSS-ad[-n]` → görünen ad."""
    ad = yol.stem[16:] if len(yol.stem) > 16 else yol.stem
    return ad[:-2] if ad[-2:-1] == "-" and ad[-1:].isdigit() else ad


class DuzenlemeArayuzu:
    # --- kurulum ---
    def _duzenleme_kur(self):
        self._bekleyen_png: bytes | None = None
        self._bekleyen_ad = ""
        self._bekleyen_genislik = VARSAYILAN_RESIM_GENISLIK
        self.muhur_klasoru = Path(self.ayarlar.fileName()).parent / "muhurler"
        self._ek_ipuclari = IPUCLARI
        a = self._arac_eylemleri
        for kimlik, ad, simge in (("metin_duzenle", "Metni Düzenle", "duzenle_metin"), ("resim", "Resim Yerleştir", "resim"),
                                  ("muhur", "Mühür Yerleştir", "muhur"), ("redaction", "Kalıcı Sil (Redaction)", "redaction")):
            e = self._eylem(ad, self._arac_uygula, simge=simge, isaretli=False)
            self._arac_grubu.addAction(e)
            a[kimlik] = e

        self.e_resim = self._eylem("Resim Ekle…", self.resim_sec, simge="resim")
        self.e_ozel_muhur = self._eylem("Özel Mühür Oluştur…", self.ozel_muhur_olustur)
        self.e_ara_sil = self._eylem("Metni Ara ve Kalıcı Sil…", self.metin_ara_ve_sil, simge="redaction")
        self.e_duzlestir = self._eylem("Düzleştir…", self.duzlestir_ac, simge="duzlestir")
        self.e_fil_temizle = self._eylem("Filigran Temizle…", self.filigran_temizle_ac, simge="filigran")
        self.e_kirp = self._eylem("Kırp…", self.kirp_ac, simge="kirp")
        self.e_kirpma_kaldir = self._eylem("Kırpmayı Kaldır", self.kirpmayi_kaldir)
        self.e_boyut = self._eylem("Sayfa Boyutu…", self.boyut_ac, simge="boyut")
        self.e_filigran = self._eylem("Filigran…", self.filigran_ac, simge="filigran")
        self.e_filigran_kaldir = self._eylem("Filigranı Kaldır…", self.filigran_kaldir_ac)
        self.e_arka_plan = self._eylem("Arka Plan…", self.arka_plan_ac, simge="arkaplan")
        self.e_ustalt = self._eylem("Üstbilgi / Altbilgi…", self.ustalt_ac, simge="ustalt")
        self.e_numara = self._eylem("Sayfa Numarası Ekle…", self.numara_ac, simge="numara")
        self.e_ustalt_kaldir = self._eylem("Üstbilgi / Altbilgiyi Kaldır…", self.ustalt_kaldir_ac)
        self.e_numara_kaldir = self._eylem("Sayfa Numaralarını Kaldır…", self.numara_kaldir_ac)

        # Düzenle menüsü
        self.m_duzenle = QMenu("Dü&zenle", self)
        self.menuBar().insertMenu(self.m_sayfa.menuAction(), self.m_duzenle)
        self.m_duzenle.addAction(a["metin_duzenle"])
        self.m_duzenle.addAction(self.e_resim)
        self.m_muhur = self.m_duzenle.addMenu(simgeler.simge("muhur"), "Mühür")
        self.m_muhur.aboutToShow.connect(self._muhur_menusunu_doldur)
        self.m_duzenle.addSeparator()
        self.m_duzenle.addAction(a["redaction"])
        self.m_duzenle.addAction(self.e_ara_sil)
        self.m_duzenle.addSeparator()
        self.m_duzenle.addAction(self.e_duzlestir)
        self.m_duzenle.addAction(self.e_fil_temizle)

        # Sayfa menüsüne
        self.m_sayfa.addSeparator()
        for e in (self.e_kirp, self.e_kirpma_kaldir, self.e_boyut, self.e_filigran, self.e_filigran_kaldir, self.e_arka_plan,
                  self.e_ustalt, self.e_ustalt_kaldir, self.e_numara, self.e_numara_kaldir):
            self.m_sayfa.addAction(e)

        # üçüncü araç çubuğu
        self.duzenleme_arac = QToolBar()
        self.duzenleme_arac.setMovable(False)
        self.duzenleme_arac.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.duzenleme_arac.setIconSize(QSize(20, 20))
        self.centralWidget().layout().insertWidget(3, self.duzenleme_arac)
        for e in (a["metin_duzenle"], self.e_resim):
            self.duzenleme_arac.addAction(e)
        muhur_dugme = QToolButton()
        muhur_dugme.setIcon(simgeler.simge("muhur"))
        muhur_dugme.setToolTip("Mühür")
        muhur_dugme.setPopupMode(QToolButton.InstantPopup)
        self._muhur_dugme_menu = QMenu(muhur_dugme)
        self._muhur_dugme_menu.aboutToShow.connect(lambda: self._muhur_menusunu_doldur(self._muhur_dugme_menu))
        muhur_dugme.setMenu(self._muhur_dugme_menu)
        self.duzenleme_arac.addWidget(muhur_dugme)
        self.duzenleme_arac.addAction(a["redaction"])
        self.duzenleme_arac.addAction(self.e_duzlestir)
        self.duzenleme_arac.addSeparator()
        for e in (self.e_kirp, self.e_boyut, self.e_filigran, self.e_arka_plan, self.e_ustalt, self.e_numara):
            self.duzenleme_arac.addAction(e)

        self._belge_eylemleri += [self.e_fil_temizle, self.e_resim, self.e_ozel_muhur, self.e_ara_sil, self.e_duzlestir, self.e_kirp,
                                  self.e_kirpma_kaldir, self.e_boyut, self.e_filigran, self.e_filigran_kaldir, self.e_arka_plan,
                                  self.e_ustalt, self.e_numara, self.e_ustalt_kaldir, self.e_numara_kaldir, a["metin_duzenle"], a["resim"], a["muhur"], a["redaction"]]
        self._muhur_dugme = muhur_dugme
        # araç çubuklarını göster/gizle
        self.e_ek_arac = self._eylem("Açıklama Araç Çubuğu", lambda: self._arac_cubugu_ayarla("ek_arac_goster", self.ek_arac, self.e_ek_arac),
                                     isaretli=True)
        self.e_duzenleme_arac = self._eylem("Düzenleme Araç Çubuğu", lambda: self._arac_cubugu_ayarla(
            "duzenleme_arac_goster", self.duzenleme_arac, self.e_duzenleme_arac), isaretli=True)
        self.m_gorunum.addSeparator()
        self.m_gorunum.addAction(self.e_ek_arac)
        self.m_gorunum.addAction(self.e_duzenleme_arac)
        for anahtar, cubuk, eylem in (("ek_arac_goster", self.ek_arac, self.e_ek_arac),
                                      ("duzenleme_arac_goster", self.duzenleme_arac, self.e_duzenleme_arac)):
            acik = str(self.ayarlar.value(anahtar, True)).lower() in ("true", "1")
            eylem.setChecked(acik)
            cubuk.setVisible(acik)

    def _arac_cubugu_ayarla(self, anahtar: str, cubuk, eylem):
        cubuk.setVisible(eylem.isChecked())
        self.ayarlar.setValue(anahtar, eylem.isChecked())

    # --- ortak ---
    def _uygula(self, fn, ileti: str = "") -> bool:
        """Belge işlemini çalıştırıp görünümleri baştan kurar (sayfa boyutu/kırpma gibi her sayfayı etkileyenler)."""
        try:
            fn()
        except BelgeHatasi as h:
            QMessageBox.warning(self, APP_NAME, str(h))
            return False
        self._belge_goster(min(self.goruntuleyici.gecerli_sayfa, self.belge.sayfa_sayisi - 1))
        if ileti:
            self.statusBar().showMessage(ileti, 6000)
        return True

    def _dialog_bilgisi(self):
        return self.belge.sayfa_sayisi, self.goruntuleyici.gecerli_sayfa, self.kucuk.secili_sayfalar()

    # --- sayfa işlemleri ---
    def kirp_ac(self):
        if not self.belge:
            return
        d = KirpPenceresi(*self._dialog_bilgisi(), parent=self)
        if not d.exec():
            return
        v = d.degerler()
        if v["otomatik"]:
            self._uygula(lambda: self.belge.otomatik_kirp(v["sayfalar"]), "Sayfalar içeriğine göre kırpıldı.")
        else:
            self._uygula(lambda: self.belge.kirp(v["sayfalar"], v["sol"], v["ust"], v["sag"], v["alt"]), "Sayfalar kırpıldı.")
        self.goruntuleyici.sayfaya_sigdir()

    def kirpmayi_kaldir(self):
        if self.belge:
            self._uygula(lambda: self.belge.kirpmayi_kaldir(self._hedef_sayfalar()), "Kırpma kaldırıldı.")

    def boyut_ac(self):
        if not self.belge:
            return
        d = BoyutPenceresi(*self._dialog_bilgisi(), parent=self)
        if d.exec():
            v = d.degerler()
            self._uygula(lambda: self.belge.sayfa_boyutu_degistir(v["sayfalar"], v["genislik"], v["yukseklik"]),
                         "Sayfa boyutu değiştirildi.")

    def filigran_ac(self):
        if not self.belge:
            return
        d = FiligranPenceresi(*self._dialog_bilgisi(), parent=self)
        if not d.exec():
            return
        v = d.degerler()
        if v["tur"] == "metin":
            self._uygula(lambda: self.belge.filigran_metin(v["sayfalar"], v["metin"], v["boyut"], v["renk"], v["aci"],
                                                           v["opaklik"], v["kalin"], v["on_plan"]), "Filigran eklendi.")
        else:
            self._uygula(lambda: self.belge.filigran_resim(v["sayfalar"], v["png"], v["genislik_orani"], v["on_plan"]),
                         "Filigran eklendi.")

    def filigran_temizle_ac(self):
        """Düzenle → Filigran Temizle…: kayıtlı dosyayı tarar; seçilenleri siler, temiz kopyayı yeni dosyaya yazar."""
        b = self.belge
        if not b:
            return
        if not b.yol or not b.yol.exists():
            QMessageBox.information(self, APP_NAME, "Filigran temizleme kayıtlı bir dosya ister. Önce belgeyi kaydedin.")
            return
        if b.degisti and QMessageBox.question(
                self, APP_NAME, "Belgede kaydedilmemiş değişiklikler var. Filigran temizleme dosyanın kayıtlı halinde çalışır, "
                                "bu değişiklikler temiz kopyaya girmez.\n\nYine de devam edilsin mi?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        from .filigran_penceresi import FiligranPenceresi
        d = FiligranPenceresi(self, str(b.yol), b._parola, engel_fn=self._acik_dosya_engeli)
        d.temizKaydedildi.connect(lambda yol: self._kopyayi_ac_sor(Path(yol), f"Filigransız kopya kaydedildi: {yol}"))
        d.exec()

    def filigran_kaldir_ac(self):
        if not self.belge:
            return
        d = FiligranKaldirPenceresi(*self._dialog_bilgisi(), self.belge.filigran_sayfalari(), parent=self)
        if d.exec():
            sayfalar = d.degerler()["sayfalar"]
            adet = []
            if self._uygula(lambda: adet.append(self.belge.filigranlari_kaldir(sayfalar))):
                self.statusBar().showMessage(f"{adet[0]} filigran kaldırıldı.", 6000)

    def _katman_kaldir_ac(self, baslik: str, ne: str, bulunan, kaldir, ileti: str):
        if not self.belge:
            return
        d = KatmanKaldirPenceresi(baslik, ne, *self._dialog_bilgisi(), bulunan(), parent=self)
        if d.exec():
            sayfalar = d.degerler()["sayfalar"]
            adet = []
            if self._uygula(lambda: adet.append(kaldir(sayfalar))):
                self.statusBar().showMessage(ileti.format(adet[0]), 6000)

    def ustalt_kaldir_ac(self):
        if self.belge:
            self._katman_kaldir_ac("Üstbilgi / Altbilgiyi Kaldır", "Üstbilgi/altbilgi metinleri", self.belge.ustalt_sayfalari,
                                   self.belge.ustalt_kaldir, "{} üstbilgi/altbilgi metni kaldırıldı.")

    def numara_kaldir_ac(self):
        if self.belge:
            self._katman_kaldir_ac("Sayfa Numaralarını Kaldır", "Sayfa numaraları", self.belge.sayfa_numarasi_sayfalari,
                                   self.belge.sayfa_numarasi_kaldir, "{} sayfa numarası kaldırıldı.")

    def arka_plan_ac(self):
        if not self.belge:
            return
        d = ArkaPlanPenceresi(*self._dialog_bilgisi(), parent=self)
        if d.exec():
            v = d.degerler()
            self._uygula(lambda: self.belge.arka_plan(v["sayfalar"], v["renk"], v["png"]), "Arka plan eklendi.")

    def ustalt_ac(self):
        if not self.belge:
            return
        d = UstAltBilgiPenceresi(*self._dialog_bilgisi(), parent=self)
        if d.exec():
            v = d.degerler()
            self._uygula(lambda: self.belge.ustalt_bilgi(v["sayfalar"], v["ust"], v["alt"], v["boyut"], v["renk"], v["kenar"]),
                         "Üstbilgi/altbilgi eklendi.")

    def numara_ac(self):
        if not self.belge:
            return
        d = SayfaNumarasiPenceresi(*self._dialog_bilgisi(), parent=self)
        if d.exec():
            v = d.degerler()
            self._uygula(lambda: self.belge.sayfa_numarasi_ekle(v["sayfalar"], v["konum"], v["bicim"], v["baslangic"],
                                                                v["boyut"], v["renk"]), "Sayfa numaraları eklendi.")

    # --- düzleştir, kalıcı silme ---
    def duzlestir_ac(self):
        if not self.belge:
            return
        d = DuzlestirPenceresi(self)
        if d.exec():
            v = d.degerler()
            self.goruntuleyici.ek_secimini_kaldir()
            self._uygula(lambda: self.belge.duzlestir(v["ek_aciklamalar"], v["form_alanlari"]), "Düzleştirildi.")

    def _kalici_silme_onayi(self, ne: str) -> bool:
        return QMessageBox.question(
            self, "Kalıcı Sil",
            f"{ne} KALICI olarak silinecek (metin ve resim pikselleri dahil).\n"
            "Dosyayı kaydettikten sonra geri getirilemez. Devam edilsin mi?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes

    def metin_ara_ve_sil(self):
        if not self.belge:
            return
        aranan, tamam = QInputDialog.getText(self, "Metni Ara ve Kalıcı Sil", "Belgede geçtiği her yerde silinecek metin:")
        if not tamam or not aranan.strip():
            return
        adet = len(self.belge.ara(aranan))
        if not adet:
            QMessageBox.information(self, APP_NAME, "Aranan metin belgede bulunamadı.")
            return
        if self._kalici_silme_onayi(f"“{aranan.strip()}” metninin {adet} yeri"):
            self._uygula(lambda: self.belge.kalici_sil_metin(aranan), f"{adet} yer kalıcı silindi.")

    # --- resim ve mühür ---
    def resim_sec(self):
        if not self.belge:
            return
        yol, _ = QFileDialog.getOpenFileName(self, "Resim Seç", self.ayarlar.value("son_klasor", ""),
                                             "Resimler (*.png *.jpg *.jpeg *.bmp *.gif)")
        if not yol:
            return
        img = QImage(yol)
        if img.isNull():
            QMessageBox.warning(self, APP_NAME, "Resim açılamadı.")
            return
        if max(img.width(), img.height()) > EN_BUYUK_RESIM_KENARI:
            img = img.scaled(EN_BUYUK_RESIM_KENARI, EN_BUYUK_RESIM_KENARI, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._yerlestirmeyi_hazirla(png_baytlari(img.convertToFormat(QImage.Format_ARGB32)), Path(yol).stem,
                                    VARSAYILAN_RESIM_GENISLIK, "resim")

    def _yerlestirmeyi_hazirla(self, png: bytes, ad: str, genislik: float, arac: str):
        if not self.belge:
            return
        self._bekleyen_png, self._bekleyen_ad, self._bekleyen_genislik = png, ad, genislik
        self._arac_eylemleri[arac].setChecked(True)
        self._arac_uygula()

    def _muhur_menusunu_doldur(self, menu: QMenu | None = None):
        menu = menu if isinstance(menu, QMenu) else self.m_muhur
        menu.clear()
        for metin in MUHUR_METINLERI:
            renk = MUHUR_RENKLERI[metin]
            pix = QPixmap.fromImage(muhur_resmi(metin, renk)).scaledToHeight(22, Qt.SmoothTransformation)
            menu.addAction(QIcon(pix), metin, lambda m=metin, r=renk: self._hazir_muhur(m, r))
        kayitli = imzalar.listele(self.muhur_klasoru)
        if kayitli:
            menu.addSeparator()
            for yol in kayitli:
                pix = QPixmap(str(yol)).scaledToHeight(22, Qt.SmoothTransformation)
                menu.addAction(QIcon(pix), muhur_adi(yol), lambda y=yol: self._kayitli_muhur(y))
        menu.addSeparator()
        menu.addAction(self.e_ozel_muhur)
        if kayitli:
            sil = menu.addMenu("Özel Mührü Sil")
            for yol in kayitli:
                sil.addAction(muhur_adi(yol), lambda y=yol: self._ozel_muhuru_sil(y))

    def _hazir_muhur(self, metin: str, renk: str):
        self._yerlestirmeyi_hazirla(png_baytlari(muhur_resmi(metin, renk)), metin, VARSAYILAN_MUHUR_GENISLIK, "muhur")

    def _kayitli_muhur(self, yol: Path):
        self._yerlestirmeyi_hazirla(imzalar.oku(yol), muhur_adi(yol), VARSAYILAN_MUHUR_GENISLIK, "muhur")

    def ozel_muhur_olustur(self):
        d = MuhurPenceresi(self)
        if d.exec():
            try:
                yol = imzalar.kaydet(self.muhur_klasoru, d.png(), d.ad())
            except (BelgeHatasi, OSError) as h:
                QMessageBox.warning(self, APP_NAME, str(h))
                return
            if self.belge:
                self._kayitli_muhur(yol)

    def _ozel_muhuru_sil(self, yol: Path):
        if QMessageBox.question(self, "Mührü Sil", f"“{muhur_adi(yol)}” mührü silinsin mi?",
                                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes:
            imzalar.sil(yol)

    # --- görüntüleyiciden gelen eylemler ---
    def _duzenleme_eylemi(self, arac: str, sayfa: int, veri) -> bool:
        b = self.belge
        if arac == "redaction":
            p1, p2 = veri
            rect = (min(p1[0], p2[0]), min(p1[1], p2[1]), max(p1[0], p2[0]), max(p1[1], p2[1]))
            if self._kalici_silme_onayi("Seçilen alan"):
                self._dene(lambda: b.kalici_sil(sayfa, [rect]), [sayfa])
            return True
        if arac in ("resim", "muhur"):
            self._png_yerlestir(arac, sayfa, veri)
            return True
        if arac == "metin_duzenle":
            self._metin_duzenle(sayfa, veri)
            return True
        if arac == "boyutla":
            xref, rect = veri
            if self._dene(lambda: b.ek_boyutlandir(sayfa, xref, rect), [sayfa]):
                self._ek_yeniden_sec(sayfa, xref)
            return True
        return False

    def _png_yerlestir(self, arac: str, sayfa: int, veri):
        if self._bekleyen_png is None:
            QMessageBox.information(self, APP_NAME, "Önce Düzenle menüsünden bir resim ya da mühür seçin.")
            return
        img = QImage.fromData(self._bekleyen_png)
        if img.isNull():
            QMessageBox.warning(self, APP_NAME, "Resim okunamadı.")
            return
        p1, p2 = veri
        oran = img.height() / img.width()
        if p2 is None:
            gen = min(self._bekleyen_genislik, self.belge.sayfa_boyutu(sayfa)[0] - 10)
            rect = (p1[0] - gen / 2, p1[1] - gen * oran / 2, p1[0] + gen / 2, p1[1] + gen * oran / 2)
        else:  # sürüklenen kutuya sığdır (en/boy oranı korunur)
            x0, y0, x1, y1 = min(p1[0], p2[0]), min(p1[1], p2[1]), max(p1[0], p2[0]), max(p1[1], p2[1])
            gen = min(x1 - x0, (y1 - y0) / oran)
            rect = (x0, y0, x0 + gen, y0 + gen * oran)
        g, y = self.belge.sayfa_boyutu(sayfa)
        x0, y0, x1, y1 = rect
        dx = -x0 if x0 < 0 else (g - x1 if x1 > g else 0)
        dy = -y0 if y0 < 0 else (y - y1 if y1 > y else 0)
        rect = (x0 + dx, y0 + dy, x1 + dx, y1 + dy)
        yeni: list[int] = []
        if self._dene(lambda: yeni.append(self.belge.muhur_ekle(sayfa, rect, self._bekleyen_png, self._yazar,
                                                                self._bekleyen_ad)), [sayfa]):
            self._arac_eylemleri[ARAC_DUZENLE].setChecked(True)  # yerleştirdikten sonra seç/taşı/boyutlandır
            self._arac_uygula()
            self._ek_yeniden_sec(sayfa, yeni[0])

    def _metin_duzenle(self, sayfa: int, nokta):
        blok = self.belge.metin_blogu(sayfa, nokta)
        if blok is None:
            self.statusBar().showMessage("Burada düzenlenebilir metin yok (taranmış/resim sayfa olabilir).", 5000)
            return
        d = MetinPenceresi(self, "Metni Düzenle", blok["metin"], stil=True, boyut=blok["boyut"],
                           kalin=blok["kalin"], italik=blok["italik"])
        if d.exec() and d.metin():
            kullanilan = []
            if self._dene(lambda: kullanilan.append(self.belge.metin_degistir(
                    sayfa, blok["rect"], d.metin(), d.boyut.value(), blok["renk"], d.kalin.isChecked(), d.italik.isChecked(),
                    orijinal=blok)), [sayfa]):
                self.statusBar().showMessage(f"Metin değiştirildi · yazı tipi: {kullanilan[0]}", 6000)
