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
    "sola": '<path d="M4 12a8 8 0 1 0 3-6.2"/><path d="M4 4v5h5"/>',
    "saga": '<path d="M20 12a8 8 0 1 1-3-6.2"/><path d="M20 4v5h-5"/>',
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
    "sec_ok": '<path d="M6 3l12 8-5 1.5L11 18z"/>',
    "vurgu": '<path d="M14 4l6 6-9 9H6v-5z"/><path d="M4 21h8"/>',
    "alti": '<path d="M7 4v8a5 5 0 0 0 10 0V4M5 21h14"/>',
    "ustu": '<path d="M6 5h12M12 5v14M4 12h16"/>',
    "dalga": '<path d="M7 3v8a5 5 0 0 0 10 0V3M3 20c1.5-2 3-2 4.5 0s3 2 4.5 0 3-2 4.5 0 3 2 4.5 0"/>',
    "kalem": '<path d="M4 20l1-4L16 5a2.1 2.1 0 0 1 3 3L8 19z"/><path d="M14 7l3 3"/>',
    "not": '<path d="M5 4h14v12l-4 4H5z"/><path d="M15 20v-4h4M8 9h8M8 13h4"/>',
    "metin": '<path d="M5 6V4h14v2M12 4v16M9 20h6"/>',
    "cizgi": '<path d="M5 19L19 5"/>',
    "ok": '<path d="M5 19L19 5M10 5h9v9"/>',
    "dikdortgen": '<rect x="4" y="6" width="16" height="12" rx="1"/>',
    "elips": '<ellipse cx="12" cy="12" rx="8" ry="6"/>',
    "baglanti": '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
    "imza": '<path d="M3 17c3-6 5-9 6-9s0 6 1 6 2-3 4-3 1 3 3 3M3 21h18"/>',
    "geri": '<path d="M9 14L4 9l5-5"/><path d="M4 9h10a6 6 0 0 1 0 12h-3"/>',
    "yinele": '<path d="M15 14l5-5-5-5"/><path d="M20 9H10a6 6 0 0 0 0 12h3"/>',
    "renk": '<circle cx="12" cy="12" r="8"/><circle cx="8.5" cy="10" r="1"/><circle cx="12" cy="7.5" r="1"/><circle cx="15.5" cy="10" r="1"/>',
    "kalinlik": '<path d="M4 6h16M4 12h16M4 19h16"/>',
    "duzenle_metin": '<path d="M4 6h10M9 6v10M14 18l1-3 5-5 2 2-5 5z"/>',
    "resim": '<rect x="3" y="5" width="18" height="14" rx="1.5"/><circle cx="9" cy="10" r="1.5"/><path d="M4 18l5-5 4 4 3-3 4 4"/>',
    "muhur": '<path d="M8 4h8v6l2 3H6l2-3z"/><path d="M5 17h14v3H5z"/>',
    "redaction": '<path d="M4 12h16" stroke-width="7"/>',
    "duzlestir": '<path d="M12 4l9 5-9 5-9-5z"/><path d="M3 14l9 5 9-5"/>',
    "kirp": '<path d="M7 3v14h14M3 7h14v14"/>',
    "boyut": '<path d="M4 9V4h5M20 15v5h-5M4 4l6 6M20 20l-6-6"/>',
    "filigran": '<path d="M5 19L12 5l7 14M8 14h8"/>',
    "arkaplan": '<rect x="4" y="4" width="16" height="16" rx="1"/><path d="M4 14l5-4 4 3 3-2 4 3"/>',
    "ustalt": '<rect x="5" y="3" width="14" height="18" rx="1"/><path d="M5 7h14M5 17h14"/>',
    "numara": '<path d="M7 5l-2 5h5M9 5l-2 14M15 5l-2 14M19 5l-2 14M5 15h14"/>',
    "donustur": '<path d="M4 8h13l-3-3M20 16H7l3 3"/>',
    "sikistir": '<path d="M4 4l6 6M10 5v5H5M20 4l-6 6M14 5v5h5M4 20l6-6M10 19v-5H5M20 20l-6-6M14 19v-5h5"/>',
    "karsilastir": '<rect x="3" y="5" width="8" height="14" rx="1"/><rect x="13" y="5" width="8" height="14" rx="1"/><path d="M6 10h2M16 10h2M16 14h2"/>',
    "tarayici": '<path d="M3 14h18v5H3zM6 14V6h12v8M7 17h.01"/>',
    "form": '<rect x="4" y="5" width="16" height="14" rx="1.5"/><path d="M8 10h8M8 14h5"/>',
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
