"""Belge sekme çubuğu: QTabBar + orta tık ile kapatma sinyali."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QTabBar


class SekmeCubugu(QTabBar):
    ortaTiklandi = Signal(int)   # orta tuşla tıklanan sekmenin sırası

    def mouseReleaseEvent(self, olay):
        if olay.button() == Qt.MiddleButton:
            sira = self.tabAt(olay.position().toPoint())
            if sira >= 0:
                self.ortaTiklandi.emit(sira)
                olay.accept()
                return
        super().mouseReleaseEvent(olay)
