from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QDoubleSpinBox, QCheckBox, QFileDialog, QGroupBox,
)


class SplitDialog(QDialog):
    """Dialog for configuring train/val/test split export."""

    export_requested = Signal(str, float, float, float, bool)  # dir, train, val, test, shuffle

    def __init__(self, default_dir: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Export YOLO avec split")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)

        # Output directory
        dir_layout = QHBoxLayout()
        dir_layout.addWidget(QLabel("Dossier:"))
        self._dir_label = QLabel(default_dir or "(choisir)")
        self._dir_label.setStyleSheet("padding: 4px;")
        dir_layout.addWidget(self._dir_label, 1)
        browse_btn = QPushButton("Parcourir")
        browse_btn.clicked.connect(self._browse)
        dir_layout.addWidget(browse_btn)
        layout.addLayout(dir_layout)
        self._output_dir = default_dir

        # Ratios
        ratio_group = QGroupBox("Proportions")
        ratio_layout = QVBoxLayout(ratio_group)

        for name, default in [("Train", 0.7), ("Val", 0.2), ("Test", 0.1)]:
            row = QHBoxLayout()
            row.addWidget(QLabel(f"{name}:"))
            spin = QDoubleSpinBox()
            spin.setRange(0.0, 1.0)
            spin.setSingleStep(0.05)
            spin.setValue(default)
            row.addWidget(spin)
            ratio_layout.addLayout(row)
            setattr(self, f"_{name.lower()}_spin", spin)

        layout.addWidget(ratio_group)

        self._shuffle = QCheckBox("Melanger les images")
        self._shuffle.setChecked(True)
        layout.addWidget(self._shuffle)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        export_btn = QPushButton("Exporter")
        export_btn.setDefault(True)
        export_btn.clicked.connect(self._on_export)
        btn_layout.addWidget(export_btn)
        cancel_btn = QPushButton("Annuler")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _browse(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Dossier de destination")
        if path:
            self._output_dir = path
            self._dir_label.setText(path)

    def _on_export(self) -> None:
        if not self._output_dir:
            self._browse()
            if not self._output_dir:
                return
        self.export_requested.emit(
            self._output_dir,
            self._train_spin.value(),
            self._val_spin.value(),
            self._test_spin.value(),
            self._shuffle.isChecked(),
        )
        self.accept()
