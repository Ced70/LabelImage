from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QRectF, QPointF
from PySide6.QtGui import QPixmap, QColor, QPainter, QWheelEvent, QMouseEvent, QKeyEvent
from PySide6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QGraphicsItem,
)

from src.canvas.items import BBoxItem
from src.models.annotation import Annotation, BoundingBox


class AnnotationScene(QGraphicsScene):
    """Scene that holds the image and all annotation items."""

    annotation_added = Signal(object)        # Annotation
    annotation_changed = Signal(object, object)  # BBoxItem, old_rect (dict or None)
    annotation_selected = Signal(str)        # uid or ""

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


class CanvasView(QGraphicsView):
    """Main canvas view with zoom, pan, and bbox drawing."""

    bbox_drawn = Signal(float, float, float, float)  # x, y, w, h in scene coords
    delete_requested = Signal()  # user pressed Delete on canvas

    def __init__(self, scene: AnnotationScene, parent=None):
        super().__init__(scene, parent)
        self._scene = scene
        self._drawing = False
        self._draw_enabled = True
        self._draw_start: QPointF | None = None
        self._temp_rect: BBoxItem | None = None
        self._panning = False
        self._pan_start: QPointF | None = None
        self._zoom_factor = 1.15

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

        # Left button: draw or select
        if event.button() == Qt.MouseButton.LeftButton:
            scene_pos = self.mapToScene(event.position().toPoint())
            # Check if clicking on existing item
            item = self._scene.itemAt(scene_pos, self.transform())
            if item and isinstance(item, BBoxItem):
                super().mousePressEvent(event)
                return

            if self._draw_enabled:
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
                # Only emit if rect is big enough (avoid accidental clicks)
                if rect.width() > 5 and rect.height() > 5:
                    self.bbox_drawn.emit(rect.x(), rect.y(), rect.width(), rect.height())
            self._draw_start = None
            event.accept()
            return

        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.delete_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)
