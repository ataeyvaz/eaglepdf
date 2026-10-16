"""Yardım → Nasıl Kullanılır penceresi. İçerik eaglepdf/yardim.md dosyasındadır (konulara bölünmüş Markdown).

Konu ayracı: `<!-- konu: kimlik | Başlık -->`. Arama Türkçe büyük/küçük harf duyarsızdır. Çevrimdışıdır.
"""

import re
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QSplitter, QTextBrowser, QVBoxLayout

from .. import APP_NAME, metin_tr, resource_dir

YARDIM_DOSYASI = resource_dir() / "yardim.md"
KONU_RE = re.compile(r"^<!--\s*konu:\s*([\w-]+)\s*\|\s*(.+?)\s*-->\s*$", re.MULTILINE)


@dataclass
class Konu:
    kimlik: str
    baslik: str
    govde: str


def konulari_yukle(yol=YARDIM_DOSYASI) -> list[Konu]:
    metin = yol.read_text(encoding="utf-8").replace("{APP_NAME}", APP_NAME)
    eslesmeler = list(KONU_RE.finditer(metin))
    konular = []
    for n, e in enumerate(eslesmeler):
        son = eslesmeler[n + 1].start() if n + 1 < len(eslesmeler) else len(metin)
        konular.append(Konu(e.group(1), e.group(2), metin[e.end():son].strip()))
    return konular


class YardimPenceresi(QDialog):
    def __init__(self, parent=None, ilk_konu: str | None = None):
        super().__init__(parent)
        self.setWindowTitle(f"{APP_NAME} — Nasıl Kullanılır")
        self.resize(860, 560)
        self.konular = konulari_yukle()
        duzen = QVBoxLayout(self)
        duzen.setContentsMargins(0, 0, 0, 0)
        self.ara = QLineEdit()
        self.ara.setPlaceholderText("Yardımda ara…")
        self.ara.setClearButtonEnabled(True)
        self.ara.textChanged.connect(self._filtrele)
        sol = QVBoxLayout()
        sol.setContentsMargins(8, 8, 8, 8)
        sol.addWidget(self.ara)
        self.liste = QListWidget()
        sol.addWidget(self.liste)
        from PySide6.QtWidgets import QWidget
        solw = QWidget()
        solw.setLayout(sol)
        self.goz = QTextBrowser()
        self.goz.setOpenLinks(False)
        self.goz.anchorClicked.connect(self._baglanti)
        ayirac = QSplitter(Qt.Horizontal)
        ayirac.addWidget(solw)
        ayirac.addWidget(self.goz)
        ayirac.setStretchFactor(1, 1)
        ayirac.setSizes([240, 620])
        duzen.addWidget(ayirac)
        self.liste.currentItemChanged.connect(self._goster)
        self._doldur(self.konular)
        if ilk_konu:
            self.konuya_git(ilk_konu)

    def _doldur(self, konular):
        self.liste.clear()
        for k in konular:
            oge = QListWidgetItem(k.baslik)
            oge.setData(Qt.UserRole, k.kimlik)
            self.liste.addItem(oge)
        if self.liste.count():
            self.liste.setCurrentRow(0)
        else:
            self.goz.setPlainText("Eşleşen konu yok.")

    def _filtrele(self, sorgu: str):
        s = metin_tr.kucuk(sorgu.strip())
        self._doldur([k for k in self.konular if not s or s in metin_tr.kucuk(k.baslik + " " + k.govde)])

    def _goster(self, oge, _onceki=None):
        if oge is None:
            return
        k = next(k for k in self.konular if k.kimlik == oge.data(Qt.UserRole))
        self.goz.setMarkdown(f"# {k.baslik}\n\n{k.govde}")

    def konuya_git(self, kimlik: str):
        for r in range(self.liste.count()):
            if self.liste.item(r).data(Qt.UserRole) == kimlik:
                self.liste.setCurrentRow(r)
                return

    def _baglanti(self, url):
        if url.scheme() == "konu":
            self.ara.clear()
            self.konuya_git(url.path() or url.host())
