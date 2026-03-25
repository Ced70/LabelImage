from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QLineEdit, QDoubleSpinBox, QCheckBox,
    QProgressBar, QComboBox, QGroupBox, QMessageBox,
)


class AutoAnnotateDialog(QDialog):
    """Dialog for configuring and running YOLO auto-annotation."""

    run_requested = Signal(str, float, bool, bool)  # model_path, confidence, use_seg, all_images

    def __init__(self, parent=None, last_model_path: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Pre-annotation YOLO")
        self.setMinimumWidth(450)

        layout = QVBoxLayout(self)

        # Model selection
        model_group = QGroupBox("Modele YOLO")
        model_layout = QVBoxLayout(model_group)

        # Preset models
        preset_layout = QHBoxLayout()
        preset_layout.addWidget(QLabel("Modele pre-entraine:"))
        self._preset_combo = QComboBox()
        self._preset_combo.addItems([
            "(personnalise)",
            "yolov8n.pt", "yolov8s.pt", "yolov8m.pt", "yolov8l.pt", "yolov8x.pt",
            "yolov8n-seg.pt", "yolov8s-seg.pt", "yolov8m-seg.pt",
            "yolo11n.pt", "yolo11s.pt", "yolo11m.pt",
            "yolo11n-seg.pt", "yolo11s-seg.pt", "yolo11m-seg.pt",
        ])
        self._preset_combo.currentTextChanged.connect(self._on_preset_changed)
        preset_layout.addWidget(self._preset_combo)
        model_layout.addLayout(preset_layout)

        # Custom model path
        path_layout = QHBoxLayout()
        self._model_path = QLineEdit(last_model_path)
        self._model_path.setPlaceholderText("Chemin vers le modele .pt")
        path_layout.addWidget(self._model_path)
        browse_btn = QPushButton("Parcourir...")
        browse_btn.clicked.connect(self._browse_model)
        path_layout.addWidget(browse_btn)
        model_layout.addLayout(path_layout)

        layout.addWidget(model_group)

        # Settings
        settings_group = QGroupBox("Parametres")
        settings_layout = QVBoxLayout(settings_group)

        conf_layout = QHBoxLayout()
        conf_layout.addWidget(QLabel("Seuil de confiance:"))
        self._confidence = QDoubleSpinBox()
        self._confidence.setRange(0.01, 1.0)
        self._confidence.setSingleStep(0.05)
        self._confidence.setValue(0.25)
        conf_layout.addWidget(self._confidence)
        settings_layout.addLayout(conf_layout)

        self._use_seg = QCheckBox("Utiliser la segmentation (polygones) si disponible")
        self._use_seg.setChecked(False)
        settings_layout.addWidget(self._use_seg)

        self._all_images = QCheckBox("Appliquer a toutes les images du dossier")
        self._all_images.setChecked(False)
        settings_layout.addWidget(self._all_images)

        layout.addWidget(settings_group)

        # Progress
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        self._status_label = QLabel("")
        layout.addWidget(self._status_label)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._run_btn = QPushButton("Lancer")
        self._run_btn.setDefault(True)
        self._run_btn.clicked.connect(self._on_run)
        btn_layout.addWidget(self._run_btn)

        cancel_btn = QPushButton("Fermer")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

    def _on_preset_changed(self, text: str) -> None:
        if text != "(personnalise)":
            self._model_path.setText(text)
            if "-seg" in text:
                self._use_seg.setChecked(True)

    def _browse_model(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Selectionner un modele YOLO",
            "", "Modeles (*.pt *.onnx);;Tous (*)",
        )
        if path:
            self._model_path.setText(path)
            self._preset_combo.setCurrentIndex(0)

    def _on_run(self) -> None:
        model_path = self._model_path.text().strip()
        if not model_path:
            QMessageBox.warning(self, "Erreur", "Veuillez selectionner un modele.")
            return

        self.run_requested.emit(
            model_path,
            self._confidence.value(),
            self._use_seg.isChecked(),
            self._all_images.isChecked(),
        )

    def set_progress(self, current: int, total: int) -> None:
        self._progress.setVisible(True)
        self._progress.setMaximum(total)
        self._progress.setValue(current)

    def set_status(self, text: str) -> None:
        self._status_label.setText(text)

    def get_model_path(self) -> str:
        return self._model_path.text().strip()
