from __future__ import annotations

import copy
import os

from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QPixmap, QAction, QKeySequence, QColor, QShortcut
from PySide6.QtWidgets import (
    QMainWindow, QDockWidget, QFileDialog, QStatusBar,
    QToolBar, QMessageBox, QApplication,
)

from src.canvas.canvas import AnnotationScene, CanvasView
from src.canvas.items import BBoxItem
from src.models.annotation import Annotation, BoundingBox
from src.models.project import Project
from src.models.label import LabelManager
from src.widgets.file_list import FileListWidget
from src.widgets.label_list import LabelListWidget
from src.widgets.annotation_list import AnnotationListWidget
from src.io.yolo import save_yolo, load_yolo, has_yolo_annotations
from src.utils.undo import (
    UndoStack, AddAnnotationAction, RemoveAnnotationAction, MoveAnnotationAction,
)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LabelImage")
        self.setMinimumSize(1200, 800)

        self._project = Project()
        self._settings = QSettings("LabelImage", "LabelImage")
        self._undo_stack = UndoStack()
        self._clipboard: list[dict] = []  # copied annotation data

        # --- Scene & Canvas ---
        self._scene = AnnotationScene(self)
        self._canvas = CanvasView(self._scene, self)
        self.setCentralWidget(self._canvas)

        # --- Widgets ---
        self._file_list = FileListWidget()
        self._label_list = LabelListWidget()
        self._annotation_list = AnnotationListWidget()

        # --- Docks ---
        self._setup_docks()

        # --- Menus & Toolbar ---
        self._setup_menus()
        self._setup_toolbar()
        self._setup_class_shortcuts()

        # --- Status bar ---
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)

        # --- Signals ---
        self._connect_signals()

        # --- Restore state ---
        self._restore_state()

    def _setup_docks(self) -> None:
        # Left: file list
        file_dock = QDockWidget("Images", self)
        file_dock.setWidget(self._file_list)
        file_dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, file_dock)

        # Right: labels + annotations
        label_dock = QDockWidget("Classes", self)
        label_dock.setWidget(self._label_list)
        label_dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, label_dock)

        ann_dock = QDockWidget("Annotations", self)
        ann_dock.setWidget(self._annotation_list)
        ann_dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, ann_dock)

    def _setup_menus(self) -> None:
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&Fichier")

        open_dir_action = QAction("Ouvrir un dossier...", self)
        open_dir_action.setShortcut(QKeySequence("Ctrl+O"))
        open_dir_action.triggered.connect(self._open_directory)
        file_menu.addAction(open_dir_action)

        save_action = QAction("Sauvegarder", self)
        save_action.setShortcut(QKeySequence("Ctrl+S"))
        save_action.triggered.connect(self._save_current)
        file_menu.addAction(save_action)

        save_all_action = QAction("Tout sauvegarder", self)
        save_all_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        save_all_action.triggered.connect(self._save_all)
        file_menu.addAction(save_all_action)

        file_menu.addSeparator()

        quit_action = QAction("Quitter", self)
        quit_action.setShortcut(QKeySequence("Ctrl+Q"))
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # Edit menu
        edit_menu = menubar.addMenu("&Edition")

        undo_action = QAction("Annuler", self)
        undo_action.setShortcut(QKeySequence("Ctrl+Z"))
        undo_action.triggered.connect(self._undo)
        edit_menu.addAction(undo_action)

        redo_action = QAction("Rétablir", self)
        redo_action.setShortcut(QKeySequence("Ctrl+Y"))
        redo_action.triggered.connect(self._redo)
        edit_menu.addAction(redo_action)

        edit_menu.addSeparator()

        copy_action = QAction("Copier annotations", self)
        copy_action.setShortcut(QKeySequence("Ctrl+C"))
        copy_action.triggered.connect(self._copy_annotations)
        edit_menu.addAction(copy_action)

        paste_action = QAction("Coller annotations", self)
        paste_action.setShortcut(QKeySequence("Ctrl+V"))
        paste_action.triggered.connect(self._paste_annotations)
        edit_menu.addAction(paste_action)

        edit_menu.addSeparator()

        del_action = QAction("Supprimer la sélection", self)
        del_action.setShortcut(QKeySequence("Delete"))
        del_action.triggered.connect(self._delete_selected)
        edit_menu.addAction(del_action)

        clear_action = QAction("Supprimer toutes les annotations", self)
        clear_action.setShortcut(QKeySequence("Ctrl+Delete"))
        clear_action.triggered.connect(self._clear_annotations)
        edit_menu.addAction(clear_action)

        # Navigation menu
        nav_menu = menubar.addMenu("&Navigation")

        next_action = QAction("Image suivante", self)
        next_action.setShortcut(QKeySequence("D"))
        next_action.triggered.connect(self._next_image)
        nav_menu.addAction(next_action)

        prev_action = QAction("Image précédente", self)
        prev_action.setShortcut(QKeySequence("A"))
        prev_action.triggered.connect(self._prev_image)
        nav_menu.addAction(prev_action)

        # View menu
        view_menu = menubar.addMenu("&Vue")

        fit_action = QAction("Ajuster à la fenêtre", self)
        fit_action.setShortcut(QKeySequence("Ctrl+0"))
        fit_action.triggered.connect(self._canvas.fit_image)
        view_menu.addAction(fit_action)

    def _setup_toolbar(self) -> None:
        toolbar = QToolBar("Outils")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        toolbar.addAction("Ouvrir", self._open_directory)
        toolbar.addAction("Sauver", self._save_current)
        toolbar.addSeparator()
        toolbar.addAction("Annuler", self._undo)
        toolbar.addAction("Retablir", self._redo)
        toolbar.addSeparator()
        toolbar.addAction("Prec.", self._prev_image)
        toolbar.addAction("Suiv.", self._next_image)
        toolbar.addSeparator()
        toolbar.addAction("Ajuster", self._canvas.fit_image)

    def _setup_class_shortcuts(self) -> None:
        """Setup 1-9 keyboard shortcuts for class selection."""
        for i in range(9):
            shortcut = QShortcut(QKeySequence(str(i + 1)), self)
            shortcut.activated.connect(lambda idx=i: self._select_class(idx))

    def _select_class(self, index: int) -> None:
        if self._project.label_manager.get(index):
            self._label_list.set_current_class(index)
            label = self._project.label_manager.get(index)
            self._statusbar.showMessage(f"Classe active: {label.name} [{index + 1}]", 2000)

    def _connect_signals(self) -> None:
        self._file_list.file_selected.connect(self._on_file_selected)
        self._label_list.labels_changed.connect(self._on_labels_changed)
        self._canvas.bbox_drawn.connect(self._on_bbox_drawn)
        self._scene.annotation_changed.connect(self._on_annotation_changed)
        self._annotation_list.annotation_selected.connect(self._on_annotation_list_selected)
        self._canvas.delete_requested.connect(self._delete_selected)

    # --- Undo / Redo ---

    def _undo(self) -> None:
        desc = self._undo_stack.undo()
        if desc:
            self._refresh_canvas()
            self._statusbar.showMessage(f"Annulé: {desc}", 2000)

    def _redo(self) -> None:
        desc = self._undo_stack.redo()
        if desc:
            self._refresh_canvas()
            self._statusbar.showMessage(f"Rétabli: {desc}", 2000)

    def _make_annotation_data(self, annotation: Annotation) -> dict:
        """Serialize annotation to dict for undo/redo."""
        return {
            "uid": annotation.uid,
            "label_id": annotation.label_id,
            "x": annotation.bbox.x,
            "y": annotation.bbox.y,
            "w": annotation.bbox.width,
            "h": annotation.bbox.height,
        }

    def _add_annotation_from_data(self, data: dict) -> None:
        """Add annotation from serialized data (for undo/redo)."""
        ann_data = self._project.current_annotations()
        if not ann_data:
            return
        annotation = Annotation(
            label_id=data["label_id"],
            bbox=BoundingBox(x=data["x"], y=data["y"], width=data["w"], height=data["h"]),
            uid=data["uid"],
        )
        ann_data.add(annotation)

    def _remove_annotation_from_data(self, data: dict) -> None:
        """Remove annotation from serialized data (for undo/redo)."""
        ann_data = self._project.current_annotations()
        if not ann_data:
            return
        ann_data.remove(data["uid"])

    def _update_annotation_bbox(self, uid: str, bbox_data: dict) -> None:
        """Update annotation bbox from dict (for undo/redo)."""
        ann_data = self._project.current_annotations()
        if not ann_data:
            return
        for ann in ann_data.annotations:
            if ann.uid == uid:
                ann.bbox.x = bbox_data["x"]
                ann.bbox.y = bbox_data["y"]
                ann.bbox.width = bbox_data["w"]
                ann.bbox.height = bbox_data["h"]
                ann_data.modified = True
                break

    # --- Copy / Paste ---

    def _copy_annotations(self) -> None:
        """Copy selected annotations (or all if none selected) to clipboard."""
        ann_data = self._project.current_annotations()
        if not ann_data:
            return

        # Get selected items from canvas
        selected_uids = {
            item.uid for item in self._scene.selectedItems()
            if isinstance(item, BBoxItem)
        }

        if selected_uids:
            self._clipboard = [
                self._make_annotation_data(ann)
                for ann in ann_data.annotations
                if ann.uid in selected_uids
            ]
        else:
            # Copy all annotations
            self._clipboard = [
                self._make_annotation_data(ann)
                for ann in ann_data.annotations
            ]

        count = len(self._clipboard)
        self._statusbar.showMessage(f"{count} annotation(s) copiée(s)", 2000)

    def _paste_annotations(self) -> None:
        """Paste clipboard annotations onto current image."""
        if not self._clipboard:
            self._statusbar.showMessage("Rien à coller", 2000)
            return

        ann_data = self._project.current_annotations()
        if not ann_data:
            return

        import uuid
        for data in self._clipboard:
            new_data = dict(data)
            new_data["uid"] = uuid.uuid4().hex[:8]
            self._add_annotation_from_data(new_data)
            self._undo_stack.push(AddAnnotationAction(
                self._add_annotation_from_data,
                self._remove_annotation_from_data,
                new_data,
                "Coller annotation",
            ))

        self._refresh_canvas()
        self._statusbar.showMessage(
            f"{len(self._clipboard)} annotation(s) collée(s)", 2000
        )

    # --- Delete ---

    def _delete_selected(self) -> None:
        """Delete selected annotations from canvas and data."""
        ann_data = self._project.current_annotations()
        if not ann_data:
            return

        selected_items = [
            item for item in self._scene.selectedItems()
            if isinstance(item, BBoxItem)
        ]
        if not selected_items:
            return

        for item in selected_items:
            for ann in ann_data.annotations:
                if ann.uid == item.uid:
                    data = self._make_annotation_data(ann)
                    self._undo_stack.push(RemoveAnnotationAction(
                        self._add_annotation_from_data,
                        self._remove_annotation_from_data,
                        data,
                    ))
                    break
            ann_data.remove(item.uid)
            self._scene.removeItem(item)

        self._annotation_list.set_data(ann_data, self._project.label_manager)
        self._statusbar.showMessage(
            f"{len(selected_items)} annotation(s) supprimée(s)", 2000
        )

    def _clear_annotations(self) -> None:
        """Clear all annotations on current image."""
        ann_data = self._project.current_annotations()
        if not ann_data or not ann_data.annotations:
            return

        reply = QMessageBox.question(
            self, "Supprimer tout",
            f"Supprimer les {len(ann_data.annotations)} annotations ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        # Push undo for each
        for ann in list(ann_data.annotations):
            data = self._make_annotation_data(ann)
            self._undo_stack.push(RemoveAnnotationAction(
                self._add_annotation_from_data,
                self._remove_annotation_from_data,
                data,
            ))

        ann_data.clear()
        self._refresh_canvas()
        self._statusbar.showMessage("Toutes les annotations supprimées", 2000)

    # --- Actions ---

    def _open_directory(self) -> None:
        last_dir = self._settings.value("last_directory", "")
        directory = QFileDialog.getExistingDirectory(
            self, "Ouvrir un dossier d'images", last_dir
        )
        if directory:
            self._settings.setValue("last_directory", directory)
            self._project.open_directory(directory)
            self._file_list.set_files(self._project.image_files)
            self._label_list.set_label_manager(self._project.label_manager)
            self._undo_stack.clear()

            # If no labels exist, prompt user to create one
            if not self._project.label_manager.labels:
                self._label_list._on_add()

            # Mark files with existing annotations
            for i, fname in enumerate(self._project.image_files):
                img_path = os.path.join(directory, fname)
                self._file_list.mark_annotated(i, has_yolo_annotations(img_path))

            if self._project.image_files:
                self._load_image(0)

    def _save_current(self) -> None:
        ann = self._project.current_annotations()
        if ann:
            save_yolo(ann)
            self._project.save_classes_txt()
            idx = self._project.current_index
            self._file_list.mark_annotated(idx, bool(ann.annotations))
            self._statusbar.showMessage("Sauvegardé.", 2000)

    def _save_all(self) -> None:
        for img_path, ann in self._project._annotations_cache.items():
            if ann.modified:
                save_yolo(ann)
        self._project.save_classes_txt()
        self._statusbar.showMessage("Tout sauvegardé.", 2000)

    def _next_image(self) -> None:
        self._auto_save()
        if self._project.go_next():
            self._undo_stack.clear()
            self._load_image(self._project.current_index)

    def _prev_image(self) -> None:
        self._auto_save()
        if self._project.go_prev():
            self._undo_stack.clear()
            self._load_image(self._project.current_index)

    def _auto_save(self) -> None:
        ann = self._project.current_annotations()
        if ann and ann.modified:
            save_yolo(ann)
            self._project.save_classes_txt()
            idx = self._project.current_index
            self._file_list.mark_annotated(idx, bool(ann.annotations))

    def _on_file_selected(self, index: int) -> None:
        self._auto_save()
        if self._project.go_to(index):
            self._undo_stack.clear()
            self._load_image(index)

    def _on_labels_changed(self) -> None:
        self._project.save_classes_txt()

    def _on_bbox_drawn(self, x: float, y: float, w: float, h: float) -> None:
        if not self._project.label_manager.labels:
            QMessageBox.warning(self, "Pas de classe",
                                "Veuillez d'abord créer au moins une classe.")
            return

        class_id = self._label_list.current_class_id()
        label = self._project.label_manager.get(class_id)
        if not label:
            return

        # Clamp to image bounds
        ann_data = self._project.current_annotations()
        if not ann_data:
            return

        x = max(0, x)
        y = max(0, y)
        w = min(w, ann_data.image_width - x)
        h = min(h, ann_data.image_height - y)

        annotation = Annotation(
            label_id=class_id,
            bbox=BoundingBox(x=x, y=y, width=w, height=h),
        )
        ann_data.add(annotation)

        # Push undo action
        data = self._make_annotation_data(annotation)
        self._undo_stack.push(AddAnnotationAction(
            self._add_annotation_from_data,
            self._remove_annotation_from_data,
            data,
        ))

        # Add visual item
        item = BBoxItem(x, y, w, h, QColor(label.color), label.name, annotation.uid)
        self._scene.addItem(item)

        # Refresh annotation list
        self._annotation_list.set_data(ann_data, self._project.label_manager)
        self._statusbar.showMessage(
            f"Annotation ajoutée: {label.name} ({len(ann_data.annotations)} total)", 2000
        )

    def _on_annotation_changed(self, item: BBoxItem, old_rect: dict | None = None) -> None:
        """Called when a bbox is moved or resized on the canvas."""
        ann_data = self._project.current_annotations()
        if not ann_data:
            return

        rect = item.get_rect_in_scene()
        new_bbox = {"x": rect.x(), "y": rect.y(), "w": rect.width(), "h": rect.height()}

        for ann in ann_data.annotations:
            if ann.uid == item.uid:
                if old_rect:
                    self._undo_stack.push(MoveAnnotationAction(
                        self._update_annotation_bbox,
                        ann.uid,
                        old_rect,
                        new_bbox,
                    ))
                ann.bbox.x = rect.x()
                ann.bbox.y = rect.y()
                ann.bbox.width = rect.width()
                ann.bbox.height = rect.height()
                ann_data.modified = True
                break

        self._annotation_list.set_data(ann_data, self._project.label_manager)

    def _on_annotation_list_selected(self, uid: str) -> None:
        """Highlight the bbox on canvas when selected in the list."""
        for item in self._scene.items():
            if isinstance(item, BBoxItem):
                selected = item.uid == uid
                item.set_selected_style(selected)
                item.setSelected(selected)

    # --- Canvas refresh ---

    def _refresh_canvas(self) -> None:
        """Redraw all annotations on current image."""
        ann_data = self._project.current_annotations()
        if not ann_data:
            return

        # Remove all bbox items but keep the pixmap
        for item in list(self._scene.items()):
            if isinstance(item, BBoxItem):
                self._scene.removeItem(item)

        # Redraw from data
        for ann in ann_data.annotations:
            label = self._project.label_manager.get(ann.label_id)
            color = QColor(label.color) if label else QColor("#888888")
            name = label.name if label else f"class_{ann.label_id}"
            item = BBoxItem(
                ann.bbox.x, ann.bbox.y, ann.bbox.width, ann.bbox.height,
                color, name, ann.uid
            )
            self._scene.addItem(item)

        self._annotation_list.set_data(ann_data, self._project.label_manager)

    # --- Image loading ---

    def _load_image(self, index: int) -> None:
        self._file_list.set_current(index)
        path = self._project.current_image_path()
        if not path:
            return

        pixmap = QPixmap(path)
        if pixmap.isNull():
            self._statusbar.showMessage(f"Impossible de charger: {path}", 3000)
            return

        self._scene.set_image(pixmap)
        self._canvas.fit_image()

        # Load existing annotations
        ann_data = self._project.get_annotations(path)
        if not ann_data.annotations:
            loaded = load_yolo(path, pixmap.width(), pixmap.height())
            for a in loaded:
                ann_data.add(a)
            ann_data.modified = False  # Just loaded, not modified

        # Draw annotations on canvas
        for ann in ann_data.annotations:
            label = self._project.label_manager.get(ann.label_id)
            color = QColor(label.color) if label else QColor("#888888")
            name = label.name if label else f"class_{ann.label_id}"
            item = BBoxItem(
                ann.bbox.x, ann.bbox.y, ann.bbox.width, ann.bbox.height,
                color, name, ann.uid
            )
            self._scene.addItem(item)

        self._annotation_list.set_data(ann_data, self._project.label_manager)

        # Update status bar
        name = self._project.current_image_name()
        total = self._project.total_images()
        self._statusbar.showMessage(
            f"{name} — {index + 1}/{total} — {pixmap.width()}x{pixmap.height()}"
        )

    # --- State ---

    def _restore_state(self) -> None:
        geometry = self._settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        state = self._settings.value("windowState")
        if state:
            self.restoreState(state)

    def closeEvent(self, event) -> None:
        self._auto_save()
        self._settings.setValue("geometry", self.saveGeometry())
        self._settings.setValue("windowState", self.saveState())
        super().closeEvent(event)
