from __future__ import annotations

import os
import uuid

from PySide6.QtCore import Qt, QSettings, QTimer
from PySide6.QtGui import QPixmap, QAction, QKeySequence, QColor, QShortcut, QActionGroup, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QMainWindow, QDockWidget, QFileDialog, QStatusBar,
    QToolBar, QMessageBox, QApplication, QLabel, QMenu,
    QInputDialog,
)

from src.canvas.canvas import AnnotationScene, CanvasView, DrawMode
from src.canvas.items import BBoxItem, PolygonItem
from src.models.annotation import Annotation, AnnotationType, BoundingBox, Polygon
from src.models.project import Project
from src.models.label import LabelManager
from src.widgets.file_list import FileListWidget
from src.widgets.label_list import LabelListWidget
from src.widgets.annotation_list import AnnotationListWidget
from src.widgets.auto_annotate_dialog import AutoAnnotateDialog
from src.widgets.stats_dialog import StatsDialog
from src.widgets.image_adjustments import ImageAdjustmentsWidget
from src.widgets.minimap import MiniMapWidget
from src.widgets.predict_dialog import PredictDialog
from src.widgets.shortcuts_dialog import ShortcutsDialog, load_shortcuts
from src.widgets.properties_panel import PropertiesPanel
from src.widgets.split_dialog import SplitDialog
from src.utils.themes import DARK_THEME, LIGHT_THEME
from src.io.yolo import save_yolo, load_yolo, has_yolo_annotations
from src.io.voc import save_voc, load_voc
from src.io.coco import save_coco, load_coco
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
        self._image_adjustments = ImageAdjustmentsWidget()
        self._minimap = MiniMapWidget()
        self._properties_panel = PropertiesPanel()
        self._annotations_locked = False
        self._review_mode = False
        self._dark_theme = True
        self._shortcuts = load_shortcuts(self._settings)

        # Drag & drop
        self.setAcceptDrops(True)

        # Auto-backup timer (every 5 minutes)
        self._backup_timer = QTimer(self)
        self._backup_timer.timeout.connect(self._auto_backup)
        self._backup_timer.start(300_000)

        # --- Docks ---
        self._setup_docks()

        # --- Menus & Toolbar ---
        self._setup_menus()
        self._setup_toolbar()
        self._setup_class_shortcuts()

        # --- Status bar ---
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)
        self._zoom_label = QLabel("100%")
        self._zoom_label.setStyleSheet("padding: 0 8px;")
        self._statusbar.addPermanentWidget(self._zoom_label)
        self._coord_label = QLabel("x: — y: —")
        self._coord_label.setStyleSheet("padding: 0 8px;")
        self._statusbar.addPermanentWidget(self._coord_label)

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

        adj_dock = QDockWidget("Affichage", self)
        adj_dock.setWidget(self._image_adjustments)
        adj_dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, adj_dock)

        props_dock = QDockWidget("Proprietes", self)
        props_dock.setWidget(self._properties_panel)
        props_dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, props_dock)

        minimap_dock = QDockWidget("Vue d'ensemble", self)
        minimap_dock.setWidget(self._minimap)
        minimap_dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, minimap_dock)
        self._minimap.set_main_view(self._canvas)

    def _setup_menus(self) -> None:
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&Fichier")

        open_dir_action = QAction("Ouvrir un dossier...", self)
        open_dir_action.setShortcut(QKeySequence("Ctrl+O"))
        open_dir_action.triggered.connect(self._open_directory)
        file_menu.addAction(open_dir_action)

        self._recent_menu = file_menu.addMenu("Dossiers recents")
        self._update_recent_menu()

        set_ann_dir_action = QAction("Dossier d'annotations...", self)
        set_ann_dir_action.triggered.connect(self._set_annotations_dir)
        file_menu.addAction(set_ann_dir_action)

        save_action = QAction("Sauvegarder", self)
        save_action.setShortcut(QKeySequence("Ctrl+S"))
        save_action.triggered.connect(self._save_current)
        file_menu.addAction(save_action)

        save_all_action = QAction("Tout sauvegarder", self)
        save_all_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        save_all_action.triggered.connect(self._save_all)
        file_menu.addAction(save_all_action)

        file_menu.addSeparator()

        import_menu = file_menu.addMenu("Importer...")

        import_voc_action = QAction("PASCAL VOC (XML du dossier)", self)
        import_voc_action.triggered.connect(self._import_voc)
        import_menu.addAction(import_voc_action)

        import_coco_action = QAction("COCO (JSON)", self)
        import_coco_action.triggered.connect(self._import_coco)
        import_menu.addAction(import_coco_action)

        export_menu = file_menu.addMenu("Exporter...")

        export_voc_action = QAction("PASCAL VOC (XML)", self)
        export_voc_action.triggered.connect(self._export_voc)
        export_menu.addAction(export_voc_action)

        export_coco_action = QAction("COCO (JSON)", self)
        export_coco_action.triggered.connect(self._export_coco)
        export_menu.addAction(export_coco_action)

        export_crops_action = QAction("Crops (images decoupees)", self)
        export_crops_action.triggered.connect(self._export_crops)
        export_menu.addAction(export_crops_action)

        export_split_action = QAction("YOLO avec split train/val/test", self)
        export_split_action.triggered.connect(self._export_split)
        export_menu.addAction(export_split_action)

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

        edit_menu.addSeparator()

        select_all_action = QAction("Tout selectionner", self)
        select_all_action.setShortcut(QKeySequence("Ctrl+A"))
        select_all_action.triggered.connect(self._select_all)
        edit_menu.addAction(select_all_action)

        change_class_action = QAction("Changer classe de la selection (E)", self)
        change_class_action.setShortcut(QKeySequence("E"))
        change_class_action.triggered.connect(self._change_selected_class)
        edit_menu.addAction(change_class_action)

        edit_menu.addSeparator()

        to_bbox_action = QAction("Convertir en BBox", self)
        to_bbox_action.triggered.connect(self._convert_selected_to_bbox)
        edit_menu.addAction(to_bbox_action)

        to_poly_action = QAction("Convertir en Polygone", self)
        to_poly_action.triggered.connect(self._convert_selected_to_polygon)
        edit_menu.addAction(to_poly_action)

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

        tools_menu.addSeparator()

        auto_annotate_action = QAction("Pre-annotation YOLO...", self)
        auto_annotate_action.setShortcut(QKeySequence("Ctrl+Shift+A"))
        auto_annotate_action.triggered.connect(self._show_auto_annotate)
        tools_menu.addAction(auto_annotate_action)

        predict_action = QAction("Predire depuis annotations precedentes...", self)
        predict_action.setShortcut(QKeySequence("Ctrl+Shift+P"))
        predict_action.triggered.connect(self._show_predict)
        tools_menu.addAction(predict_action)

        tools_menu.addSeparator()

        stats_action = QAction("Statistiques...", self)
        stats_action.triggered.connect(self._show_stats)
        tools_menu.addAction(stats_action)

        tools_menu.addSeparator()

        self._review_action = QAction("Mode revue", self)
        self._review_action.setShortcut(QKeySequence("Ctrl+Shift+V"))
        self._review_action.setCheckable(True)
        self._review_action.triggered.connect(self._toggle_review_mode)
        tools_menu.addAction(self._review_action)

        tools_menu.addSeparator()

        shortcuts_action = QAction("Raccourcis clavier...", self)
        shortcuts_action.triggered.connect(self._show_shortcuts)
        tools_menu.addAction(shortcuts_action)

        # Help menu
        help_menu = menubar.addMenu("&Aide")
        about_action = QAction("A propos de LabelImage...", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

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

        zoom_sel_action = QAction("Zoom sur selection (F)", self)
        zoom_sel_action.setShortcut(QKeySequence("F"))
        zoom_sel_action.triggered.connect(self._zoom_to_selected)
        view_menu.addAction(zoom_sel_action)

        view_menu.addSeparator()

        self._crosshair_action = QAction("Reticule (crosshair)", self)
        self._crosshair_action.setCheckable(True)
        self._crosshair_action.setChecked(True)
        self._crosshair_action.triggered.connect(
            lambda checked: self._canvas.set_crosshair(checked)
        )
        view_menu.addAction(self._crosshair_action)

        view_menu.addSeparator()

        rotate_cw_action = QAction("Rotation 90 CW", self)
        rotate_cw_action.setShortcut(QKeySequence("Ctrl+R"))
        rotate_cw_action.triggered.connect(lambda: self._rotate_view(90))
        view_menu.addAction(rotate_cw_action)

        rotate_ccw_action = QAction("Rotation 90 CCW", self)
        rotate_ccw_action.setShortcut(QKeySequence("Ctrl+Shift+R"))
        rotate_ccw_action.triggered.connect(lambda: self._rotate_view(-90))
        view_menu.addAction(rotate_ccw_action)

        reset_rotation_action = QAction("Reset rotation", self)
        reset_rotation_action.triggered.connect(lambda: self._rotate_view(0))
        view_menu.addAction(reset_rotation_action)

        view_menu.addSeparator()

        self._grid_action = QAction("Grille", self)
        self._grid_action.setShortcut(QKeySequence("G"))
        self._grid_action.setCheckable(True)
        self._grid_action.setChecked(False)
        self._grid_action.triggered.connect(self._toggle_grid)
        view_menu.addAction(self._grid_action)

        self._lock_action = QAction("Verrouiller annotations (L)", self)
        self._lock_action.setShortcut(QKeySequence("L"))
        self._lock_action.setCheckable(True)
        self._lock_action.setChecked(False)
        self._lock_action.triggered.connect(self._toggle_lock)
        view_menu.addAction(self._lock_action)

        view_menu.addSeparator()

        self._theme_action = QAction("Theme clair", self)
        self._theme_action.setCheckable(True)
        self._theme_action.triggered.connect(self._toggle_theme)
        view_menu.addAction(self._theme_action)

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
        toolbar.addAction("Auto YOLO", self._show_auto_annotate)
        toolbar.addAction("Predire", self._show_predict)
        toolbar.addAction("Stats", self._show_stats)
        toolbar.addSeparator()
        toolbar.addAction("Prec.", self._prev_image)
        toolbar.addAction("Suiv.", self._next_image)
        toolbar.addSeparator()
        toolbar.addAction("Ajuster", self._canvas.fit_image)

    def _setup_class_shortcuts(self) -> None:
        for i in range(9):
            shortcut = QShortcut(QKeySequence(str(i + 1)), self)
            shortcut.activated.connect(lambda idx=i: self._select_class(idx))

        # W = duplicate last annotation
        dup_shortcut = QShortcut(QKeySequence("W"), self)
        dup_shortcut.activated.connect(self._duplicate_last_annotation)

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
        self._canvas.cursor_moved.connect(self._on_cursor_moved)
        self._image_adjustments.values_changed.connect(self._on_adjustments_changed)
        self._label_list.visibility_changed.connect(self._on_class_visibility_changed)
        self._canvas.context_menu_requested.connect(self._show_context_menu)
        self._properties_panel.annotation_updated.connect(self._on_annotation_attr_updated)

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

    def _on_cursor_moved(self, x: float, y: float) -> None:
        self._coord_label.setText(f"x: {int(x)}  y: {int(y)}")
        self._update_zoom_label()

    def _on_class_visibility_changed(self, class_id: int, visible: bool) -> None:
        """Show/hide annotations of a specific class."""
        for item in self._scene.items():
            if isinstance(item, (BBoxItem, PolygonItem)):
                # Find the annotation's class_id
                ann_data = self._project.current_annotations()
                if ann_data:
                    for ann in ann_data.annotations:
                        if ann.uid == item.uid and ann.label_id == class_id:
                            item.setVisible(visible)
                            break

    def _on_adjustments_changed(self, brightness: int, contrast: int) -> None:
        self._scene.set_brightness_contrast(brightness, contrast)

    def _show_context_menu(self, item, global_pos) -> None:
        """Show right-click context menu on an annotation."""
        menu = QMenu(self)

        # Change class submenu
        class_menu = menu.addMenu("Changer classe")
        for label in self._project.label_manager.labels:
            action = class_menu.addAction(f"{label.name}")
            action.setData(label.class_id)

        menu.addSeparator()
        dup_action = menu.addAction("Dupliquer")
        zoom_action = menu.addAction("Zoom dessus")
        menu.addSeparator()
        del_action = menu.addAction("Supprimer")

        result = menu.exec(global_pos)
        if not result:
            return

        ann_data = self._project.current_annotations()
        if not ann_data:
            return

        if result == dup_action:
            for ann in ann_data.annotations:
                if ann.uid == item.uid:
                    data = self._make_annotation_data(ann)
                    data["uid"] = uuid.uuid4().hex[:8]
                    if "x" in data:
                        data["x"] += 20
                        data["y"] += 20
                    elif "points" in data:
                        data["points"] = [(x + 20, y + 20) for x, y in data["points"]]
                    self._add_annotation_from_data(data)
                    self._undo_stack.push(AddAnnotationAction(
                        self._add_annotation_from_data, self._remove_annotation_from_data,
                        data, "Dupliquer annotation",
                    ))
                    self._refresh_canvas()
                    break

        elif result == zoom_action:
            self._canvas.fit_to_rect(item.get_rect_in_scene())

        elif result == del_action:
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

        elif result.data() is not None:
            # Change class
            new_class_id = result.data()
            for ann in ann_data.annotations:
                if ann.uid == item.uid:
                    ann.label_id = new_class_id
                    ann_data.modified = True
                    break
            self._refresh_canvas()

    def _toggle_grid(self, checked: bool) -> None:
        self._scene.set_grid(checked)
        self._statusbar.showMessage(
            "Grille activee" if checked else "Grille desactivee", 2000
        )

    def _toggle_lock(self, checked: bool) -> None:
        self._annotations_locked = checked
        # Make all annotation items non-movable/non-selectable when locked
        for item in self._scene.items():
            if isinstance(item, (BBoxItem, PolygonItem)):
                if checked:
                    item.setFlag(BBoxItem.GraphicsItemFlag.ItemIsMovable, False)
                    item.setFlag(BBoxItem.GraphicsItemFlag.ItemIsSelectable, False)
                else:
                    item.setFlag(BBoxItem.GraphicsItemFlag.ItemIsMovable, True)
                    item.setFlag(BBoxItem.GraphicsItemFlag.ItemIsSelectable, True)
        self._statusbar.showMessage(
            "Annotations verrouillees (L)" if checked else "Annotations deverrouillees", 2000
        )

    def _update_minimap(self) -> None:
        self._minimap.update_viewport()

    def _duplicate_last_annotation(self) -> None:
        """Duplicate the last annotation on the current image (W key)."""
        ann_data = self._project.current_annotations()
        if not ann_data or not ann_data.annotations:
            return

        last = ann_data.annotations[-1]
        data = self._make_annotation_data(last)
        data["uid"] = uuid.uuid4().hex[:8]
        # Offset slightly so it's visible
        if "x" in data:
            data["x"] += 20
            data["y"] += 20
        elif "points" in data:
            data["points"] = [(x + 20, y + 20) for x, y in data["points"]]

        self._add_annotation_from_data(data)
        self._undo_stack.push(AddAnnotationAction(
            self._add_annotation_from_data, self._remove_annotation_from_data,
            data, "Dupliquer annotation",
        ))
        self._refresh_canvas()
        self._statusbar.showMessage("Annotation dupliquee (W)", 2000)

    def _rotate_view(self, angle: int) -> None:
        """Rotate the canvas view. 0 = reset."""
        if angle == 0:
            self._canvas.resetTransform()
            self._canvas.fit_image()
        else:
            self._canvas.rotate(angle)
        self._statusbar.showMessage(f"Rotation: {angle}°" if angle else "Rotation reset", 2000)

    def _select_all(self) -> None:
        """Select all annotation items on the canvas."""
        for item in self._scene.items():
            if isinstance(item, (BBoxItem, PolygonItem)):
                item.setSelected(True)
                item.set_selected_style(True)
        ann_data = self._project.current_annotations()
        count = len(ann_data.annotations) if ann_data else 0
        self._statusbar.showMessage(f"{count} annotation(s) selectionnee(s)", 2000)

    def _change_selected_class(self) -> None:
        """Change the class of selected annotations to the current active class."""
        ann_data = self._project.current_annotations()
        if not ann_data:
            return

        new_class_id = self._label_list.current_class_id()
        label = self._project.label_manager.get(new_class_id)
        if not label:
            return

        selected_uids = {
            item.uid for item in self._scene.selectedItems()
            if isinstance(item, (BBoxItem, PolygonItem))
        }
        if not selected_uids:
            self._statusbar.showMessage("Aucune annotation selectionnee", 2000)
            return

        count = 0
        for ann in ann_data.annotations:
            if ann.uid in selected_uids:
                ann.label_id = new_class_id
                ann_data.modified = True
                count += 1

        self._refresh_canvas()
        self._statusbar.showMessage(
            f"{count} annotation(s) -> classe '{label.name}'", 2000
        )

    def _zoom_to_selected(self) -> None:
        """Zoom to selected annotation (F key)."""
        selected = [
            item for item in self._scene.selectedItems()
            if isinstance(item, (BBoxItem, PolygonItem))
        ]
        if selected:
            rect = selected[0].get_rect_in_scene()
            self._canvas.fit_to_rect(rect)
        else:
            self._canvas.fit_image()

    def _on_annotation_list_selected(self, uid: str) -> None:
        for item in self._scene.items():
            if isinstance(item, (BBoxItem, PolygonItem)):
                selected = item.uid == uid
                item.set_selected_style(selected)
                item.setSelected(selected)
        # Update properties panel
        ann_data = self._project.current_annotations()
        if ann_data:
            for ann in ann_data.annotations:
                if ann.uid == uid:
                    self._properties_panel.set_annotation(ann)
                    return
        self._properties_panel.set_annotation(None)

    def _on_annotation_attr_updated(self, uid: str) -> None:
        ann_data = self._project.current_annotations()
        if ann_data:
            ann_data.modified = True

    # --- Actions ---

    def _open_directory(self) -> None:
        last_dir = self._settings.value("last_directory", "")
        directory = QFileDialog.getExistingDirectory(
            self, "Ouvrir un dossier d'images", last_dir
        )
        if directory:
            self._open_directory_path(directory)

    def _set_annotations_dir(self) -> None:
        """Let user choose a separate directory for annotation files."""
        current = self._project.get_annotations_dir()
        directory = QFileDialog.getExistingDirectory(
            self, "Dossier d'annotations",
            current if current else self._project.image_dir,
        )
        if directory:
            self._project.annotations_dir = directory
            self._settings.setValue("annotations_dir", directory)
            self._statusbar.showMessage(f"Annotations -> {directory}", 3000)

            # Reload current image annotations from new dir
            if self._project.current_image_path():
                self._load_image(self._project.current_index)

    def _save_current(self) -> None:
        ann = self._project.current_annotations()
        if ann:
            save_yolo(ann, self._project.get_annotations_dir())
            self._project.save_classes_txt()
            idx = self._project.current_index
            self._file_list.mark_annotated(idx, bool(ann.annotations))
            self._statusbar.showMessage("Sauvegarde.", 2000)

    def _save_all(self) -> None:
        for img_path, ann in self._project._annotations_cache.items():
            if ann.modified:
                save_yolo(ann, self._project.get_annotations_dir())
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
            save_yolo(ann, self._project.get_annotations_dir())
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
            item = PolygonItem(ann.polygon.points, color, name, ann.uid)
        elif ann.bbox:
            item = BBoxItem(ann.bbox.x, ann.bbox.y, ann.bbox.width, ann.bbox.height,
                            color, name, ann.uid)
        else:
            return None

        # Respect class visibility
        if not self._label_list.is_class_visible(ann.label_id):
            item.setVisible(False)
        # Respect lock state
        if self._annotations_locked:
            item.setFlag(BBoxItem.GraphicsItemFlag.ItemIsMovable, False)
            item.setFlag(BBoxItem.GraphicsItemFlag.ItemIsSelectable, False)
        return item

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
        self._minimap.set_scene(self._scene)
        self._update_minimap()

        ann_data = self._project.get_annotations(path)
        if not ann_data.annotations:
            loaded = load_yolo(path, pixmap.width(), pixmap.height(), self._project.get_annotations_dir())
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

    # --- Import ---

    def _import_voc(self) -> None:
        """Import PASCAL VOC XML annotations from the current image directory."""
        if not self._project.image_dir:
            QMessageBox.warning(self, "Erreur", "Ouvrez d'abord un dossier d'images.")
            return

        from pathlib import Path
        count = 0
        for fname in self._project.image_files:
            img_path = os.path.join(self._project.image_dir, fname)
            xml_path = str(Path(img_path).with_suffix(".xml"))
            if not os.path.isfile(xml_path):
                continue

            annotations = load_voc(xml_path, self._project.label_manager)
            if not annotations:
                continue

            ann_data = self._project.get_annotations(img_path)
            for ann in annotations:
                ann_data.add(ann)
            count += len(annotations)

            idx = self._project.image_files.index(fname)
            self._file_list.mark_annotated(idx, True)

        self._label_list.set_label_manager(self._project.label_manager)
        self._refresh_canvas()
        self._statusbar.showMessage(f"Import VOC: {count} annotations importees", 3000)

    def _import_coco(self) -> None:
        """Import annotations from a COCO JSON file."""
        if not self._project.image_dir:
            QMessageBox.warning(self, "Erreur", "Ouvrez d'abord un dossier d'images.")
            return

        json_path, _ = QFileDialog.getOpenFileName(
            self, "Importer COCO JSON",
            self._project.image_dir,
            "JSON (*.json)",
        )
        if not json_path:
            return

        result = load_coco(json_path, self._project.image_dir, self._project.label_manager)
        count = 0
        for fname, annotations in result.items():
            img_path = os.path.join(self._project.image_dir, fname)
            if not os.path.isfile(img_path):
                continue

            ann_data = self._project.get_annotations(img_path)
            for ann in annotations:
                ann_data.add(ann)
            count += len(annotations)

            try:
                idx = self._project.image_files.index(fname)
                self._file_list.mark_annotated(idx, True)
            except ValueError:
                pass

        self._label_list.set_label_manager(self._project.label_manager)
        self._refresh_canvas()
        self._statusbar.showMessage(f"Import COCO: {count} annotations importees", 3000)

    # --- Auto-annotation ---

    def _show_auto_annotate(self) -> None:
        from src.utils.auto_annotate import check_ultralytics
        if not check_ultralytics():
            reply = QMessageBox.question(
                self, "ultralytics manquant",
                "Le package 'ultralytics' n'est pas installe.\n"
                "Voulez-vous l'installer maintenant ?\n\n"
                "pip install ultralytics",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                import subprocess, sys
                self._statusbar.showMessage("Installation de ultralytics en cours...", 0)
                QApplication.processEvents()
                try:
                    subprocess.check_call([sys.executable, "-m", "pip", "install", "ultralytics"])
                    self._statusbar.showMessage("ultralytics installe.", 3000)
                except subprocess.CalledProcessError:
                    QMessageBox.critical(self, "Erreur", "Echec de l'installation.")
                    return
            else:
                return

        last_model = self._settings.value("last_yolo_model", "yolov8n.pt")
        dialog = AutoAnnotateDialog(self, last_model)
        dialog.run_requested.connect(self._run_auto_annotate)
        dialog.exec()

    def _run_auto_annotate(self, model_path: str, confidence: float,
                           use_seg: bool, all_images: bool) -> None:
        from src.utils.auto_annotate import load_yolo_model, predict_image, detections_to_annotations

        self._settings.setValue("last_yolo_model", model_path)

        dialog = self.sender().parent() if self.sender() else None

        try:
            if dialog:
                dialog.set_status("Chargement du modele...")
            QApplication.processEvents()
            model = load_yolo_model(model_path)
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Impossible de charger le modele:\n{e}")
            return

        if all_images:
            paths = [
                os.path.join(self._project.image_dir, f)
                for f in self._project.image_files
            ]
        else:
            path = self._project.current_image_path()
            paths = [path] if path else []

        total = len(paths)
        added_total = 0

        for i, img_path in enumerate(paths):
            if dialog:
                dialog.set_progress(i + 1, total)
                dialog.set_status(f"Analyse: {os.path.basename(img_path)} ({i+1}/{total})")
            QApplication.processEvents()

            try:
                detections = predict_image(model, img_path, confidence, use_seg)
            except Exception:
                continue

            if not detections:
                continue

            annotations = detections_to_annotations(detections, self._project.label_manager)
            ann_data = self._project.get_annotations(img_path)

            for ann in annotations:
                ann_data.add(ann)
                added_total += 1

            # Mark as annotated in file list
            try:
                idx = self._project.image_files.index(os.path.basename(img_path))
                self._file_list.mark_annotated(idx, True)
            except ValueError:
                pass

        # Refresh UI
        self._label_list.set_label_manager(self._project.label_manager)
        self._refresh_canvas()

        if dialog:
            dialog.set_status(f"Termine: {added_total} annotations ajoutees sur {total} image(s)")

        self._statusbar.showMessage(
            f"Pre-annotation: {added_total} annotations ajoutees", 3000
        )

    # --- Statistics ---

    def _show_stats(self) -> None:
        # Make sure current annotations are loaded
        self._auto_save()

        # Load annotations for all images that have YOLO files
        for fname in self._project.image_files:
            img_path = os.path.join(self._project.image_dir, fname)
            if img_path not in self._project._annotations_cache:
                if has_yolo_annotations(img_path, self._project.get_annotations_dir()):
                    from PySide6.QtGui import QImage
                    img = QImage(img_path)
                    ann_data = self._project.get_annotations(img_path)
                    if not ann_data.annotations:
                        loaded = load_yolo(img_path, img.width(), img.height(), self._project.get_annotations_dir())
                        for a in loaded:
                            ann_data.add(a)
                        ann_data.modified = False

        dialog = StatsDialog(
            self._project._annotations_cache,
            self._project.label_manager,
            self._project.total_images(),
            self,
        )
        dialog.exec()

    # --- Predict from previous ---

    def _show_predict(self) -> None:
        if not self._project.image_dir or not self._project.image_files:
            QMessageBox.warning(self, "Erreur", "Ouvrez d'abord un dossier d'images.")
            return

        has_prev = self._project.current_index > 0
        dialog = PredictDialog(has_previous=has_prev, parent=self)
        dialog.propagate_requested.connect(lambda: self._propagate_annotations(dialog))
        dialog.template_match_requested.connect(
            lambda conf, max_src, multi: self._template_match_annotations(dialog, conf, max_src, multi)
        )
        dialog.exec()

    def _propagate_annotations(self, dialog: PredictDialog) -> None:
        from src.utils.predict import propagate_from_previous

        idx = self._project.current_index
        if idx <= 0:
            dialog.set_status("Pas d'image precedente.")
            return

        prev_path = os.path.join(self._project.image_dir, self._project.image_files[idx - 1])
        prev_ann = self._project.get_annotations(prev_path)

        # Load from disk if not in cache
        if not prev_ann.annotations:
            from PySide6.QtGui import QImage
            img = QImage(prev_path)
            loaded = load_yolo(prev_path, img.width(), img.height(), self._project.get_annotations_dir())
            for a in loaded:
                prev_ann.add(a)
            prev_ann.modified = False

        if not prev_ann.annotations:
            dialog.set_status("Aucune annotation sur l'image precedente.")
            return

        ann_data = self._project.current_annotations()
        if not ann_data:
            return

        new_anns = propagate_from_previous(prev_ann, ann_data.image_width, ann_data.image_height)
        for ann in new_anns:
            ann_data.add(ann)

        self._refresh_canvas()
        dialog.set_status(f"{len(new_anns)} annotation(s) propagee(s) depuis l'image precedente.")
        self._statusbar.showMessage(f"Propagation: {len(new_anns)} annotations", 3000)

    def _template_match_annotations(self, dialog: PredictDialog,
                                     confidence: float, max_sources: int,
                                     multi_scale: bool) -> None:
        from src.utils.predict import predict_by_template_matching, check_opencv

        if not check_opencv():
            reply = QMessageBox.question(
                self, "OpenCV manquant",
                "Le package 'opencv-python' est necessaire.\nInstaller maintenant ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                import subprocess, sys
                dialog.set_status("Installation de opencv-python...")
                QApplication.processEvents()
                try:
                    subprocess.check_call([sys.executable, "-m", "pip", "install", "opencv-python"])
                    dialog.set_status("opencv-python installe.")
                except subprocess.CalledProcessError:
                    QMessageBox.critical(self, "Erreur", "Echec de l'installation.")
                    return
            else:
                return

        target_path = self._project.current_image_path()
        if not target_path:
            return

        ann_data = self._project.current_annotations()
        if not ann_data:
            return

        dialog.set_status("Chargement des annotations sources...")
        QApplication.processEvents()

        # Collect annotated source images (before current)
        sources: list[tuple[str, ImageAnnotations]] = []
        idx = self._project.current_index
        for i in range(max(0, idx - max_sources), idx):
            src_path = os.path.join(self._project.image_dir, self._project.image_files[i])
            src_ann = self._project.get_annotations(src_path)
            if not src_ann.annotations:
                from PySide6.QtGui import QImage
                img = QImage(src_path)
                loaded = load_yolo(src_path, img.width(), img.height(), self._project.get_annotations_dir())
                for a in loaded:
                    src_ann.add(a)
                src_ann.modified = False
            if src_ann.annotations:
                sources.append((src_path, src_ann))

        if not sources:
            dialog.set_status("Aucune image annotee precedente trouvee.")
            return

        dialog.set_status(f"Template matching sur {len(sources)} image(s) source...")
        dialog.set_progress(0, 1)
        QApplication.processEvents()

        scales = [0.8, 0.9, 1.0, 1.1, 1.2] if multi_scale else [1.0]

        results = predict_by_template_matching(
            sources, target_path,
            ann_data.image_width, ann_data.image_height,
            confidence_threshold=confidence,
            max_sources=max_sources,
            scales=scales,
        )

        for r in results:
            ann_data.add(r.annotation)

        self._refresh_canvas()
        dialog.set_progress(1, 1)

        if results:
            confs = [f"{r.confidence:.0%}" for r in results]
            dialog.set_status(
                f"{len(results)} annotation(s) predite(s) "
                f"(confiances: {', '.join(confs)})"
            )
        else:
            dialog.set_status("Aucune correspondance trouvee. Essayez de baisser le seuil.")

        self._statusbar.showMessage(f"Prediction: {len(results)} annotations", 3000)

    # --- Review mode ---

    def _toggle_review_mode(self, checked: bool) -> None:
        self._review_mode = checked
        if checked:
            self._statusbar.showMessage(
                "MODE REVUE: Y=valider & suivant | N=rejeter (suppr) & suivant | A/D=naviguer", 0
            )
            # Add review shortcuts
            self._review_shortcut_y = QShortcut(QKeySequence("Y"), self)
            self._review_shortcut_y.activated.connect(self._review_accept)
            self._review_shortcut_n = QShortcut(QKeySequence("N"), self)
            self._review_shortcut_n.activated.connect(self._review_reject)
        else:
            self._statusbar.showMessage("Mode revue desactive", 2000)
            if hasattr(self, "_review_shortcut_y"):
                self._review_shortcut_y.setEnabled(False)
                self._review_shortcut_n.setEnabled(False)

    def _review_accept(self) -> None:
        """Accept current image annotations and move to next."""
        self._save_current()
        self._next_image()

    def _review_reject(self) -> None:
        """Clear current annotations and move to next."""
        ann_data = self._project.current_annotations()
        if ann_data:
            ann_data.clear()
            self._refresh_canvas()
            self._save_current()
        self._next_image()

    # --- Shortcuts dialog ---

    def _show_shortcuts(self) -> None:
        dialog = ShortcutsDialog(self._settings, self)
        dialog.exec()

    # --- Theme ---

    def _toggle_theme(self, checked: bool) -> None:
        self._dark_theme = not checked
        app = QApplication.instance()
        if app:
            app.setStyleSheet(LIGHT_THEME if checked else DARK_THEME)
        self._settings.setValue("light_theme", checked)
        self._canvas.setBackgroundBrush(
            QColor(240, 240, 240) if checked else QColor(40, 40, 40)
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

    def _export_crops(self) -> None:
        """Export annotated regions as cropped images."""
        self._save_all()
        if not self._project.image_dir:
            return

        output_dir = QFileDialog.getExistingDirectory(
            self, "Dossier de destination pour les crops",
            os.path.join(self._project.image_dir, "crops"),
        )
        if not output_dir:
            return

        from src.utils.crop_export import export_crops
        count = export_crops(
            self._project._annotations_cache,
            self._project.label_manager,
            output_dir,
        )
        self._statusbar.showMessage(f"Export crops: {count} images exportees dans {output_dir}", 3000)

    def _export_split(self) -> None:
        """Export YOLO dataset with train/val/test split."""
        self._save_all()
        if not self._project.image_dir:
            return

        default_dir = os.path.join(self._project.image_dir, "dataset")
        dialog = SplitDialog(default_dir, self)

        def do_export(output_dir, train, val, test, shuffle):
            from src.utils.dataset_split import export_yolo_split

            # Load all annotations first
            for fname in self._project.image_files:
                img_path = os.path.join(self._project.image_dir, fname)
                if img_path not in self._project._annotations_cache:
                    if has_yolo_annotations(img_path, self._project.get_annotations_dir()):
                        from PySide6.QtGui import QImage
                        img = QImage(img_path)
                        ann_data = self._project.get_annotations(img_path)
                        if not ann_data.annotations:
                            loaded = load_yolo(img_path, img.width(), img.height(), self._project.get_annotations_dir())
                            for a in loaded:
                                ann_data.add(a)
                            ann_data.modified = False

            counts = export_yolo_split(
                self._project.image_dir,
                self._project.image_files,
                self._project._annotations_cache,
                self._project.label_manager,
                output_dir, train, val, test, shuffle,
            )
            self._statusbar.showMessage(
                f"Export split: train={counts['train']}, val={counts['val']}, test={counts['test']}", 5000
            )

        dialog.export_requested.connect(do_export)
        dialog.exec()

    # --- Drag & Drop ---

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        urls = event.mimeData().urls()
        if not urls:
            return
        path = urls[0].toLocalFile()
        if os.path.isdir(path):
            self._open_directory_path(path)
        elif os.path.isfile(path):
            parent = os.path.dirname(path)
            self._open_directory_path(parent)

    def _open_directory_path(self, directory: str) -> None:
        """Open directory programmatically (used by drag&drop and recent)."""
        self._settings.setValue("last_directory", directory)
        self._add_recent(directory)
        ann_dir = self._settings.value("annotations_dir", "")
        self._project.open_directory(directory, ann_dir)

        # Update window title
        title = f"LabelImage — {directory}"
        if ann_dir and ann_dir != directory:
            title += f"  [annotations: {ann_dir}]"
        self.setWindowTitle(title)

        self._file_list.set_files(self._project.image_files)
        self._label_list.set_label_manager(self._project.label_manager)
        self._undo_stack.clear()

        if not self._project.label_manager.labels:
            self._label_list._on_add()

        for i, fname in enumerate(self._project.image_files):
            img_path = os.path.join(directory, fname)
            self._file_list.mark_annotated(i, has_yolo_annotations(img_path, self._project.get_annotations_dir()))

        if self._project.image_files:
            self._load_image(0)

    # --- Recent files ---

    def _add_recent(self, directory: str) -> None:
        recents = self._settings.value("recent_dirs", [], type=list)
        if directory in recents:
            recents.remove(directory)
        recents.insert(0, directory)
        recents = recents[:10]
        self._settings.setValue("recent_dirs", recents)
        self._update_recent_menu()

    def _update_recent_menu(self) -> None:
        self._recent_menu.clear()
        recents = self._settings.value("recent_dirs", [], type=list)
        if not recents:
            self._recent_menu.setEnabled(False)
            return
        self._recent_menu.setEnabled(True)
        for path in recents:
            action = self._recent_menu.addAction(path)
            action.triggered.connect(lambda checked, p=path: self._open_directory_path(p))

    # --- About ---

    def _show_about(self) -> None:
        QMessageBox.about(
            self, "A propos de LabelImage",
            "<h2>LabelImage</h2>"
            "<p>Outil d'annotation d'images cross-platform</p>"
            "<p>Version 1.0.0</p>"
            "<hr>"
            "<p><b>Fonctionnalites:</b></p>"
            "<ul>"
            "<li>Bounding boxes et polygones</li>"
            "<li>Export YOLO, PASCAL VOC, COCO</li>"
            "<li>Pre-annotation YOLO et prediction par template matching</li>"
            "<li>Mode revue, statistiques, crops export</li>"
            "</ul>"
            "<p>Construit avec Python + PySide6</p>"
        )

    # --- Auto-backup ---

    def _auto_backup(self) -> None:
        """Auto-save all modified annotations (called by timer)."""
        if not self._project.image_dir:
            return
        saved = 0
        for img_path, ann in self._project._annotations_cache.items():
            if ann.modified:
                save_yolo(ann, self._project.get_annotations_dir())
                saved += 1
        if saved:
            self._project.save_classes_txt()

    # --- Zoom tracking ---

    def _update_zoom_label(self) -> None:
        transform = self._canvas.transform()
        zoom_pct = int(transform.m11() * 100)
        self._zoom_label.setText(f"{zoom_pct}%")

    # --- Polygon <-> BBox conversion ---

    def _convert_selected_to_bbox(self) -> None:
        ann_data = self._project.current_annotations()
        if not ann_data:
            return
        count = 0
        for item in self._scene.selectedItems():
            if isinstance(item, PolygonItem):
                for ann in ann_data.annotations:
                    if ann.uid == item.uid and ann.polygon:
                        x, y, w, h = ann.polygon.bounding_rect()
                        ann.ann_type = AnnotationType.BBOX
                        ann.bbox = BoundingBox(x=x, y=y, width=w, height=h)
                        ann.polygon = None
                        ann_data.modified = True
                        count += 1
                        break
        if count:
            self._refresh_canvas()
            self._statusbar.showMessage(f"{count} polygone(s) converti(s) en bbox", 2000)

    def _convert_selected_to_polygon(self) -> None:
        ann_data = self._project.current_annotations()
        if not ann_data:
            return
        count = 0
        for item in self._scene.selectedItems():
            if isinstance(item, BBoxItem):
                for ann in ann_data.annotations:
                    if ann.uid == item.uid and ann.bbox:
                        b = ann.bbox
                        points = [
                            (b.x, b.y), (b.x + b.width, b.y),
                            (b.x + b.width, b.y + b.height), (b.x, b.y + b.height),
                        ]
                        ann.ann_type = AnnotationType.POLYGON
                        ann.polygon = Polygon(points=points)
                        ann.bbox = None
                        ann_data.modified = True
                        count += 1
                        break
        if count:
            self._refresh_canvas()
            self._statusbar.showMessage(f"{count} bbox converti(s) en polygone", 2000)

    # --- State ---

    def _restore_state(self) -> None:
        geometry = self._settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        state = self._settings.value("windowState")
        if state:
            self.restoreState(state)
        light = self._settings.value("light_theme", False, type=bool)
        if light:
            self._theme_action.setChecked(True)
            self._toggle_theme(True)

    def _has_unsaved_changes(self) -> bool:
        for ann in self._project._annotations_cache.values():
            if ann.modified:
                return True
        return False

    def closeEvent(self, event) -> None:
        if self._has_unsaved_changes():
            reply = QMessageBox.question(
                self, "Modifications non sauvegardees",
                "Des annotations n'ont pas ete sauvegardees.\nSauvegarder avant de quitter ?",
                QMessageBox.StandardButton.Save |
                QMessageBox.StandardButton.Discard |
                QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Save:
                self._save_all()
            elif reply == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
        self._auto_save()
        self._settings.setValue("geometry", self.saveGeometry())
        self._settings.setValue("windowState", self.saveState())
        super().closeEvent(event)
