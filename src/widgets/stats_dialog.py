from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QProgressBar, QHBoxLayout,
)

from src.models.annotation import ImageAnnotations, AnnotationType
from src.models.label import LabelManager


class StatsDialog(QDialog):
    """Dialog showing annotation statistics."""

    def __init__(self, annotations_cache: dict[str, ImageAnnotations],
                 label_manager: LabelManager, total_images: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Statistiques d'annotation")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)

        layout = QVBoxLayout(self)

        # --- Progress ---
        annotated_count = sum(
            1 for ann in annotations_cache.values() if ann.annotations
        )
        total_annotations = sum(
            len(ann.annotations) for ann in annotations_cache.values()
        )

        progress_group = QVBoxLayout()
        progress_label = QLabel(
            f"Progression: {annotated_count}/{total_images} images annotees "
            f"({total_annotations} annotations au total)"
        )
        progress_label.setStyleSheet("font-size: 14px; padding: 8px;")
        progress_group.addWidget(progress_label)

        progress_bar = QProgressBar()
        progress_bar.setMaximum(total_images if total_images > 0 else 1)
        progress_bar.setValue(annotated_count)
        progress_bar.setFormat(f"{annotated_count}/{total_images} ({_pct(annotated_count, total_images)}%)")
        progress_group.addWidget(progress_bar)

        layout.addLayout(progress_group)

        # --- Per-class stats ---
        class_counts: dict[int, dict] = {}
        for ann_data in annotations_cache.values():
            for ann in ann_data.annotations:
                if ann.label_id not in class_counts:
                    class_counts[ann.label_id] = {"bbox": 0, "polygon": 0, "total": 0}
                class_counts[ann.label_id]["total"] += 1
                if ann.ann_type == AnnotationType.BBOX:
                    class_counts[ann.label_id]["bbox"] += 1
                else:
                    class_counts[ann.label_id]["polygon"] += 1

        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["Classe", "Couleur", "BBox", "Polygone", "Total"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        rows = sorted(class_counts.keys())
        table.setRowCount(len(rows))

        for row_idx, class_id in enumerate(rows):
            label = label_manager.get(class_id)
            name = label.name if label else f"class_{class_id}"
            color = label.color if label else "#888888"
            counts = class_counts[class_id]

            name_item = QTableWidgetItem(name)
            table.setItem(row_idx, 0, name_item)

            color_item = QTableWidgetItem("")
            color_item.setBackground(QColor(color))
            table.setItem(row_idx, 1, color_item)

            table.setItem(row_idx, 2, QTableWidgetItem(str(counts["bbox"])))
            table.setItem(row_idx, 3, QTableWidgetItem(str(counts["polygon"])))
            table.setItem(row_idx, 4, QTableWidgetItem(str(counts["total"])))

        layout.addWidget(table)

        # Close button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("Fermer")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)


def _pct(a: int, b: int) -> str:
    if b == 0:
        return "0"
    return f"{a * 100 // b}"
