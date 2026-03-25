from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QPushButton,
)
from PySide6.QtCore import Qt


class ImageAdjustmentsWidget(QWidget):
    """Sliders for brightness and contrast adjustment."""

    values_changed = Signal(int, int)  # brightness, contrast

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("Affichage")
        title.setStyleSheet("font-weight: bold; padding: 4px;")
        layout.addWidget(title)

        # Brightness
        b_layout = QHBoxLayout()
        b_layout.addWidget(QLabel("Luminosite"))
        self._brightness = QSlider(Qt.Orientation.Horizontal)
        self._brightness.setRange(-100, 100)
        self._brightness.setValue(0)
        self._brightness.valueChanged.connect(self._on_changed)
        b_layout.addWidget(self._brightness)
        self._b_label = QLabel("0")
        self._b_label.setFixedWidth(30)
        b_layout.addWidget(self._b_label)
        layout.addLayout(b_layout)

        # Contrast
        c_layout = QHBoxLayout()
        c_layout.addWidget(QLabel("Contraste"))
        self._contrast = QSlider(Qt.Orientation.Horizontal)
        self._contrast.setRange(-100, 100)
        self._contrast.setValue(0)
        self._contrast.valueChanged.connect(self._on_changed)
        c_layout.addWidget(self._contrast)
        self._c_label = QLabel("0")
        self._c_label.setFixedWidth(30)
        c_layout.addWidget(self._c_label)
        layout.addLayout(c_layout)

        # Reset button
        reset_btn = QPushButton("Reinitialiser")
        reset_btn.clicked.connect(self._reset)
        layout.addWidget(reset_btn)

    def _on_changed(self) -> None:
        b = self._brightness.value()
        c = self._contrast.value()
        self._b_label.setText(str(b))
        self._c_label.setText(str(c))
        self.values_changed.emit(b, c)

    def _reset(self) -> None:
        self._brightness.setValue(0)
        self._contrast.setValue(0)
