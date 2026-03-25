from __future__ import annotations

from enum import Enum

from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QLabel,
    QListWidgetItem, QLineEdit, QComboBox,
)


class FileFilter(Enum):
    ALL = "Tous"
    ANNOTATED = "Annotes"
    NOT_ANNOTATED = "Non annotes"


class FileListWidget(QWidget):
    """Panel listing all images with search and filter."""

    file_selected = Signal(int)  # real index in the full file list

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._title = QLabel("Images")
        self._title.setStyleSheet("font-weight: bold; padding: 4px;")
        layout.addWidget(self._title)

        # Search bar
        self._search = QLineEdit()
        self._search.setPlaceholderText("Rechercher...")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._apply_filter)
        layout.addWidget(self._search)

        # Filter combo
        filter_layout = QHBoxLayout()
        filter_layout.setContentsMargins(0, 0, 0, 0)
        self._filter_combo = QComboBox()
        self._filter_combo.addItems([f.value for f in FileFilter])
        self._filter_combo.currentTextChanged.connect(lambda _: self._apply_filter())
        filter_layout.addWidget(self._filter_combo)
        layout.addLayout(filter_layout)

        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_row_changed)
        layout.addWidget(self._list)

        self._all_filenames: list[str] = []
        self._annotated: set[int] = set()  # indices of annotated files
        self._annotation_counts: dict[int, int] = {}  # index -> count
        self._filtered_indices: list[int] = []  # mapping: visible row -> real index

    def set_files(self, filenames: list[str]) -> None:
        self._all_filenames = list(filenames)
        self._annotated.clear()
        self._search.clear()
        self._filter_combo.setCurrentIndex(0)
        self._apply_filter()

    def set_current(self, index: int) -> None:
        """Set current by real index."""
        self._list.blockSignals(True)
        for visible_row, real_idx in enumerate(self._filtered_indices):
            if real_idx == index:
                self._list.setCurrentRow(visible_row)
                break
        self._list.blockSignals(False)

    def mark_annotated(self, index: int, annotated: bool, count: int = 0) -> None:
        if annotated:
            self._annotated.add(index)
            self._annotation_counts[index] = count
        else:
            self._annotated.discard(index)
            self._annotation_counts.pop(index, None)
        # Update display if item is visible
        for visible_row, real_idx in enumerate(self._filtered_indices):
            if real_idx == index:
                item = self._list.item(visible_row)
                if item:
                    self._style_item(item, real_idx)
                break

    def _apply_filter(self, _text: str = "") -> None:
        search_text = self._search.text().lower().strip()
        filter_name = self._filter_combo.currentText()

        try:
            file_filter = FileFilter(filter_name)
        except ValueError:
            file_filter = FileFilter.ALL

        self._filtered_indices.clear()
        self._list.blockSignals(True)
        self._list.clear()

        for i, fname in enumerate(self._all_filenames):
            # Search filter
            if search_text and search_text not in fname.lower():
                continue

            # Annotation filter
            if file_filter == FileFilter.ANNOTATED and i not in self._annotated:
                continue
            if file_filter == FileFilter.NOT_ANNOTATED and i in self._annotated:
                continue

            self._filtered_indices.append(i)
            display = fname
            if i in self._annotation_counts and self._annotation_counts[i] > 0:
                display = f"{fname} ({self._annotation_counts[i]})"
            item = QListWidgetItem(display)
            self._style_item(item, i)
            self._list.addItem(item)

        self._list.blockSignals(False)

        visible = len(self._filtered_indices)
        total = len(self._all_filenames)
        annotated = len(self._annotated)
        self._title.setText(f"Images ({visible}/{total} | {annotated} annotes)")

    def _style_item(self, item: QListWidgetItem, real_index: int) -> None:
        if real_index in self._annotated:
            item.setForeground(QColor("#4ec9b0"))  # green-ish
        else:
            item.setForeground(QColor("#ddd"))

    def _on_row_changed(self, row: int) -> None:
        if 0 <= row < len(self._filtered_indices):
            real_index = self._filtered_indices[row]
            self.file_selected.emit(real_index)

    def _update_title(self, count: int) -> None:
        self._title.setText(f"Images ({count})")
