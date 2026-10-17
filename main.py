import sys

from PySide6.QtWidgets import QApplication

from eaglepdf import APP_NAME, __version__
from eaglepdf.ui import theme
from eaglepdf.ui.oturum import komut_satiri_yollari
from eaglepdf.ui.pencere import AnaPencere


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    theme.apply(app)
    pencere = AnaPencere()
    pencere.show()
    pencere.ac_coklu(komut_satiri_yollari(sys.argv))   # "Birlikte aç" ya da birden çok dosya: her biri bir sekme
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
