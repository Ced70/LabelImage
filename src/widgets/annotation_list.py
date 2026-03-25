from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor, QPixmap, QIcon
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget, QListWidgetItem, QLabel,
)

from src.models.annotation import Annotation, ImageAnnotations
from src.models.label import LabelManager


class AnnotationListWidget(QWidget):
    """Panel listing all annotations on the current image."""

    annotation_selected = Signal(str)  # uid

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._title = QLabel("Annotations")
        self._title.setStyleSheet("font-weight: bold; padding: 4px;")
        layout.addWidget(self._title)

        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_row_changed)
        layout.addWidget(self._list)

        self._annotations: ImageAnnotations | None = None
        self._label_manager: LabelManager | None = None

    def set_data(self, annotations: ImageAnnotations | None, label_manager: LabelManager) -> None:
        self._annotations = annotations
        self._label_manager = label_manager
        self._refresh()

    def _refresh(self) -> None:
        self._list.blockSignals(True)
        self._list.clear()
        if self._annotations and self._label_manager:
            for ann in self._annotations.annotations:
                label = self._label_manager.get(ann.label_id)
                name = label.name if label else f"class_{ann.label_id}"
                color = label.color if label else "#888888"
                text = f"{name} {ann.display_info()}"
                item = QListWidgetItem(text)
                pixmap = QPixmap(16, 16)
                pixmap.fill(QColor(color))
                item.setIcon(QIcon(pixmap))
                item.setData(256, ann.uid)  # Qt.UserRole = 256
                self._list.addItem(item)
            self._title.setText(f"Annotations ({len(self._annotations.annotations)})")
        else:
            self._title.setText("Annotations (0)")
        self._list.blockSignals(False)

    def select_uid(self, uid: str) -> None:
        self._list.blockSignals(True)
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item and item.data(256) == uid:
                self._list.setCurrentRow(i)
                break
        self._list.blockSignals(False)

    def _on_row_changed(self, row: int) -> None:
        item = self._list.item(row)
        if item:
            uid = item.data(256)
            if uid:
                self.annotation_selected.emit(uid)
