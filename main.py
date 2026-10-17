import os
import sys

from PySide6.QtWidgets import QApplication

from eaglepdf import APP_NAME, __version__
from eaglepdf.ui import theme
from eaglepdf.ui.oturum import komut_satiri_yollari
from eaglepdf.ui.pencere import AnaPencere, ayarlari_ac
from eaglepdf.ui.tek_ornek import baslat_veya_devret


def _dogru_mu(deger) -> bool:
    return str(deger).lower() in ("true", "1")


def main():
    from eaglepdf.oz_sinama import komut_satirindan
    kod = komut_satirindan(sys.argv)   # --oz-sinama: kritik yolları sınar, rapor yazar, çıkar (paketleme doğrulaması)
    if kod is not None:
        sys.exit(kod)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    theme.apply(app)
    ayar = ayarlari_ac()
    # Göreli yollar bu sürecin çalışma klasörüne göredir; çalışan örneğe gönderilecekse mutlak olmalı
    yollar = [os.path.abspath(y) for y in komut_satiri_yollari(sys.argv)]
    sunucu = None
    if _dogru_mu(ayar.value("tek_ornek", True)):
        devredildi, sunucu = baslat_veya_devret(yollar)   # çalışan örnek varsa dosyalar ona gider
        if devredildi:
            sys.exit(0)
    pencere = AnaPencere()
    pencere.tek_ornek_destegi = True
    if sunucu is not None:
        pencere.tek_ornek = sunucu
        sunucu.istekGeldi.connect(pencere.tek_ornek_istegi)
    pencere.show()
    if _dogru_mu(ayar.value("oturumu_geri_yukle", False)):
        pencere.oturumu_geri_yukle()
    pencere.ac_coklu(yollar)   # "Birlikte aç" ya da birden çok dosya: her biri bir sekme
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
