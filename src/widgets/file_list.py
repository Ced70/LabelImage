from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget, QLabel, QListWidgetItem,
)


class FileListWidget(QWidget):
    """Panel listing all images in the current directory."""

    file_selected = Signal(int)  # index

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._title = QLabel("Images")
        self._title.setStyleSheet("font-weight: bold; padding: 4px;")
        layout.addWidget(self._title)

        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_row_changed)
        layout.addWidget(self._list)

    def set_files(self, filenames: list[str]) -> None:
        self._list.blockSignals(True)
        self._list.clear()
        for name in filenames:
            self._list.addItem(name)
        self._list.blockSignals(False)
        self._update_title(len(filenames))

    def set_current(self, index: int) -> None:
        self._list.blockSignals(True)
        self._list.setCurrentRow(index)
        self._list.blockSignals(False)

    def mark_annotated(self, index: int, annotated: bool) -> None:
        item = self._list.item(index)
        if item:
            text = item.text()
            base = text.rstrip(" *")
            item.setText(f"{base} *" if annotated else base)

    def _on_row_changed(self, row: int) -> None:
        if row >= 0:
            self.file_selected.emit(row)

    def _update_title(self, count: int) -> None:
        self._title.setText(f"Images ({count})")
