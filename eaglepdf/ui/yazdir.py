"""Yazdırma: sayfaları yazıcı çözünürlüğünde çizip kâğıda sığdırır."""

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtPrintSupport import QPrinter

from ..core.belge import Belge

EN_COK_DPI = 300  # çok yüksek çözünürlüklü yazıcılarda bellek için üst sınır


def sayfalari_yazdir(belge: Belge, printer: QPrinter, sayfalar: list[int], ilerleme=None) -> int:
    """`sayfalar` (0 tabanlı) sırayla yazıcıya gönderilir; yazdırılan sayfa sayısını döndürür.
    `ilerleme(n)` her sayfadan sonra çağrılır; True dönerse işlem iptal edilir."""
    boya = QPainter()
    if not boya.begin(printer):
        raise OSError("Yazıcı başlatılamadı.")
    yazilan = 0
    try:
        dpi = min(printer.resolution() or 150, EN_COK_DPI)
        for n, i in enumerate(sayfalar):
            if n:
                printer.newPage()
            px = belge.render(i, dpi / 72)
            img = QImage(px.samples, px.width, px.height, px.stride, QImage.Format_RGB888)
            alan: QRect = boya.viewport()
            hedef = img.size().scaled(alan.size(), Qt.KeepAspectRatio)
            hedef_rect = QRect(alan.x() + (alan.width() - hedef.width()) // 2,
                               alan.y() + (alan.height() - hedef.height()) // 2, hedef.width(), hedef.height())
            boya.drawImage(hedef_rect, img)
            yazilan += 1
            if ilerleme and ilerleme(yazilan):
                break
    finally:
        boya.end()
    return yazilan
