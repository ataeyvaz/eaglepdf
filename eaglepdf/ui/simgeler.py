"""Kodla çizilen çizgi simgeler (24×24 SVG, renk temadan). Dış görsel dosyası kullanılmaz."""

from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from . import theme

# Her simge: SVG iç içeriği (stroke="currentColor" yerine {c} ile boyanır)
_YOLLAR = {
    "ac": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    "kaydet": '<path d="M5 4h11l3 3v13H5z"/><path d="M8 4v5h7V4M8 20v-6h8v6"/>',
    "yazdir": '<path d="M7 9V4h10v5M7 17H5a1 1 0 0 1-1-1v-6a1 1 0 0 1 1-1h14a1 1 0 0 1 1 1v6a1 1 0 0 1-1 1h-2"/>'
              '<path d="M7 14h10v6H7z"/>',
    "yakinlastir": '<circle cx="11" cy="11" r="6"/><path d="M16 16l5 5M11 8v6M8 11h6"/>',
    "uzaklastir": '<circle cx="11" cy="11" r="6"/><path d="M16 16l5 5M8 11h6"/>',
    "genislik": '<path d="M3 12h18M3 12l3-3M3 12l3 3M21 12l-3-3M21 12l-3 3M3 5v14M21 5v14"/>',
    "sayfa": '<rect x="6" y="3" width="12" height="18" rx="1.5"/><path d="M9 8h6M9 12h6"/>',
    "sola": '<path d="M5 9h9a5 5 0 0 1 0 10H9"/><path d="M8 5L4 9l4 4"/>',
    "saga": '<path d="M19 9h-9a5 5 0 0 0 0 10h5"/><path d="M16 5l4 4-4 4"/>',
    "sil": '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
    "ara": '<circle cx="11" cy="11" r="6"/><path d="M16 16l5 5"/>',
    "el": '<path d="M8 12V6a1.5 1.5 0 0 1 3 0v5M11 11V4.5a1.5 1.5 0 0 1 3 0V11M14 11V6a1.5 1.5 0 0 1 3 0v8'
          'a6 6 0 0 1-6 6h-1a5 5 0 0 1-4-2l-3-4a1.5 1.5 0 0 1 2.2-2L8 15"/>',
    "imlec": '<path d="M9 4h6M9 20h6M12 4v16"/>',
    "gece": '<path d="M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5z"/>',
    "tek": '<rect x="7" y="4" width="10" height="16" rx="1.5"/>',
    "cift": '<rect x="3" y="5" width="8" height="14" rx="1.5"/><rect x="13" y="5" width="8" height="14" rx="1.5"/>',
    "sureklu": '<rect x="7" y="2" width="10" height="8" rx="1.5"/><rect x="7" y="13" width="10" height="9" rx="1.5"/>',
    "kopyala": '<rect x="8" y="8" width="12" height="12" rx="1.5"/><path d="M16 8V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3"/>',
    "boslu": '<path d="M12 5v14M5 12h14"/>',
    "birlestir": '<path d="M6 4v6a4 4 0 0 0 4 4h4a4 4 0 0 1 4 4v2M18 4v6M12 14v6"/>',
    "bol": '<path d="M12 3v18M5 8l-3 4 3 4M19 8l3 4-3 4"/>',
}


def _svg(ad: str, renk: str) -> bytes:
    govde = _YOLLAR[ad]
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{renk}" '
            f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{govde}</svg>').encode()


def _pixmap(ad: str, renk: str, boyut: int, dpr: float = 2.0) -> QPixmap:
    px = QPixmap(round(boyut * dpr), round(boyut * dpr))
    px.fill(Qt.transparent)
    p = QPainter(px)
    QSvgRenderer(QByteArray(_svg(ad, renk))).render(p)
    p.end()
    px.setDevicePixelRatio(dpr)
    return px


_onbellek: dict[str, QIcon] = {}


def simge(ad: str) -> QIcon:
    """Normal / etkin değil / seçili (vurgu rengi) durumlu simge."""
    if ad not in _onbellek:
        ic = QIcon()
        ic.addPixmap(_pixmap(ad, theme.TEXT_MUTED, 20), QIcon.Normal, QIcon.Off)
        ic.addPixmap(_pixmap(ad, theme.ACCENT, 20), QIcon.Normal, QIcon.On)
        ic.addPixmap(_pixmap(ad, "#b8b8b8", 20), QIcon.Disabled, QIcon.Off)
        _onbellek[ad] = ic
    return _onbellek[ad]


def simge_adlari() -> list[str]:
    return list(_YOLLAR)
