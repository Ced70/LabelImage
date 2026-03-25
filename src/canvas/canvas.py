from __future__ import annotations

from enum import Enum

from PySide6.QtCore import Qt, Signal, QRectF, QPointF
from PySide6.QtGui import (
    QPixmap, QColor, QPainter, QWheelEvent, QMouseEvent, QKeyEvent,
    QPen, QPolygonF,
)
from PySide6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QGraphicsItem,
    QGraphicsLineItem,
)

from src.canvas.items import BBoxItem, PolygonItem


class DrawMode(Enum):
    BBOX = "bbox"
    POLYGON = "polygon"


class AnnotationScene(QGraphicsScene):
    """Scene that holds the image and all annotation items."""

    annotation_added = Signal(object)            # Annotation
    annotation_changed = Signal(object, object)  # item, old_data (dict or None)
    annotation_selected = Signal(str)            # uid or ""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap_item: QGraphicsPixmapItem | None = None

    def set_image(self, pixmap: QPixmap) -> None:
        self.clear()
        self._pixmap_item = self.addPixmap(pixmap)
        self._pixmap_item.setZValue(-1)
        self.setSceneRect(QRectF(pixmap.rect()))

    def bbox_changed(self, item: BBoxItem, old_rect: dict | None = None) -> None:
        self.annotation_changed.emit(item, old_rect)

    def polygon_changed(self, item: PolygonItem, old_points: list | None = None) -> None:
        self.annotation_changed.emit(item, old_points)


class CanvasView(QGraphicsView):
    """Main canvas view with zoom, pan, bbox and polygon drawing."""

    bbox_drawn = Signal(float, float, float, float)  # x, y, w, h
    polygon_drawn = Signal(object)  # list of (x, y) tuples
    delete_requested = Signal()
    mode_changed = Signal(str)  # "bbox" or "polygon"

    def __init__(self, scene: AnnotationScene, parent=None):
        super().__init__(scene, parent)
        self._scene = scene
        self._draw_mode = DrawMode.BBOX
        self._drawing = False
        self._draw_enabled = True
        self._draw_start: QPointF | None = None
        self._temp_rect: BBoxItem | None = None
        self._panning = False
        self._pan_start: QPointF | None = None
        self._zoom_factor = 1.15

        # Polygon drawing state
        self._poly_points: list[QPointF] = []
        self._poly_lines: list[QGraphicsLineItem] = []
        self._poly_preview_line: QGraphicsLineItem | None = None

        self.setRenderHints(
            QPainter.RenderHint.Antialiasing |
            QPainter.RenderHint.SmoothPixmapTransform
        )
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setBackgroundBrush(QColor(40, 40, 40))
        self.setMouseTracking(True)

    @property
    def draw_mode(self) -> DrawMode:
        return self._draw_mode

    def set_draw_mode(self, mode: DrawMode) -> None:
        self._cancel_polygon_drawing()
        self._draw_mode = mode
        self.mode_changed.emit(mode.value)

    def set_draw_enabled(self, enabled: bool) -> None:
        self._draw_enabled = enabled

    def fit_image(self) -> None:
        self.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.angleDelta().y() > 0:
            self.scale(self._zoom_factor, self._zoom_factor)
        else:
            self.scale(1 / self._zoom_factor, 1 / self._zoom_factor)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        # Middle button: pan
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = True
            self._pan_start = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return

        # Left button
        if event.button() == Qt.MouseButton.LeftButton:
            scene_pos = self.mapToScene(event.position().toPoint())

            # Check if clicking on existing item (not during polygon drawing)
            if not self._poly_points:
                item = self._scene.itemAt(scene_pos, self.transform())
                if item and isinstance(item, (BBoxItem, PolygonItem)):
                    super().mousePressEvent(event)
                    return

            if not self._draw_enabled:
                super().mousePressEvent(event)
                return

            if self._draw_mode == DrawMode.BBOX:
                self._drawing = True
                self._draw_start = scene_pos
                self._temp_rect = BBoxItem(
                    scene_pos.x(), scene_pos.y(), 0, 0,
                    QColor(100, 100, 100), "", ""
                )
                self._temp_rect.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
                self._temp_rect.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
                self._scene.addItem(self._temp_rect)
                event.accept()
                return

            elif self._draw_mode == DrawMode.POLYGON:
                self._add_polygon_point(scene_pos)
                event.accept()
                return

        # Right button: finish polygon
        if event.button() == Qt.MouseButton.RightButton:
            if self._poly_points and len(self._poly_points) >= 3:
                self._finish_polygon()
                event.accept()
                return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._panning and self._pan_start is not None:
            delta = event.position() - self._pan_start
            self._pan_start = event.position()
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - int(delta.x())
            )
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - int(delta.y())
            )
            event.accept()
            return

        if self._drawing and self._draw_start and self._temp_rect:
            scene_pos = self.mapToScene(event.position().toPoint())
            x = min(self._draw_start.x(), scene_pos.x())
            y = min(self._draw_start.y(), scene_pos.y())
            w = abs(scene_pos.x() - self._draw_start.x())
            h = abs(scene_pos.y() - self._draw_start.y())
            self._temp_rect.setRect(x, y, w, h)
            event.accept()
            return

        # Preview line for polygon drawing
        if self._poly_points:
            scene_pos = self.mapToScene(event.position().toPoint())
            if self._poly_preview_line:
                self._scene.removeItem(self._poly_preview_line)
            pen = QPen(QColor(200, 200, 200), 1, Qt.PenStyle.DashLine)
            pen.setCosmetic(True)
            last = self._poly_points[-1]
            self._poly_preview_line = self._scene.addLine(
                last.x(), last.y(), scene_pos.x(), scene_pos.y(), pen
            )

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = False
            self._pan_start = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton and self._drawing:
            self._drawing = False
            if self._temp_rect:
                rect = self._temp_rect.rect()
                self._scene.removeItem(self._temp_rect)
                self._temp_rect = None
                if rect.width() > 5 and rect.height() > 5:
                    self.bbox_drawn.emit(rect.x(), rect.y(), rect.width(), rect.height())
            self._draw_start = None
            event.accept()
            return

        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        # Double-click finishes polygon (alternative to right-click)
        if event.button() == Qt.MouseButton.LeftButton and self._poly_points:
            if len(self._poly_points) >= 3:
                self._finish_polygon()
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.delete_requested.emit()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape:
            self._cancel_polygon_drawing()
            event.accept()
            return
        super().keyPressEvent(event)

    # --- Polygon drawing helpers ---

    def _add_polygon_point(self, pos: QPointF) -> None:
        if self._poly_points:
            last = self._poly_points[-1]
            pen = QPen(QColor(0, 255, 0), 2)
            pen.setCosmetic(True)
            line = self._scene.addLine(last.x(), last.y(), pos.x(), pos.y(), pen)
            self._poly_lines.append(line)
        self._poly_points.append(pos)

    def _finish_polygon(self) -> None:
        points = [(p.x(), p.y()) for p in self._poly_points]
        self._cleanup_polygon_temp()
        self.polygon_drawn.emit(points)

    def _cancel_polygon_drawing(self) -> None:
        self._cleanup_polygon_temp()

    def _cleanup_polygon_temp(self) -> None:
        for line in self._poly_lines:
            self._scene.removeItem(line)
        self._poly_lines.clear()
        if self._poly_preview_line:
            self._scene.removeItem(self._poly_preview_line)
            self._poly_preview_line = None
        self._poly_points.clear()
