from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QColor, QPixmap, QIcon
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QInputDialog, QColorDialog, QMessageBox,
)

from src.models.label import Label, LabelManager


class LabelListWidget(QWidget):
    """Panel for managing annotation classes/labels."""

    label_selected = Signal(int)  # class_id
    labels_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._title = QLabel("Classes")
        self._title.setStyleSheet("font-weight: bold; padding: 4px;")
        layout.addWidget(self._title)

        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_row_changed)
        layout.addWidget(self._list)

        btn_layout = QHBoxLayout()
        self._add_btn = QPushButton("+")
        self._add_btn.setFixedWidth(40)
        self._add_btn.clicked.connect(self._on_add)
        self._remove_btn = QPushButton("-")
        self._remove_btn.setFixedWidth(40)
        self._remove_btn.clicked.connect(self._on_remove)
        btn_layout.addWidget(self._add_btn)
        btn_layout.addWidget(self._remove_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self._label_manager: LabelManager | None = None

    def set_label_manager(self, manager: LabelManager) -> None:
        self._label_manager = manager
        self._refresh()

    def _refresh(self) -> None:
        self._list.blockSignals(True)
        self._list.clear()
        if self._label_manager:
            for label in self._label_manager.labels:
                item = QListWidgetItem(label.name)
                pixmap = QPixmap(16, 16)
                pixmap.fill(QColor(label.color))
                item.setIcon(QIcon(pixmap))
                self._list.addItem(item)
            if self._label_manager.labels:
                self._list.setCurrentRow(0)
        self._list.blockSignals(False)

    def current_class_id(self) -> int:
        row = self._list.currentRow()
        return row if row >= 0 else 0

    def set_current_class(self, index: int) -> None:
        if 0 <= index < self._list.count():
            self._list.setCurrentRow(index)

    def _on_row_changed(self, row: int) -> None:
        if row >= 0:
            self.label_selected.emit(row)

    def _on_add(self) -> None:
        name, ok = QInputDialog.getText(self, "Nouvelle classe", "Nom de la classe:")
        if ok and name.strip():
            if self._label_manager:
                self._label_manager.add(name.strip())
                self._refresh()
                self._list.setCurrentRow(len(self._label_manager.labels) - 1)
                self.labels_changed.emit()

    def _on_remove(self) -> None:
        row = self._list.currentRow()
        if row >= 0 and self._label_manager:
            label = self._label_manager.get(row)
            if label:
                reply = QMessageBox.question(
                    self, "Supprimer la classe",
                    f"Supprimer la classe '{label.name}' ?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    self._label_manager.remove(row)
                    self._refresh()
                    self.labels_changed.emit()
