"""Hakkında penceresi: ad, sürüm, künye, iletişim, kullanılan açık kaynak bileşenler ve lisans."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QVBoxLayout

from .. import APP_NAME, DEVELOPERS, ILETISIM_EPOSTA, PAKET_ADI, PAKET_URUNLERI, __version__, resource_dir

# (ad, ne için, lisans) — yeni bağımlılık eklenince buraya ve README'ye yazılır
KATKILAR = [
    ("PyMuPDF (MuPDF)", "PDF motoru: görüntüleme, sayfa işlemleri", "AGPL-3.0"),
    ("PySide6 (Qt)", "arayüz", "LGPL-3.0"),
    ("pymupdf-fonts (Noto Sans)", "PDF'e gömülen Türkçe karakterli yazı tipi", "SIL OFL 1.1"),
    ("pdf2docx", "PDF'den Word'e dönüştürme", "MIT"),
    ("python-docx, openpyxl, python-pptx", "Word, Excel, PowerPoint dosyaları", "MIT"),
    ("mammoth", "Word belgesini HTML'e çevirme", "BSD-2-Clause"),
    ("NumPy, Pillow, OpenCV (headless)", "görüntü işleme, resim biçimleri", "BSD / HPND / Apache-2.0"),
    ("comtypes", "tarayıcıdan sayfa alma (WIA)", "MIT"),
]
GIZLILIK = "Tüm işlemler bu bilgisayarda yapılır; belgeleriniz hiçbir sunucuya gönderilmez."
LISANS = f"{APP_NAME} açık kaynaktır (GNU AGPL-3.0). Ticari amaç taşımaz."


def paket_metni() -> str:
    return f"{PAKET_ADI} paketi: " + "  ·  ".join(f"{ad} ({ne})" for ad, ne in PAKET_URUNLERI)


def hakkinda_metni() -> str:
    satirlar = [PAKET_ADI, APP_NAME, f"Sürüm {__version__}  ·  Türkçe PDF aracı", DEVELOPERS, paket_metni(),
                f"İletişim: {ILETISIM_EPOSTA}", GIZLILIK, LISANS, "Kullanılan açık kaynak bileşenler:"]
    satirlar += [f"•  {ad} — {ne} ({lisans})" for ad, ne, lisans in KATKILAR]
    return "\n".join(satirlar)


class HakkindaPenceresi(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{APP_NAME} Hakkında")
        self.setFixedWidth(460)
        duzen = QVBoxLayout(self)
        duzen.setContentsMargins(20, 18, 20, 14)
        duzen.setSpacing(10)
        ust = QHBoxLayout()
        ust.setSpacing(14)
        logo = resource_dir() / "eagle-office-logo.png"
        if logo.exists():
            pix = QPixmap(str(logo))
            etiket = QLabel()
            etiket.setPixmap(pix.scaledToWidth(120, Qt.SmoothTransformation))
            ust.addWidget(etiket, 0, Qt.AlignTop)
        basliklar = QVBoxLayout()
        ad = QLabel(APP_NAME)
        yazi = QFont(ad.font())
        yazi.setPointSize(18)
        yazi.setBold(True)
        ad.setFont(yazi)
        basliklar.addWidget(ad)
        basliklar.addWidget(QLabel(f"Sürüm {__version__}  ·  Türkçe PDF aracı"))
        basliklar.addWidget(QLabel(DEVELOPERS))
        ust.addLayout(basliklar, 1)
        duzen.addLayout(ust)
        for metin in (paket_metni(), f"İletişim: {ILETISIM_EPOSTA}", GIZLILIK, LISANS):
            e = QLabel(metin)
            e.setWordWrap(True)
            duzen.addWidget(e)
        duzen.addWidget(QLabel("Kullanılan açık kaynak bileşenler:"))
        for ad_, ne, lisans in KATKILAR:
            e = QLabel(f"•  {ad_} — {ne} ({lisans})")
            e.setWordWrap(True)
            duzen.addWidget(e)
        kutu = QDialogButtonBox(QDialogButtonBox.Close)
        kutu.button(QDialogButtonBox.Close).setText("Kapat")
        kutu.rejected.connect(self.reject)
        kutu.accepted.connect(self.accept)
        duzen.addWidget(kutu)
