"""Görsel tema: renkler (vurgu rengi KIRMIZI — tek yerden değişir), Qt stil sayfası, uygulama ikonu."""

import ctypes
import sys

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPalette, QPixmap
from PySide6.QtWidgets import QProxyStyle, QStyle, QMenu

ACCENT = "#c62828"
ACCENT_DARK = "#a31f1f"
SELECTION = "#f4b8b8"
TEXT = "#242424"
TEXT_MUTED = "#616161"
WINDOW = "#f3f3f3"
CANVAS = "#e9e9e9"
SURFACE = "#ffffff"
BORDER = "#e0e0e0"
HOVER = "#f0f0f0"
PRESSED = "#e0e0e0"
CHECKED = "#fbe3e3"
CHECKED_HOVER = "#f5d0d0"


def stylesheet():
    return f"""
QMainWindow, #central {{ background: {WINDOW}; }}
QToolTip {{ background: {SURFACE}; color: {TEXT}; border: 1px solid {BORDER}; padding: 5px 8px; border-radius: 4px; }}

#header {{ background: {ACCENT}; }}
#header QLabel {{ color: #ffffff; }}
#header #belgeAdi {{ font-weight: 600; }}
#header #belgeDurum {{ color: rgba(255,255,255,0.8); }}

QMenuBar {{ background: {SURFACE}; border-bottom: 1px solid {BORDER}; padding: 1px 4px; }}
QMenuBar::item {{ padding: 5px 10px; border-radius: 4px; background: transparent; }}
QMenuBar::item:selected {{ background: {HOVER}; }}
QMenuBar::item:pressed {{ background: {CHECKED}; color: {ACCENT}; }}
QMenu {{ background: {SURFACE}; border: 1px solid {BORDER}; padding: 4px; }}
QMenu::item {{ padding: 5px 28px 5px 24px; border-radius: 4px; }}
QMenu::item:selected {{ background: {CHECKED}; color: {TEXT}; }}
QMenu::item:disabled {{ color: #a0a0a0; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 4px 6px; }}

QToolBar {{ background: {SURFACE}; border: none; border-bottom: 1px solid {BORDER}; padding: 3px 6px; spacing: 3px; }}
QToolButton {{ border: 1px solid transparent; border-radius: 4px; padding: 4px 8px; background: transparent; }}
QToolButton:hover {{ background: {HOVER}; }}
QToolButton:pressed {{ background: {PRESSED}; }}
QToolButton:checked {{ background: {CHECKED}; color: {ACCENT}; }}
QToolButton:disabled {{ color: #a0a0a0; }}

QLineEdit, QSpinBox, QComboBox {{
    background: {SURFACE}; border: 1px solid #d1d1d1; border-radius: 4px; padding: 3px 6px;
    selection-background-color: {SELECTION}; selection-color: {TEXT};
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{ border-color: {ACCENT}; }}

QListWidget, QTreeWidget, QTextBrowser {{ background: {SURFACE}; border: none; selection-background-color: {SELECTION}; }}
QListWidget::item:selected, QTreeWidget::item:selected {{ background: {CHECKED}; color: {TEXT}; border: 1px solid {ACCENT}; }}
QListWidget::item:hover:!selected {{ background: {HOVER}; }}
QTabWidget::pane {{ border: none; border-top: 1px solid {BORDER}; }}
QTabBar::tab {{ padding: 5px 14px; border: none; background: transparent; }}
QTabBar::tab:selected {{ color: {ACCENT}; border-bottom: 3px solid {ACCENT}; }}
QTabBar::tab:hover:!selected {{ background: {HOVER}; }}
QSplitter::handle {{ background: {BORDER}; }}
QStatusBar {{ background: {SURFACE}; border-top: 1px solid {BORDER}; }}
QScrollArea {{ border: none; background: {CANVAS}; }}

QPushButton {{ background: {SURFACE}; border: 1px solid #d1d1d1; border-radius: 4px; padding: 5px 16px; min-width: 64px; }}
QPushButton:hover {{ background: {HOVER}; }}
QPushButton:default {{ background: {ACCENT}; color: #ffffff; border-color: {ACCENT}; }}
QPushButton:default:hover {{ background: {ACCENT_DARK}; }}
"""


class _Style(QProxyStyle):
    def pixelMetric(self, metric, option=None, widget=None):
        if metric == QStyle.PM_SmallIconSize and isinstance(widget, QMenu):
            return 20
        return super().pixelMetric(metric, option, widget)


def apply(app):
    app.setStyle(_Style("Fusion"))
    palette = QPalette()
    for role, color in (
        (QPalette.Window, WINDOW), (QPalette.WindowText, TEXT), (QPalette.Base, SURFACE),
        (QPalette.AlternateBase, WINDOW), (QPalette.Text, TEXT), (QPalette.Button, SURFACE),
        (QPalette.ButtonText, TEXT), (QPalette.Highlight, SELECTION), (QPalette.HighlightedText, TEXT),
        (QPalette.ToolTipBase, SURFACE), (QPalette.ToolTipText, TEXT), (QPalette.PlaceholderText, "#8a8a8a"),
    ):
        palette.setColor(role, QColor(color))
    app.setPalette(palette)
    app.setFont(QFont("Segoe UI", 9))
    app.setStyleSheet(stylesheet())
    app.setWindowIcon(app_icon())


def app_icon():
    result = QIcon()
    for size in (16, 24, 32, 48, 64, 256):
        pix = QPixmap(size, size)
        pix.fill(Qt.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(ACCENT))
        p.drawRoundedRect(QRectF(0, 0, size, size), size * 0.2, size * 0.2)
        p.setPen(QColor("#ffffff"))
        font = QFont("Segoe UI", 1, QFont.DemiBold)
        font.setPixelSize(round(size * 0.62))
        p.setFont(font)
        p.drawText(QRectF(0, -size * 0.03, size, size), Qt.AlignCenter, "P")
        p.end()
        result.addPixmap(pix)
    return result


def color_title_bar(widget, background=ACCENT, text="#ffffff"):
    """Windows 11'de yerel başlık çubuğunu başlık şeridiyle aynı renge boyar."""
    if sys.platform != "win32":
        return

    def colorref(hex_color):
        c = QColor(hex_color)
        return c.red() | (c.green() << 8) | (c.blue() << 16)

    try:
        hwnd = int(widget.winId())
        dwm = ctypes.windll.dwmapi
        for attribute, value in ((35, colorref(background)), (36, colorref(text)), (34, colorref(background))):
            v = ctypes.c_int(value)
            dwm.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(v), ctypes.sizeof(v))
    except (AttributeError, OSError):
        pass
