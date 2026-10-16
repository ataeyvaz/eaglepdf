import sys

from PySide6.QtWidgets import QApplication

from eaglepdf import APP_NAME, __version__
from eaglepdf.ui import theme
from eaglepdf.ui.pencere import AnaPencere


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    theme.apply(app)
    pencere = AnaPencere()
    pencere.show()
    if len(sys.argv) > 1:
        pencere.ac(sys.argv[1])
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
