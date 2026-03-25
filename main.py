import sys

from PySide6.QtWidgets import QApplication

from src.app import MainWindow
from src.utils.themes import DARK_THEME


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("LabelImage")
    app.setOrganizationName("LabelImage")
    app.setStyleSheet(DARK_THEME)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
