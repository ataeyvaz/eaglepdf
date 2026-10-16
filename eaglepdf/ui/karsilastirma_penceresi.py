"""İki PDF'i karşılaştırma penceresi: sayfa listesi, değişen yerleri kırmızı gösteren görüntü ve kelime farkları."""

import html
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QDialog, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QProgressBar, QPushButton,
    QScrollArea, QSplitter, QTabWidget, QTextBrowser, QVBoxLayout, QWidget,
)

from ..core import donustur
from ..core.belge import BelgeHatasi
from .donusum_penceresi import IsParcacigi

EN_COK_GOSTERILEN_FARK = 60  # bir sayfada listelenen en çok kelime grubu


def fark_ozeti(f: donustur.SayfaFarki) -> str:
    if f.yalniz:
        return "yalnızca birinci belgede var" if f.yalniz == "a" else "yalnızca ikinci belgede var"
    if not f.farkli:
        return "fark yok"
    parcalar = []
    if f.eklenen or f.silinen:
        parcalar.append("metin değişti")
    if f.piksel_orani > 0.0005:
        parcalar.append(f"görüntü %{f.piksel_orani * 100:.1f}".replace(".", ",") + " değişti")
    return ", ".join(parcalar)


def fark_html(f: donustur.SayfaFarki) -> str:
    if f.yalniz:
        return f"<p>{html.escape(fark_ozeti(f))}.</p>"
    if not (f.eklenen or f.silinen):
        return "<p>Bu sayfada kelime farkı yok" + (" (yalnızca görüntü farkı olabilir: yerleşim, resim, çizim)." if f.farkli else ".") + "</p>"
    parca = []
    for baslik, liste, renk in (("Silinen (birinci belgede olup ikincide olmayan)", f.silinen, "#c62828"),
                                ("Eklenen (ikinci belgede olup birincide olmayan)", f.eklenen, "#2e7d32")):
        if liste:
            ogeler = "".join(f'<li><span style="color:{renk}">{html.escape(m)}</span></li>' for m in liste[:EN_COK_GOSTERILEN_FARK])
            fazla = f"<li>… ve {len(liste) - EN_COK_GOSTERILEN_FARK} fark daha</li>" if len(liste) > EN_COK_GOSTERILEN_FARK else ""
            parca.append(f"<p><b>{baslik}</b></p><ul>{ogeler}{fazla}</ul>")
    return "".join(parca)


class KarsilastirmaPenceresi(QDialog):
    def __init__(self, yol_a: str = "", yol_b: str = "", klasor: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("PDF Karşılaştır")
        self.resize(980, 700)
        self._klasor = klasor
        self.sonuclar: list[donustur.SayfaFarki] = []
        self.is_parcacigi: IsParcacigi | None = None
        duzen = QVBoxLayout(self)
        self.kutu_a, self.kutu_b = QLineEdit(yol_a), QLineEdit(yol_b)
        for etiket, kutu in (("Birinci belge (eski):", self.kutu_a), ("İkinci belge (yeni):", self.kutu_b)):
            satir = QHBoxLayout()
            satir.addWidget(QLabel(etiket))
            satir.addWidget(kutu, 1)
            sec = QPushButton("Seç…")
            sec.setAutoDefault(False)
            sec.clicked.connect(lambda _=False, k=kutu: self._sec(k))
            satir.addWidget(sec)
            duzen.addLayout(satir)
        ust = QHBoxLayout()
        self.dugme = QPushButton("Karşılaştır")
        self.dugme.setDefault(True)
        self.dugme.clicked.connect(self.basla)
        self.ozet = QLabel("")
        self.ozet.setWordWrap(True)
        self.ilerleme = QProgressBar()
        self.ilerleme.hide()
        ust.addWidget(self.dugme)
        ust.addWidget(self.ozet, 1)
        duzen.addLayout(ust)
        duzen.addWidget(self.ilerleme)

        self.liste = QListWidget()
        self.liste.currentRowChanged.connect(self._sayfa_goster)
        self.sekmeler = QTabWidget()
        self.gorsel = QLabel("Karşılaştırma sonucu burada görünür.")
        self.gorsel.setAlignment(Qt.AlignCenter)
        kaydir = QScrollArea()
        kaydir.setWidget(self.gorsel)
        kaydir.setWidgetResizable(True)
        self.metin = QTextBrowser()
        self.sekmeler.addTab(kaydir, "Görsel fark (kırmızı = değişen)")
        self.sekmeler.addTab(self.metin, "Metin farkı")
        ayirac = QSplitter(Qt.Horizontal)
        ayirac.addWidget(self.liste)
        ayirac.addWidget(self.sekmeler)
        ayirac.setSizes([240, 740])
        duzen.addWidget(ayirac, 1)
        kapat = QPushButton("Kapat")
        kapat.setAutoDefault(False)
        kapat.clicked.connect(self.reject)
        alt = QHBoxLayout()
        alt.addStretch()
        alt.addWidget(kapat)
        duzen.addLayout(alt)

    def _sec(self, kutu: QLineEdit):
        yol, _ = QFileDialog.getOpenFileName(self, "PDF Seç", kutu.text() or self._klasor, "PDF belgeleri (*.pdf)")
        if yol:
            kutu.setText(yol)

    def basla(self):
        if self.is_parcacigi is not None:
            return
        a, b = self.kutu_a.text().strip(), self.kutu_b.text().strip()
        if not a or not b:
            self.ozet.setText("⚠ İki belgeyi de seçin.")
            return
        if Path(a).resolve() == Path(b).resolve():
            self.ozet.setText("⚠ Aynı dosyayı kendisiyle karşılaştırmanın anlamı yok.")
            return
        self.ozet.setText("Karşılaştırılıyor…")
        self.dugme.setEnabled(False)
        self.liste.clear()
        self.ilerleme.show()
        self.ilerleme.setValue(0)

        def gorev(il):
            self.sonuclar = donustur.karsilastir(a, b, ilerleme=il)
            return [], ""
        self.is_parcacigi = IsParcacigi([("karşılaştırma", gorev)], self)
        self.is_parcacigi.yuzde.connect(self.ilerleme.setValue)
        self.is_parcacigi.dosyaBitti.connect(self._bitti)
        self.is_parcacigi.finished.connect(self._temizle)
        self.is_parcacigi.start()

    def _temizle(self):
        self.is_parcacigi = None
        self.dugme.setEnabled(True)
        self.ilerleme.hide()

    def _bitti(self, _sira, basarili: bool, mesaj: str, _ciktilar):
        if not basarili:
            self.ozet.setText(f"⚠ {mesaj}")
            return
        farkli = [f for f in self.sonuclar if f.farkli]
        self.ozet.setText(f"{len(self.sonuclar)} sayfa karşılaştırıldı: {len(farkli)} sayfada fark var." if farkli
                          else f"{len(self.sonuclar)} sayfa karşılaştırıldı: belgeler aynı görünüyor.")
        for f in self.sonuclar:
            oge = QListWidgetItem(f"Sayfa {f.sayfa + 1} — {fark_ozeti(f)}")
            oge.setForeground(QColor("#c62828" if f.farkli else "#616161"))
            self.liste.addItem(oge)
        if farkli:
            self.liste.setCurrentRow(self.sonuclar.index(farkli[0]))
        elif self.sonuclar:
            self.liste.setCurrentRow(0)

    def _sayfa_goster(self, satir: int):
        if not 0 <= satir < len(self.sonuclar):
            return
        f = self.sonuclar[satir]
        if f.fark_png:
            pix = QPixmap()
            pix.loadFromData(f.fark_png)
            self.gorsel.setPixmap(pix)
        else:
            self.gorsel.setPixmap(QPixmap())
            self.gorsel.setText("Bu sayfada görüntü farkı yok." if not f.yalniz else fark_ozeti(f).capitalize() + ".")
        self.metin.setHtml(fark_html(f))
