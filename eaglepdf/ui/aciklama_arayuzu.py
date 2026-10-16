"""Ana pencerenin Faz 2 bölümü: açıklama araç çubuğu, araç eylemleri, imza, bağlantı, form, geri al/yinele.

`AnaPencere`ye karışım (mixin) olarak eklenir; pencerenin `belge`, `goruntuleyici`, `kucuk`, `paneller`,
`yer_imleri`, `ayarlar`, `_eylem` ve `_arac_eylemleri` üyelerini kullanır.
"""

import os
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import QActionGroup, QColor, QDesktopServices, QIcon, QImage, QPixmap
from PySide6.QtWidgets import QColorDialog, QInputDialog, QMenu, QMessageBox, QToolBar, QToolButton

from .. import APP_NAME
from ..core import imzalar
from ..core.belge import BelgeHatasi
from . import simgeler
from .dialoglar import BaglantiPenceresi, ImzaPenceresi, MetinPenceresi
from .goruntuleyici import ARAC_DUZENLE, ISARET_ARACLARI
from .paneller import AciklamaPaneli

# (kimlik, menü adı, simge, varsayılan renk)
ACIKLAMA_ARACLARI = [
    (ARAC_DUZENLE, "Seç / Düzenle", "sec_ok", None),
    ("vurgu", "Vurgula", "vurgu", "#ffeb3b"),
    ("alti", "Altını Çiz", "alti", "#c62828"),
    ("ustu", "Üstünü Çiz", "ustu", "#c62828"),
    ("dalga", "Dalgalı Çizgi", "dalga", "#c62828"),
    ("ciz", "Serbest Çizim", "kalem", "#c62828"),
    ("not", "Not", "not", "#ffc107"),
    ("metin", "Metin Kutusu", "metin", "#111111"),
    ("cizgi", "Çizgi", "cizgi", "#c62828"),
    ("ok", "Ok", "ok", "#c62828"),
    ("dikdortgen", "Dikdörtgen", "dikdortgen", "#c62828"),
    ("elips", "Elips", "elips", "#c62828"),
    ("baglanti", "Bağlantı", "baglanti", None),
    ("imza", "İmza Yerleştir", "imza", None),
]
RENK_PALETI = ["#111111", "#c62828", "#e65100", "#ffeb3b", "#2e7d32", "#1565c0", "#6a1b9a", "#ffffff"]
KALINLIKLAR = (1, 2, 3, 4, 6, 8)
VARSAYILAN_IMZA_GENISLIK = 150.0   # pt
VARSAYILAN_METIN_KUTUSU = (200.0, 40.0)


def renk_simgesi(renk: str) -> QIcon:
    pix = QPixmap(20, 20)
    pix.fill(Qt.transparent)
    from PySide6.QtGui import QPainter
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(renk))
    p.setPen(QColor("#9e9e9e"))
    p.drawRoundedRect(2, 2, 16, 16, 4, 4)
    p.end()
    return QIcon(pix)


class AciklamaArayuzu:
    # --- kurulum ---
    def _aciklama_kur(self):
        self._renkler = {k: self.ayarlar.value(f"renk_{k}", v) for k, _a, _i, v in ACIKLAMA_ARACLARI if v}
        self._kalinlik = float(self.ayarlar.value("kalinlik", 2))
        self._metin_boyutu = 14
        self._yazar = str(self.ayarlar.value("yazar", "") or os.environ.get("USERNAME", ""))
        self.imza_klasoru = Path(self.ayarlar.fileName()).parent / "imzalar"
        self._aktif_imza: Path | None = None
        yol = self.ayarlar.value("aktif_imza", "")
        if yol and Path(yol).is_file():
            self._aktif_imza = Path(yol)

        # araç çubuğu (ikinci satır)
        self.ek_arac = QToolBar()
        self.ek_arac.setMovable(False)
        self.ek_arac.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.ek_arac.setIconSize(QSize(20, 20))
        self.centralWidget().layout().insertWidget(2, self.ek_arac)

        self.arac_grubu_ek = {}
        for kimlik, ad, simge, _renk in ACIKLAMA_ARACLARI:
            e = self._eylem(ad, self._arac_uygula, simge=simge, isaretli=False)
            self._arac_grubu.addAction(e)
            self._arac_eylemleri[kimlik] = e
        a = self._arac_eylemleri
        for grup in ((ARAC_DUZENLE,), ("vurgu", "alti", "ustu", "dalga"), ("ciz", "not", "metin"),
                     ("cizgi", "ok", "dikdortgen", "elips"), ("baglanti", "imza")):
            for k in grup:
                self.ek_arac.addAction(a[k])
            self.ek_arac.addSeparator()

        # renk ve kalınlık düğmeleri
        self.renk_dugme = QToolButton()
        self.renk_dugme.setToolTip("Renk")
        self.renk_dugme.setPopupMode(QToolButton.InstantPopup)
        self.renk_menu = QMenu(self.renk_dugme)
        for r in RENK_PALETI:
            self.renk_menu.addAction(renk_simgesi(r), r.upper(), lambda r=r: self._renk_sec(r))
        self.renk_menu.addSeparator()
        self.renk_menu.addAction("Diğer renk…", self._renk_diger)
        self.renk_dugme.setMenu(self.renk_menu)
        self.ek_arac.addWidget(self.renk_dugme)
        self.kalinlik_dugme = QToolButton()
        self.kalinlik_dugme.setIcon(simgeler.simge("kalinlik"))
        self.kalinlik_dugme.setToolTip("Çizgi kalınlığı")
        self.kalinlik_dugme.setPopupMode(QToolButton.InstantPopup)
        km = QMenu(self.kalinlik_dugme)
        for k in KALINLIKLAR:
            km.addAction(f"{k} pt", lambda k=k: self._kalinlik_sec(k))
        self.kalinlik_dugme.setMenu(km)
        self.ek_arac.addWidget(self.kalinlik_dugme)
        self.ek_arac.addSeparator()

        # geri al / yinele, form
        self.e_geri = self._eylem("Geri Al", self.geri_al, "Ctrl+Z", simge="geri")
        self.e_yinele = self._eylem("Yinele", self.yinele, "Ctrl+Y", simge="yinele")
        self.e_form = self._eylem("Form Alanlarını Göster", self._form_uygula, simge="form", isaretli=True)
        self.e_yazar = self._eylem("Yazar Adı…", self.yazar_sor)
        self.e_yeni_imza = self._eylem("Yeni İmza Oluştur…", self.yeni_imza)
        for e in (self.e_geri, self.e_yinele, self.e_form):
            self.ek_arac.addAction(e)

        # menüler
        self.m_duzen.insertAction(self.m_duzen.actions()[0], self.e_yinele)
        self.m_duzen.insertAction(self.e_yinele, self.e_geri)
        self.m_duzen.insertSeparator(self.m_duzen.actions()[2])
        self.m_aciklama = QMenu("&Açıklama", self)
        self.menuBar().insertMenu(self.m_sayfa.menuAction(), self.m_aciklama)
        for grup in ((ARAC_DUZENLE,), ("vurgu", "alti", "ustu", "dalga"), ("ciz", "not", "metin"),
                     ("cizgi", "ok", "dikdortgen", "elips"), ("baglanti",)):
            for k in grup:
                self.m_aciklama.addAction(a[k])
            self.m_aciklama.addSeparator()
        self.m_imza = self.m_aciklama.addMenu(simgeler.simge("imza"), "İmza")
        self.m_imza.aboutToShow.connect(self._imza_menusunu_doldur)
        self.m_aciklama.addSeparator()
        self.m_aciklama.addAction(self.e_form)
        self.m_aciklama.addAction(self.e_yazar)

        # paneller
        self.aciklama_paneli = AciklamaPaneli()
        self.paneller.addTab(self.aciklama_paneli, "Açıklamalar")
        self.aciklama_paneli.ekSecildi.connect(self._panelden_ek_sec)
        self.aciklama_paneli.silmeIstendi.connect(self._panelden_sil)
        self.yer_imleri.degisti.connect(self._yer_imleri_degisti)

        g = self.goruntuleyici
        g.aracEylemi.connect(self._arac_eylemi)
        g.ekSecildi.connect(self._ek_secildi)
        g.baglantiTiklandi.connect(self._baglanti_ac)
        g.sagTiklandi.connect(self._sag_tik_menusu)
        g.formDegisti.connect(self._form_degisti)

        self._belge_eylemleri += [self.e_form, self.e_yazar, self.e_yeni_imza] + [self._arac_eylemleri[k[0]] for k in ACIKLAMA_ARACLARI]
        self.form_gorunum_yukle()
        self._arac_degisti("el")

    def form_gorunum_yukle(self):
        acik = str(self.ayarlar.value("form_goster", True)).lower() in ("true", "1")
        self.e_form.setChecked(acik)
        self.goruntuleyici.form_acik_ata(acik)

    # --- araç seçimi, renk, kalınlık ---
    def _arac_degisti(self, kimlik: str):
        """Araç değişince renk/kalınlık düğmelerini ve görüntüleyiciyi hazırlar."""
        renkli = kimlik in self._renkler
        kalinlikli = kimlik in ("ciz", "cizgi", "ok", "dikdortgen", "elips")
        self.renk_dugme.setEnabled(renkli or kimlik == ARAC_DUZENLE)
        self.kalinlik_dugme.setEnabled(kalinlikli)
        self._renk_dugmesini_boya(self._renkler.get(kimlik, "#9e9e9e"))
        g = self.goruntuleyici
        g.renk = self._renkler.get(kimlik, "#c62828")
        g.kalinlik = self._kalinlik
        if kimlik == "imza" and self.belge and self._aktif_imza is None:
            self.yeni_imza()
            if self._aktif_imza is None:
                self._arac_eylemleri["el"].setChecked(True)
                self._arac_uygula()
        ipuclari = {
            ARAC_DUZENLE: "Bir açıklamaya tıklayıp seçin; sürükleyerek taşıyın, çift tıklayıp düzenleyin, Del ile silin.",
            "vurgu": "İşaretlenecek metni fareyle seçin.", "alti": "Altı çizilecek metni fareyle seçin.",
            "ustu": "Üstü çizilecek metni fareyle seçin.", "dalga": "Dalgalı çizgi çekilecek metni seçin.",
            "ciz": "Sayfada fareyi basılı tutarak çizin.", "not": "Not eklenecek yere tıklayın.",
            "metin": "Metin kutusunun yerini sürükleyerek belirleyin (ya da tıklayın).",
            "cizgi": "Başlangıçtan bitişe sürükleyin.", "ok": "Başlangıçtan ok ucuna sürükleyin.",
            "dikdortgen": "Köşeden köşeye sürükleyin.", "elips": "Çerçeveyi sürükleyerek çizin.",
            "baglanti": "Bağlantı olacak alanı sürükleyerek seçin.",
            "imza": "İmzanın yerini sürükleyin (ya da tıklayın).",
        }
        ipuclari.update(getattr(self, "_ek_ipuclari", {}))
        if kimlik in ipuclari:
            self.statusBar().showMessage(ipuclari[kimlik], 6000)

    def _etkin_arac(self) -> str:
        for k, e in self._arac_eylemleri.items():
            if e.isChecked():
                return k
        return "el"

    def _renk_dugmesini_boya(self, renk: str):
        self.renk_dugme.setIcon(renk_simgesi(renk))

    def _renk_sec(self, renk: str):
        arac = self._etkin_arac()
        if arac in self._renkler:
            self._renkler[arac] = renk
            self.ayarlar.setValue(f"renk_{arac}", renk)
            self.goruntuleyici.renk = renk
        self._renk_dugmesini_boya(renk)
        ek = self.goruntuleyici.secili_ek
        if arac == ARAC_DUZENLE and ek and self.belge:
            self._dene(lambda: self.belge.ek_renk_degistir(ek.sayfa, ek.xref, renk), [ek.sayfa])
            self._ek_yeniden_sec(ek.sayfa, ek.xref)

    def _renk_diger(self):
        arac = self._etkin_arac()
        baslangic = QColor(self._renkler.get(arac, "#c62828"))
        renk = QColorDialog.getColor(baslangic, self, "Renk Seç")
        if renk.isValid():
            self._renk_sec(renk.name())

    def _kalinlik_sec(self, k: float):
        self._kalinlik = float(k)
        self.goruntuleyici.kalinlik = self._kalinlik
        self.ayarlar.setValue("kalinlik", k)

    def yazar_sor(self):
        ad, tamam = QInputDialog.getText(self, "Yazar Adı", "Açıklamalarda görünecek ad:", text=self._yazar)
        if tamam:
            self._yazar = ad.strip()
            self.ayarlar.setValue("yazar", self._yazar)

    # --- belge değişikliği sonrası tazeleme ---
    def _ek_degisti(self, sayfalar: list[int]):
        for s in set(sayfalar):
            self.goruntuleyici.yenile_sayfa(s)
            self.kucuk.yenile(s)
        self.aciklama_paneli.doldur(self.belge.ek_listele() if self.belge else [])
        self._durumu_guncelle()

    def _dene(self, fn, sayfalar: list[int]) -> bool:
        """Belge işlemini çalıştırır; hata olursa Türkçe uyarı gösterir, başarıda görünümleri tazeler."""
        try:
            fn()
        except BelgeHatasi as h:
            QMessageBox.warning(self, APP_NAME, str(h))
            return False
        self._ek_degisti(sayfalar)
        return True

    def aciklamalari_tazele(self):
        self.aciklama_paneli.doldur(self.belge.ek_listele() if self.belge else [])

    # --- görüntüleyiciden gelen eylemler ---
    def _arac_eylemi(self, arac: str, sayfa: int, veri):
        if not self.belge:
            return
        if self._duzenleme_eylemi(arac, sayfa, veri) or self._ocr_eylemi(arac, sayfa, veri):
            return
        b, renk, yazar = self.belge, self._renkler.get(arac, "#c62828"), self._yazar
        if arac in ISARET_ARACLARI:
            def isle():
                for s, satirlar in veri.items():
                    b.ek_isaret(s, arac, satirlar, renk, yazar)
            self._dene(isle, list(veri))
        elif arac == "ciz":
            def isle():
                for cizgi in veri:
                    b.ek_cizim(sayfa, [cizgi], renk, self._kalinlik, yazar)
            self._dene(isle, [sayfa])
        elif arac == "not":
            d = MetinPenceresi(self, "Not Ekle")
            if d.exec() and d.metin():
                self._dene(lambda: b.ek_not(sayfa, veri, d.metin(), renk, yazar), [sayfa])
        elif arac == "metin":
            self._metin_kutusu_ekle(sayfa, veri, renk, yazar)
        elif arac in ("cizgi", "ok", "dikdortgen", "elips"):
            self._dene(lambda: b.ek_sekil(sayfa, arac, veri[0], veri[1], renk, self._kalinlik, None, yazar), [sayfa])
        elif arac == "baglanti":
            self._baglanti_ekle(sayfa, veri)
        elif arac == "imza":
            self._imza_yerlestir(sayfa, veri)
        elif arac == "tasi":
            xref, dx, dy = veri
            yeni = []
            if self._dene(lambda: yeni.append(b.ek_tasi(sayfa, xref, dx, dy)), [sayfa]):
                self._ek_yeniden_sec(sayfa, yeni[0])
        elif arac == "ek_duzenle":
            self.ek_metnini_duzenle(veri)

    def _metin_kutusu_ekle(self, sayfa: int, veri, renk: str, yazar: str):
        p1, p2 = veri
        if p2 is None:
            gen, yuk = VARSAYILAN_METIN_KUTUSU
            rect = (p1[0], p1[1], p1[0] + gen, p1[1] + yuk)
        else:
            rect = (min(p1[0], p2[0]), min(p1[1], p2[1]), max(p1[0], p2[0]), max(p1[1], p2[1]))
        d = MetinPenceresi(self, "Metin Kutusu", stil=True, boyut=self._metin_boyutu)
        if d.exec() and d.metin():
            self._metin_boyutu = d.boyut.value()
            self._dene(lambda: self.belge.ek_metin_kutusu(
                sayfa, rect, d.metin(), self._metin_boyutu, renk, d.kalin.isChecked(), d.italik.isChecked(), yazar=yazar),
                [sayfa])

    def ek_metnini_duzenle(self, ek):
        b = self.belge
        if ek.tur == "FreeText":
            d = MetinPenceresi(self, "Metin Kutusunu Düzenle", ek.metin)
        else:
            d = MetinPenceresi(self, "Not / Yorum", ek.metin)
        if d.exec():
            if ek.tur == "FreeText" and not d.metin():
                return
            if self._dene(lambda: b.ek_metin_degistir(ek.sayfa, ek.xref, d.metin()), [ek.sayfa]):
                self._ek_yeniden_sec(ek.sayfa, ek.xref)

    def _ek_yeniden_sec(self, sayfa: int, xref: int):
        for e in self.belge.ek_listele([sayfa]):
            if e.xref == xref:
                self.goruntuleyici.ek_secimini_ayarla(e)
                return
        self.goruntuleyici.ek_secimini_ayarla(None)

    def _ek_secildi(self, ek):
        if ek is not None:
            self._renk_dugmesini_boya(ek.renk or "#9e9e9e")

    def ek_sil_secili(self) -> bool:
        ek = self.goruntuleyici.secili_ek
        if not ek or not self.belge:
            return False
        self.goruntuleyici.ek_secimini_kaldir()
        self._dene(lambda: self.belge.ek_sil(ek.sayfa, [ek.xref]), [ek.sayfa])
        return True

    # --- bağlantılar ---
    def _baglanti_ekle(self, sayfa: int, veri):
        p1, p2 = veri
        d = BaglantiPenceresi(self.belge.sayfa_sayisi, self)
        if not d.exec():
            return
        uri, hedef = d.sonuc()
        rect = (min(p1[0], p2[0]), min(p1[1], p2[1]), max(p1[0], p2[0]), max(p1[1], p2[1]))
        self._dene(lambda: self.belge.baglanti_ekle(sayfa, rect, uri=uri, hedef_sayfa=hedef), [sayfa])

    def _baglanti_ac(self, baglanti: dict):
        if baglanti["tur"] == "sayfa" and baglanti["hedef_sayfa"] >= 0:
            self.goruntuleyici.git(baglanti["hedef_sayfa"])
        elif baglanti["tur"] == "uri" and baglanti["uri"]:
            if baglanti["uri"].lower().startswith(("http://", "https://", "mailto:")):
                QDesktopServices.openUrl(QUrl(baglanti["uri"]))
            else:
                self.statusBar().showMessage(f"Bu bağlantı türü açılmıyor: {baglanti['uri']}", 5000)

    def _sag_tik_menusu(self, tur: str, sayfa: int, veri, genel):
        if not self.belge:
            return
        menu = QMenu(self)
        if tur == "ek":
            menu.addAction("Metni / Yorumu Düzenle…", lambda: self.ek_metnini_duzenle(veri))
            menu.addAction("Rengi Değiştir…", self._renk_diger)
            menu.addSeparator()
            menu.addAction("Sil", self.ek_sil_secili)
        elif tur == "baglanti":
            menu.addAction("Bağlantıyı Sil", lambda: self._dene(
                lambda: self.belge.baglanti_sil(sayfa, veri["xref"]), [sayfa]))
        else:
            return
        menu.exec(genel)

    # --- açıklama paneli ---
    def _panelden_ek_sec(self, ek):
        self.goruntuleyici.git(ek.sayfa, ek.rect[1])
        if self._etkin_arac() == ARAC_DUZENLE:
            self.goruntuleyici.ek_secimini_ayarla(ek)

    def _panelden_sil(self, liste: list):
        if len(liste) > 1 and QMessageBox.question(
                self, "Açıklamaları Sil", f"{len(liste)} açıklama silinsin mi?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        per_sayfa: dict[int, list[int]] = {}
        for e in liste:
            per_sayfa.setdefault(e.sayfa, []).append(e.xref)
        self.goruntuleyici.ek_secimini_kaldir()

        def isle():
            for s, xrefler in per_sayfa.items():
                self.belge.ek_sil(s, xrefler)
        self._dene(isle, list(per_sayfa))

    # --- imza ---
    def _imza_menusunu_doldur(self):
        self.m_imza.clear()
        imzalar_listesi = imzalar.listele(self.imza_klasoru)
        for n, yol in enumerate(imzalar_listesi, 1):
            pix = QPixmap(str(yol)).scaledToHeight(24, Qt.SmoothTransformation)
            baslik = f"İmza {n}" + ("  ✓" if yol == self._aktif_imza else "")
            self.m_imza.addAction(QIcon(pix), baslik, lambda y=yol: self._imza_kullan(y))
        if imzalar_listesi:
            self.m_imza.addSeparator()
        self.m_imza.addAction(self.e_yeni_imza)
        if imzalar_listesi:
            sil_menu = self.m_imza.addMenu("İmzayı Sil")
            for n, yol in enumerate(imzalar_listesi, 1):
                sil_menu.addAction(f"İmza {n}", lambda y=yol: self._imza_sil(y))

    def _imza_kullan(self, yol: Path):
        self._aktif_imza = yol
        self.ayarlar.setValue("aktif_imza", str(yol))
        self._arac_eylemleri["imza"].setChecked(True)
        self._arac_uygula()

    def _imza_sil(self, yol: Path):
        if QMessageBox.question(self, "İmzayı Sil", "Kayıtlı imza silinsin mi?", QMessageBox.Yes | QMessageBox.No,
                                QMessageBox.No) != QMessageBox.Yes:
            return
        imzalar.sil(yol)
        if self._aktif_imza == yol:
            self._aktif_imza = None
            self.ayarlar.remove("aktif_imza")

    def yeni_imza(self):
        d = ImzaPenceresi(self)
        if d.exec() and d.png():
            try:
                yol = imzalar.kaydet(self.imza_klasoru, d.png())
            except (BelgeHatasi, OSError) as h:
                QMessageBox.warning(self, APP_NAME, str(h))
                return
            self._aktif_imza = yol
            self.ayarlar.setValue("aktif_imza", str(yol))
            self.statusBar().showMessage("İmza kaydedildi. Yerleştirmek için sayfada sürükleyin.", 6000)

    def _imza_yerlestir(self, sayfa: int, veri):
        if self._aktif_imza is None or not self._aktif_imza.is_file():
            QMessageBox.information(self, APP_NAME, "Önce Açıklama → İmza menüsünden bir imza oluşturun.")
            return
        png = imzalar.oku(self._aktif_imza)
        img = QImage.fromData(png)
        if img.isNull():
            QMessageBox.warning(self, APP_NAME, "İmza dosyası okunamadı.")
            return
        p1, p2 = veri
        oran = img.height() / img.width()
        if p2 is None:
            gen = VARSAYILAN_IMZA_GENISLIK
            rect = (p1[0] - gen / 2, p1[1] - gen * oran / 2, p1[0] + gen / 2, p1[1] + gen * oran / 2)
        else:
            rect = (min(p1[0], p2[0]), min(p1[1], p2[1]), max(p1[0], p2[0]), max(p1[1], p2[1]))
        g, y = self.belge.sayfa_boyutu(sayfa)
        x0, y0, x1, y1 = rect  # sayfa dışına taşmasın
        dx = -x0 if x0 < 0 else (g - x1 if x1 > g else 0)
        dy = -y0 if y0 < 0 else (y - y1 if y1 > y else 0)
        rect = (x0 + dx, y0 + dy, x1 + dx, y1 + dy)
        self._dene(lambda: self.belge.resim_yerlestir(sayfa, rect, png), [sayfa])

    # --- form ---
    def _form_uygula(self, *_):
        acik = self.e_form.isChecked()
        self.goruntuleyici.form_acik_ata(acik)
        self.ayarlar.setValue("form_goster", acik)

    def _form_degisti(self, sayfa: int, xref: int, deger):
        if self.belge:
            self._dene(lambda: self.belge.form_degeri_yaz(sayfa, xref, deger), [sayfa])

    # --- yer imleri ---
    def _yer_imleri_degisti(self, liste: list):
        if not self.belge:
            return
        try:
            self.belge.yer_imleri_ayarla(liste)
        except BelgeHatasi as h:
            QMessageBox.warning(self, APP_NAME, str(h))
            self.yer_imleri.belge_ata(self.belge)
            return
        self._durumu_guncelle()

    # --- geri al / yinele ---
    def geri_al(self):
        if self.belge and self.belge.geri_al():
            self._geri_alma_sonrasi()

    def yinele(self):
        if self.belge and self.belge.yinele():
            self._geri_alma_sonrasi()

    def _geri_alma_sonrasi(self):
        self._belge_goster(min(self.goruntuleyici.gecerli_sayfa, self.belge.sayfa_sayisi - 1))

    def _aciklama_durumu(self):
        """`_durumu_guncelle` içinden çağrılır: geri al/yinele ve araçların etkinliği."""
        var = self.belge is not None
        self.e_geri.setEnabled(var and self.belge.geri_alinabilir_mi)
        self.e_yinele.setEnabled(var and self.belge.yinelenebilir_mi)
        for k, e in self._arac_eylemleri.items():
            e.setEnabled(var)
