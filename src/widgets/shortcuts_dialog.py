from __future__ import annotations

from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QKeySequenceEdit, QMessageBox,
)

# Default shortcuts
DEFAULT_SHORTCUTS = {
    "open_directory": "Ctrl+O",
    "save": "Ctrl+S",
    "save_all": "Ctrl+Shift+S",
    "quit": "Ctrl+Q",
    "undo": "Ctrl+Z",
    "redo": "Ctrl+Y",
    "copy": "Ctrl+C",
    "paste": "Ctrl+V",
    "delete": "Delete",
    "clear_all": "Ctrl+Delete",
    "select_all": "Ctrl+A",
    "change_class": "E",
    "next_image": "D",
    "prev_image": "A",
    "fit_image": "Ctrl+0",
    "zoom_selection": "F",
    "duplicate_last": "W",
    "mode_bbox": "R",
    "mode_polygon": "P",
    "grid_toggle": "G",
    "lock_toggle": "L",
    "rotate_cw": "Ctrl+R",
    "rotate_ccw": "Ctrl+Shift+R",
    "auto_annotate": "Ctrl+Shift+A",
    "predict": "Ctrl+Shift+P",
}

SHORTCUT_LABELS = {
    "open_directory": "Ouvrir dossier",
    "save": "Sauvegarder",
    "save_all": "Tout sauvegarder",
    "quit": "Quitter",
    "undo": "Annuler",
    "redo": "Retablir",
    "copy": "Copier",
    "paste": "Coller",
    "delete": "Supprimer selection",
    "clear_all": "Supprimer tout",
    "select_all": "Tout selectionner",
    "change_class": "Changer classe",
    "next_image": "Image suivante",
    "prev_image": "Image precedente",
    "fit_image": "Ajuster fenetre",
    "zoom_selection": "Zoom selection",
    "duplicate_last": "Dupliquer derniere",
    "mode_bbox": "Mode rectangle",
    "mode_polygon": "Mode polygone",
    "grid_toggle": "Grille",
    "lock_toggle": "Verrouiller",
    "rotate_cw": "Rotation CW",
    "rotate_ccw": "Rotation CCW",
    "auto_annotate": "Pre-annotation YOLO",
    "predict": "Predire annotations",
}


def load_shortcuts(settings: QSettings) -> dict[str, str]:
    """Load custom shortcuts from settings, falling back to defaults."""
    shortcuts = dict(DEFAULT_SHORTCUTS)
    for key in DEFAULT_SHORTCUTS:
        val = settings.value(f"shortcuts/{key}")
        if val:
            shortcuts[key] = val
    return shortcuts


def save_shortcuts(settings: QSettings, shortcuts: dict[str, str]) -> None:
    """Save shortcuts to settings."""
    for key, val in shortcuts.items():
        settings.setValue(f"shortcuts/{key}", val)


class ShortcutsDialog(QDialog):
    """Dialog to view and edit keyboard shortcuts."""

    def __init__(self, settings: QSettings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Raccourcis clavier")
        self.setMinimumSize(500, 500)
        self._settings = settings
        self._shortcuts = load_shortcuts(settings)

        layout = QVBoxLayout(self)

        self._table = QTableWidget()
        self._table.setColumnCount(3)
        self._table.setHorizontalHeaderLabels(["Action", "Raccourci", "Defaut"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        keys = list(DEFAULT_SHORTCUTS.keys())
        self._table.setRowCount(len(keys))
        self._key_edits: dict[str, QKeySequenceEdit] = {}

        for row, key in enumerate(keys):
            label = SHORTCUT_LABELS.get(key, key)
            self._table.setItem(row, 0, QTableWidgetItem(label))

            edit = QKeySequenceEdit(QKeySequence(self._shortcuts[key]))
            self._key_edits[key] = edit
            self._table.setCellWidget(row, 1, edit)

            default_item = QTableWidgetItem(DEFAULT_SHORTCUTS[key])
            default_item.setFlags(default_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._table.setItem(row, 2, default_item)

        layout.addWidget(self._table)

        btn_layout = QHBoxLayout()
        reset_btn = QPushButton("Reinitialiser tout")
        reset_btn.clicked.connect(self._reset_all)
        btn_layout.addWidget(reset_btn)
        btn_layout.addStretch()

        save_btn = QPushButton("Sauvegarder")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._save)
        btn_layout.addWidget(save_btn)

        cancel_btn = QPushButton("Annuler")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        layout.addLayout(btn_layout)

    def _reset_all(self) -> None:
        for key, edit in self._key_edits.items():
            edit.setKeySequence(QKeySequence(DEFAULT_SHORTCUTS[key]))

    def _save(self) -> None:
        new_shortcuts = {}
        for key, edit in self._key_edits.items():
            seq = edit.keySequence().toString()
            new_shortcuts[key] = seq if seq else DEFAULT_SHORTCUTS[key]
        save_shortcuts(self._settings, new_shortcuts)
        QMessageBox.information(
            self, "Raccourcis",
            "Raccourcis sauvegardes.\nRedemarrez l'application pour appliquer les changements."
        )
        self.accept()
