from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFormLayout, QScrollArea, QFrame,
)

from src.models.annotation import Annotation


class PropertiesPanel(QWidget):
    """Panel for editing annotation attributes/tags."""

    annotation_updated = Signal(str)  # uid

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._title = QLabel("Proprietes")
        self._title.setStyleSheet("font-weight: bold; padding: 4px;")
        layout.addWidget(self._title)

        self._no_selection = QLabel("Aucune annotation selectionnee")
        self._no_selection.setStyleSheet("color: #888; padding: 8px;")
        layout.addWidget(self._no_selection)

        # Scrollable form
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._form_widget = QWidget()
        self._form_layout = QFormLayout(self._form_widget)
        self._form_layout.setContentsMargins(4, 4, 4, 4)
        scroll.setWidget(self._form_widget)
        layout.addWidget(scroll)

        # Add attribute button
        add_layout = QHBoxLayout()
        self._attr_name = QLineEdit()
        self._attr_name.setPlaceholderText("Nom attribut")
        add_layout.addWidget(self._attr_name)
        self._attr_value = QLineEdit()
        self._attr_value.setPlaceholderText("Valeur")
        add_layout.addWidget(self._attr_value)
        add_btn = QPushButton("+")
        add_btn.setFixedWidth(30)
        add_btn.clicked.connect(self._add_attribute)
        add_layout.addWidget(add_btn)
        layout.addLayout(add_layout)

        self._current_annotation: Annotation | None = None
        self._attr_edits: dict[str, QLineEdit] = {}

    def set_annotation(self, annotation: Annotation | None) -> None:
        self._current_annotation = annotation
        self._refresh()

    def _refresh(self) -> None:
        # Clear form
        while self._form_layout.count():
            item = self._form_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._attr_edits.clear()

        if not self._current_annotation:
            self._no_selection.setVisible(True)
            self._title.setText("Proprietes")
            return

        self._no_selection.setVisible(False)
        ann = self._current_annotation

        # Show basic info
        self._title.setText(f"Proprietes [{ann.uid}]")

        type_label = QLabel(ann.ann_type.value)
        self._form_layout.addRow("Type:", type_label)

        class_label = QLabel(str(ann.label_id))
        self._form_layout.addRow("Classe:", class_label)

        if ann.bbox:
            pos_label = QLabel(f"{ann.bbox.x:.0f}, {ann.bbox.y:.0f}")
            self._form_layout.addRow("Position:", pos_label)
            size_label = QLabel(f"{ann.bbox.width:.0f} x {ann.bbox.height:.0f}")
            self._form_layout.addRow("Taille:", size_label)
        elif ann.polygon:
            pts_label = QLabel(f"{len(ann.polygon.points)} points")
            self._form_layout.addRow("Points:", pts_label)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        self._form_layout.addRow(sep)

        # Custom attributes
        attrs = getattr(ann, "attributes", {})
        if not hasattr(ann, "attributes"):
            ann.attributes = {}
            attrs = ann.attributes

        for key, value in attrs.items():
            edit = QLineEdit(str(value))
            edit.editingFinished.connect(lambda k=key, e=edit: self._on_attr_changed(k, e))
            self._attr_edits[key] = edit

            row_layout = QHBoxLayout()
            row_layout.addWidget(edit)
            del_btn = QPushButton("x")
            del_btn.setFixedWidth(24)
            del_btn.clicked.connect(lambda checked, k=key: self._remove_attribute(k))
            row_layout.addWidget(del_btn)

            container = QWidget()
            container.setLayout(row_layout)
            self._form_layout.addRow(f"{key}:", container)

    def _add_attribute(self) -> None:
        if not self._current_annotation:
            return
        name = self._attr_name.text().strip()
        value = self._attr_value.text().strip()
        if not name:
            return

        if not hasattr(self._current_annotation, "attributes"):
            self._current_annotation.attributes = {}
        self._current_annotation.attributes[name] = value
        self._attr_name.clear()
        self._attr_value.clear()
        self._refresh()
        self.annotation_updated.emit(self._current_annotation.uid)

    def _remove_attribute(self, key: str) -> None:
        if self._current_annotation and hasattr(self._current_annotation, "attributes"):
            self._current_annotation.attributes.pop(key, None)
            self._refresh()
            self.annotation_updated.emit(self._current_annotation.uid)

    def _on_attr_changed(self, key: str, edit: QLineEdit) -> None:
        if self._current_annotation and hasattr(self._current_annotation, "attributes"):
            self._current_annotation.attributes[key] = edit.text()
            self.annotation_updated.emit(self._current_annotation.uid)
