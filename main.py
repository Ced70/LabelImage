import sys

from PySide6.QtWidgets import QApplication

from src.app import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("LabelImage")
    app.setOrganizationName("LabelImage")

    # Dark theme style
    app.setStyleSheet("""
        QMainWindow { background-color: #2b2b2b; }
        QDockWidget { color: #ddd; }
        QDockWidget::title {
            background-color: #3c3c3c;
            padding: 6px;
        }
        QListWidget {
            background-color: #1e1e1e;
            color: #ddd;
            border: none;
            font-size: 13px;
        }
        QListWidget::item:selected {
            background-color: #264f78;
        }
        QListWidget::item:hover {
            background-color: #333333;
        }
        QLabel {
            color: #ddd;
        }
        QPushButton {
            background-color: #3c3c3c;
            color: #ddd;
            border: 1px solid #555;
            padding: 4px 12px;
            border-radius: 3px;
        }
        QPushButton:hover {
            background-color: #4a4a4a;
        }
        QToolBar {
            background-color: #2b2b2b;
            border: none;
            spacing: 4px;
            padding: 2px;
        }
        QToolBar QToolButton {
            color: #ddd;
            padding: 4px 8px;
        }
        QMenuBar {
            background-color: #2b2b2b;
            color: #ddd;
        }
        QMenuBar::item:selected {
            background-color: #3c3c3c;
        }
        QMenu {
            background-color: #2b2b2b;
            color: #ddd;
        }
        QMenu::item:selected {
            background-color: #264f78;
        }
        QStatusBar {
            background-color: #007acc;
            color: white;
        }
        QScrollBar:vertical {
            background-color: #1e1e1e;
            width: 12px;
        }
        QScrollBar::handle:vertical {
            background-color: #555;
            border-radius: 4px;
            min-height: 20px;
        }
        QScrollBar:horizontal {
            background-color: #1e1e1e;
            height: 12px;
        }
        QScrollBar::handle:horizontal {
            background-color: #555;
            border-radius: 4px;
            min-width: 20px;
        }
    """)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
