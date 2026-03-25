from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QDoubleSpinBox, QSpinBox, QRadioButton, QButtonGroup,
    QGroupBox, QProgressBar, QCheckBox,
)


class PredictDialog(QDialog):
    """Dialog for prediction based on previous annotations."""

    propagate_requested = Signal()
    template_match_requested = Signal(float, int, bool)  # confidence, max_sources, multi_scale

    def __init__(self, has_previous: bool = True, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Predire les annotations")
        self.setMinimumWidth(450)

        layout = QVBoxLayout(self)

        # Strategy selection
        strategy_group = QGroupBox("Strategie")
        strategy_layout = QVBoxLayout(strategy_group)

        self._btn_group = QButtonGroup(self)

        self._propagate_radio = QRadioButton(
            "Propager depuis l'image precedente\n"
            "  Copie les annotations de l'image precedente (ideal pour sequences video)"
        )
        self._propagate_radio.setEnabled(has_previous)
        self._propagate_radio.setChecked(has_previous)
        self._btn_group.addButton(self._propagate_radio, 0)
        strategy_layout.addWidget(self._propagate_radio)

        self._template_radio = QRadioButton(
            "Template matching (OpenCV)\n"
            "  Recherche des regions similaires aux annotations existantes"
        )
        self._template_radio.setChecked(not has_previous)
        self._btn_group.addButton(self._template_radio, 1)
        strategy_layout.addWidget(self._template_radio)

        layout.addWidget(strategy_group)

        # Template matching settings
        self._tm_group = QGroupBox("Parametres template matching")
        tm_layout = QVBoxLayout(self._tm_group)

        conf_layout = QHBoxLayout()
        conf_layout.addWidget(QLabel("Seuil de confiance:"))
        self._confidence = QDoubleSpinBox()
        self._confidence.setRange(0.1, 1.0)
        self._confidence.setSingleStep(0.05)
        self._confidence.setValue(0.60)
        conf_layout.addWidget(self._confidence)
        tm_layout.addLayout(conf_layout)

        src_layout = QHBoxLayout()
        src_layout.addWidget(QLabel("Images sources (max):"))
        self._max_sources = QSpinBox()
        self._max_sources.setRange(1, 20)
        self._max_sources.setValue(5)
        src_layout.addWidget(self._max_sources)
        tm_layout.addLayout(src_layout)

        self._multi_scale = QCheckBox("Multi-scale (plus lent, meilleure detection)")
        self._multi_scale.setChecked(True)
        tm_layout.addWidget(self._multi_scale)

        layout.addWidget(self._tm_group)

        # Toggle settings visibility
        self._btn_group.idToggled.connect(self._on_strategy_changed)
        self._on_strategy_changed(self._btn_group.checkedId(), True)

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

        close_btn = QPushButton("Fermer")
        close_btn.clicked.connect(self.reject)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def _on_strategy_changed(self, id_: int, checked: bool) -> None:
        self._tm_group.setEnabled(self._template_radio.isChecked())

    def _on_run(self) -> None:
        if self._propagate_radio.isChecked():
            self.propagate_requested.emit()
        else:
            self.template_match_requested.emit(
                self._confidence.value(),
                self._max_sources.value(),
                self._multi_scale.isChecked(),
            )

    def set_status(self, text: str) -> None:
        self._status_label.setText(text)

    def set_progress(self, current: int, total: int) -> None:
        self._progress.setVisible(True)
        self._progress.setMaximum(total)
        self._progress.setValue(current)
