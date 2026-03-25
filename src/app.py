from __future__ import annotations

import os
import uuid

from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QPixmap, QAction, QKeySequence, QColor, QShortcut, QActionGroup
from PySide6.QtWidgets import (
    QMainWindow, QDockWidget, QFileDialog, QStatusBar,
    QToolBar, QMessageBox, QApplication,
)

from src.canvas.canvas import AnnotationScene, CanvasView, DrawMode
from src.canvas.items import BBoxItem, PolygonItem
from src.models.annotation import Annotation, AnnotationType, BoundingBox, Polygon
from src.models.project import Project
from src.models.label import LabelManager
from src.widgets.file_list import FileListWidget
from src.widgets.label_list import LabelListWidget
from src.widgets.annotation_list import AnnotationListWidget
from src.io.yolo import save_yolo, load_yolo, has_yolo_annotations
from src.io.voc import save_voc, load_voc
from src.io.coco import save_coco
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
        self._clipboard: list[dict] = []

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
        file_dock = QDockWidget("Images", self)
        file_dock.setWidget(self._file_list)
        file_dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, file_dock)

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

        export_menu = file_menu.addMenu("Exporter...")

        export_voc_action = QAction("PASCAL VOC (XML)", self)
        export_voc_action.triggered.connect(self._export_voc)
        export_menu.addAction(export_voc_action)

        export_coco_action = QAction("COCO (JSON)", self)
        export_coco_action.triggered.connect(self._export_coco)
        export_menu.addAction(export_coco_action)

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

        redo_action = QAction("Retablir", self)
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

        del_action = QAction("Supprimer la selection", self)
        del_action.setShortcut(QKeySequence("Delete"))
        del_action.triggered.connect(self._delete_selected)
        edit_menu.addAction(del_action)

        clear_action = QAction("Supprimer toutes les annotations", self)
        clear_action.setShortcut(QKeySequence("Ctrl+Delete"))
        clear_action.triggered.connect(self._clear_annotations)
        edit_menu.addAction(clear_action)

        # Tools menu
        tools_menu = menubar.addMenu("&Outils")

        tool_group = QActionGroup(self)

        self._bbox_mode_action = QAction("Rectangle (R)", self)
        self._bbox_mode_action.setShortcut(QKeySequence("R"))
        self._bbox_mode_action.setCheckable(True)
        self._bbox_mode_action.setChecked(True)
        self._bbox_mode_action.triggered.connect(lambda: self._set_draw_mode(DrawMode.BBOX))
        tool_group.addAction(self._bbox_mode_action)
        tools_menu.addAction(self._bbox_mode_action)

        self._poly_mode_action = QAction("Polygone (P)", self)
        self._poly_mode_action.setShortcut(QKeySequence("P"))
        self._poly_mode_action.setCheckable(True)
        self._poly_mode_action.triggered.connect(lambda: self._set_draw_mode(DrawMode.POLYGON))
        tool_group.addAction(self._poly_mode_action)
        tools_menu.addAction(self._poly_mode_action)

        # Navigation menu
        nav_menu = menubar.addMenu("&Navigation")

        next_action = QAction("Image suivante", self)
        next_action.setShortcut(QKeySequence("D"))
        next_action.triggered.connect(self._next_image)
        nav_menu.addAction(next_action)

        prev_action = QAction("Image precedente", self)
        prev_action.setShortcut(QKeySequence("A"))
        prev_action.triggered.connect(self._prev_image)
        nav_menu.addAction(prev_action)

        # View menu
        view_menu = menubar.addMenu("&Vue")

        fit_action = QAction("Ajuster a la fenetre", self)
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
        toolbar.addAction("Rect [R]", lambda: self._set_draw_mode(DrawMode.BBOX))
        toolbar.addAction("Poly [P]", lambda: self._set_draw_mode(DrawMode.POLYGON))
        toolbar.addSeparator()
        toolbar.addAction("Prec.", self._prev_image)
        toolbar.addAction("Suiv.", self._next_image)
        toolbar.addSeparator()
        toolbar.addAction("Ajuster", self._canvas.fit_image)

    def _setup_class_shortcuts(self) -> None:
        for i in range(9):
            shortcut = QShortcut(QKeySequence(str(i + 1)), self)
            shortcut.activated.connect(lambda idx=i: self._select_class(idx))

    def _set_draw_mode(self, mode: DrawMode) -> None:
        self._canvas.set_draw_mode(mode)
        if mode == DrawMode.BBOX:
            self._bbox_mode_action.setChecked(True)
        else:
            self._poly_mode_action.setChecked(True)
        self._statusbar.showMessage(
            f"Outil: {'Rectangle' if mode == DrawMode.BBOX else 'Polygone'}", 2000
        )

    def _select_class(self, index: int) -> None:
        if self._project.label_manager.get(index):
            self._label_list.set_current_class(index)
            label = self._project.label_manager.get(index)
            self._statusbar.showMessage(f"Classe active: {label.name} [{index + 1}]", 2000)

    def _connect_signals(self) -> None:
        self._file_list.file_selected.connect(self._on_file_selected)
        self._label_list.labels_changed.connect(self._on_labels_changed)
        self._canvas.bbox_drawn.connect(self._on_bbox_drawn)
        self._canvas.polygon_drawn.connect(self._on_polygon_drawn)
        self._scene.annotation_changed.connect(self._on_annotation_changed)
        self._annotation_list.annotation_selected.connect(self._on_annotation_list_selected)
        self._canvas.delete_requested.connect(self._delete_selected)

    # --- Undo / Redo ---

    def _undo(self) -> None:
        desc = self._undo_stack.undo()
        if desc:
            self._refresh_canvas()
            self._statusbar.showMessage(f"Annule: {desc}", 2000)

    def _redo(self) -> None:
        desc = self._undo_stack.redo()
        if desc:
            self._refresh_canvas()
            self._statusbar.showMessage(f"Retabli: {desc}", 2000)

    def _make_annotation_data(self, annotation: Annotation) -> dict:
        """Serialize annotation to dict for undo/redo/clipboard."""
        data: dict = {
            "uid": annotation.uid,
            "label_id": annotation.label_id,
            "ann_type": annotation.ann_type.value,
        }
        if annotation.ann_type == AnnotationType.BBOX and annotation.bbox:
            data["x"] = annotation.bbox.x
            data["y"] = annotation.bbox.y
            data["w"] = annotation.bbox.width
            data["h"] = annotation.bbox.height
        elif annotation.ann_type == AnnotationType.POLYGON and annotation.polygon:
            data["points"] = list(annotation.polygon.points)
        return data

    def _add_annotation_from_data(self, data: dict) -> None:
        ann_data = self._project.current_annotations()
        if not ann_data:
            return
        ann_type = AnnotationType(data.get("ann_type", "bbox"))
        if ann_type == AnnotationType.POLYGON:
            annotation = Annotation(
                label_id=data["label_id"],
                ann_type=AnnotationType.POLYGON,
                polygon=Polygon(points=list(data["points"])),
                uid=data["uid"],
            )
        else:
            annotation = Annotation(
                label_id=data["label_id"],
                ann_type=AnnotationType.BBOX,
                bbox=BoundingBox(x=data["x"], y=data["y"], width=data["w"], height=data["h"]),
                uid=data["uid"],
            )
        ann_data.add(annotation)

    def _remove_annotation_from_data(self, data: dict) -> None:
        ann_data = self._project.current_annotations()
        if not ann_data:
            return
        ann_data.remove(data["uid"])

    def _update_annotation_bbox(self, uid: str, bbox_data: dict) -> None:
        ann_data = self._project.current_annotations()
        if not ann_data:
            return
        for ann in ann_data.annotations:
            if ann.uid == uid:
                if ann.ann_type == AnnotationType.POLYGON and ann.polygon and "points" in bbox_data:
                    ann.polygon.points = list(bbox_data["points"])
                elif ann.bbox:
                    ann.bbox.x = bbox_data["x"]
                    ann.bbox.y = bbox_data["y"]
                    ann.bbox.width = bbox_data["w"]
                    ann.bbox.height = bbox_data["h"]
                ann_data.modified = True
                break

    # --- Copy / Paste ---

    def _copy_annotations(self) -> None:
        ann_data = self._project.current_annotations()
        if not ann_data:
            return

        selected_uids = {
            item.uid for item in self._scene.selectedItems()
            if isinstance(item, (BBoxItem, PolygonItem))
        }

        if selected_uids:
            self._clipboard = [
                self._make_annotation_data(ann)
                for ann in ann_data.annotations if ann.uid in selected_uids
            ]
        else:
            self._clipboard = [self._make_annotation_data(ann) for ann in ann_data.annotations]

        self._statusbar.showMessage(f"{len(self._clipboard)} annotation(s) copiee(s)", 2000)

    def _paste_annotations(self) -> None:
        if not self._clipboard:
            self._statusbar.showMessage("Rien a coller", 2000)
            return

        ann_data = self._project.current_annotations()
        if not ann_data:
            return

        for data in self._clipboard:
            new_data = dict(data)
            if "points" in new_data:
                new_data["points"] = list(new_data["points"])
            new_data["uid"] = uuid.uuid4().hex[:8]
            self._add_annotation_from_data(new_data)
            self._undo_stack.push(AddAnnotationAction(
                self._add_annotation_from_data, self._remove_annotation_from_data,
                new_data, "Coller annotation",
            ))

        self._refresh_canvas()
        self._statusbar.showMessage(f"{len(self._clipboard)} annotation(s) collee(s)", 2000)

    # --- Delete ---

    def _delete_selected(self) -> None:
        ann_data = self._project.current_annotations()
        if not ann_data:
            return

        selected_items = [
            item for item in self._scene.selectedItems()
            if isinstance(item, (BBoxItem, PolygonItem))
        ]
        if not selected_items:
            return

        for item in selected_items:
            for ann in ann_data.annotations:
                if ann.uid == item.uid:
                    data = self._make_annotation_data(ann)
                    self._undo_stack.push(RemoveAnnotationAction(
                        self._add_annotation_from_data, self._remove_annotation_from_data, data,
                    ))
                    break
            ann_data.remove(item.uid)
            self._scene.removeItem(item)

        self._annotation_list.set_data(ann_data, self._project.label_manager)
        self._statusbar.showMessage(f"{len(selected_items)} annotation(s) supprimee(s)", 2000)

    def _clear_annotations(self) -> None:
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

        for ann in list(ann_data.annotations):
            data = self._make_annotation_data(ann)
            self._undo_stack.push(RemoveAnnotationAction(
                self._add_annotation_from_data, self._remove_annotation_from_data, data,
            ))

        ann_data.clear()
        self._refresh_canvas()
        self._statusbar.showMessage("Toutes les annotations supprimees", 2000)

    # --- Drawing callbacks ---

    def _on_bbox_drawn(self, x: float, y: float, w: float, h: float) -> None:
        if not self._project.label_manager.labels:
            QMessageBox.warning(self, "Pas de classe",
                                "Veuillez d'abord creer au moins une classe.")
            return

        class_id = self._label_list.current_class_id()
        label = self._project.label_manager.get(class_id)
        if not label:
            return

        ann_data = self._project.current_annotations()
        if not ann_data:
            return

        x = max(0, x)
        y = max(0, y)
        w = min(w, ann_data.image_width - x)
        h = min(h, ann_data.image_height - y)

        annotation = Annotation(
            label_id=class_id,
            ann_type=AnnotationType.BBOX,
            bbox=BoundingBox(x=x, y=y, width=w, height=h),
        )
        ann_data.add(annotation)

        data = self._make_annotation_data(annotation)
        self._undo_stack.push(AddAnnotationAction(
            self._add_annotation_from_data, self._remove_annotation_from_data, data,
        ))

        item = BBoxItem(x, y, w, h, QColor(label.color), label.name, annotation.uid)
        self._scene.addItem(item)

        self._annotation_list.set_data(ann_data, self._project.label_manager)
        self._statusbar.showMessage(
            f"BBox ajoutee: {label.name} ({len(ann_data.annotations)} total)", 2000
        )

    def _on_polygon_drawn(self, points: list) -> None:
        if not self._project.label_manager.labels:
            QMessageBox.warning(self, "Pas de classe",
                                "Veuillez d'abord creer au moins une classe.")
            return

        class_id = self._label_list.current_class_id()
        label = self._project.label_manager.get(class_id)
        if not label:
            return

        ann_data = self._project.current_annotations()
        if not ann_data:
            return

        annotation = Annotation(
            label_id=class_id,
            ann_type=AnnotationType.POLYGON,
            polygon=Polygon(points=points),
        )
        ann_data.add(annotation)

        data = self._make_annotation_data(annotation)
        self._undo_stack.push(AddAnnotationAction(
            self._add_annotation_from_data, self._remove_annotation_from_data, data,
        ))

        item = PolygonItem(points, QColor(label.color), label.name, annotation.uid)
        self._scene.addItem(item)

        self._annotation_list.set_data(ann_data, self._project.label_manager)
        self._statusbar.showMessage(
            f"Polygone ajoute: {label.name} ({len(annotation.polygon.points)} pts)", 2000
        )

    def _on_annotation_changed(self, item, old_data=None) -> None:
        """Called when any annotation item is moved/resized on the canvas."""
        ann_data = self._project.current_annotations()
        if not ann_data:
            return

        if isinstance(item, PolygonItem):
            new_points = item.get_points()
            for ann in ann_data.annotations:
                if ann.uid == item.uid and ann.polygon:
                    if old_data:
                        self._undo_stack.push(MoveAnnotationAction(
                            self._update_annotation_bbox, ann.uid,
                            {"points": old_data},
                            {"points": new_points},
                        ))
                    ann.polygon.points = new_points
                    ann_data.modified = True
                    break
        elif isinstance(item, BBoxItem):
            rect = item.get_rect_in_scene()
            new_bbox = {"x": rect.x(), "y": rect.y(), "w": rect.width(), "h": rect.height()}
            for ann in ann_data.annotations:
                if ann.uid == item.uid and ann.bbox:
                    if old_data:
                        self._undo_stack.push(MoveAnnotationAction(
                            self._update_annotation_bbox, ann.uid, old_data, new_bbox,
                        ))
                    ann.bbox.x = rect.x()
                    ann.bbox.y = rect.y()
                    ann.bbox.width = rect.width()
                    ann.bbox.height = rect.height()
                    ann_data.modified = True
                    break

        self._annotation_list.set_data(ann_data, self._project.label_manager)

    def _on_annotation_list_selected(self, uid: str) -> None:
        for item in self._scene.items():
            if isinstance(item, (BBoxItem, PolygonItem)):
                selected = item.uid == uid
                item.set_selected_style(selected)
                item.setSelected(selected)

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

            if not self._project.label_manager.labels:
                self._label_list._on_add()

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
            self._statusbar.showMessage("Sauvegarde.", 2000)

    def _save_all(self) -> None:
        for img_path, ann in self._project._annotations_cache.items():
            if ann.modified:
                save_yolo(ann)
        self._project.save_classes_txt()
        self._statusbar.showMessage("Tout sauvegarde.", 2000)

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

    # --- Canvas refresh ---

    def _create_item_for_annotation(self, ann: Annotation) -> BBoxItem | PolygonItem | None:
        label = self._project.label_manager.get(ann.label_id)
        color = QColor(label.color) if label else QColor("#888888")
        name = label.name if label else f"class_{ann.label_id}"

        if ann.ann_type == AnnotationType.POLYGON and ann.polygon:
            return PolygonItem(ann.polygon.points, color, name, ann.uid)
        elif ann.bbox:
            return BBoxItem(ann.bbox.x, ann.bbox.y, ann.bbox.width, ann.bbox.height,
                            color, name, ann.uid)
        return None

    def _refresh_canvas(self) -> None:
        ann_data = self._project.current_annotations()
        if not ann_data:
            return

        for item in list(self._scene.items()):
            if isinstance(item, (BBoxItem, PolygonItem)):
                self._scene.removeItem(item)

        for ann in ann_data.annotations:
            item = self._create_item_for_annotation(ann)
            if item:
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

        ann_data = self._project.get_annotations(path)
        if not ann_data.annotations:
            loaded = load_yolo(path, pixmap.width(), pixmap.height())
            for a in loaded:
                ann_data.add(a)
            ann_data.modified = False

        for ann in ann_data.annotations:
            item = self._create_item_for_annotation(ann)
            if item:
                self._scene.addItem(item)

        self._annotation_list.set_data(ann_data, self._project.label_manager)

        name = self._project.current_image_name()
        total = self._project.total_images()
        mode = "Rect" if self._canvas.draw_mode == DrawMode.BBOX else "Poly"
        self._statusbar.showMessage(
            f"{name} — {index + 1}/{total} — {pixmap.width()}x{pixmap.height()} [{mode}]"
        )

    # --- Export ---

    def _export_voc(self) -> None:
        """Export all annotations as PASCAL VOC XML (one file per image)."""
        self._save_all()  # save YOLO first
        if not self._project.image_dir:
            return

        count = 0
        for img_path, ann in self._project._annotations_cache.items():
            if ann.annotations:
                save_voc(ann, self._project.label_manager)
                count += 1

        self._statusbar.showMessage(f"Export VOC: {count} fichier(s) XML crees", 3000)

    def _export_coco(self) -> None:
        """Export all annotations as a single COCO JSON file."""
        self._save_all()
        if not self._project.image_dir:
            return

        output_path, _ = QFileDialog.getSaveFileName(
            self, "Exporter COCO JSON",
            os.path.join(self._project.image_dir, "annotations.json"),
            "JSON (*.json)",
        )
        if not output_path:
            return

        save_coco(self._project._annotations_cache, self._project.label_manager, output_path)
        self._statusbar.showMessage(f"Export COCO: {output_path}", 3000)

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
