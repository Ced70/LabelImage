from __future__ import annotations

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPen, QBrush, QColor, QPainter, QPolygonF
from PySide6.QtWidgets import (
    QGraphicsRectItem, QGraphicsPolygonItem, QGraphicsItem,
    QGraphicsSceneMouseEvent, QGraphicsEllipseItem,
)

HANDLE_SIZE = 8


class BBoxItem(QGraphicsRectItem):
    """Interactive bounding box item on the canvas."""

    def __init__(self, x: float, y: float, w: float, h: float,
                 color: QColor, label_text: str = "", uid: str = ""):
        super().__init__(x, y, w, h)
        self.uid = uid
        self.label_text = label_text
        self._color = color
        self._selected = False
        self._resizing = False
        self._resize_handle: str | None = None
        self._drag_start: QPointF | None = None
        self._rect_before_edit: dict | None = None  # for undo tracking

        pen = QPen(color, 2)
        pen.setCosmetic(True)  # constant width regardless of zoom
        self.setPen(pen)

        fill = QColor(color)
        fill.setAlpha(30)
        self.setBrush(QBrush(fill))

        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)

    def set_selected_style(self, selected: bool) -> None:
        self._selected = selected
        pen = QPen(self._color, 3 if selected else 2)
        pen.setCosmetic(True)
        if selected:
            pen.setStyle(Qt.PenStyle.DashLine)
        self.setPen(pen)
        self.update()

    def paint(self, painter: QPainter, option, widget=None):
        super().paint(painter, option, widget)
        # Draw label text
        if self.label_text:
            r = self.rect()
            painter.setPen(Qt.GlobalColor.white)
            font = painter.font()
            font.setPointSize(10)
            painter.setFont(font)
            text_rect = painter.fontMetrics().boundingRect(self.label_text)
            bg_rect = QRectF(
                r.x(), r.y() - text_rect.height() - 4,
                text_rect.width() + 8, text_rect.height() + 4
            )
            painter.fillRect(bg_rect, QBrush(self._color))
            painter.drawText(bg_rect, Qt.AlignmentFlag.AlignCenter, self.label_text)

        # Draw resize handles when selected
        if self._selected:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(Qt.GlobalColor.white))
            for handle_rect in self._handle_rects().values():
                painter.drawRect(handle_rect)

    def _handle_rects(self) -> dict[str, QRectF]:
        r = self.rect()
        hs = HANDLE_SIZE
        return {
            "tl": QRectF(r.left() - hs / 2, r.top() - hs / 2, hs, hs),
            "tr": QRectF(r.right() - hs / 2, r.top() - hs / 2, hs, hs),
            "bl": QRectF(r.left() - hs / 2, r.bottom() - hs / 2, hs, hs),
            "br": QRectF(r.right() - hs / 2, r.bottom() - hs / 2, hs, hs),
        }

    def _handle_at(self, pos: QPointF) -> str | None:
        for name, rect in self._handle_rects().items():
            if rect.contains(pos):
                return name
        return None

    def hoverMoveEvent(self, event: QGraphicsSceneMouseEvent):
        if self._selected and self._handle_at(event.pos()):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        else:
            self.setCursor(Qt.CursorShape.SizeAllCursor)
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            # Save rect before any edit for undo
            r = self.get_rect_in_scene()
            self._rect_before_edit = {
                "x": r.x(), "y": r.y(), "w": r.width(), "h": r.height()
            }
            if self._selected:
                handle = self._handle_at(event.pos())
                if handle:
                    self._resizing = True
                    self._resize_handle = handle
                    self._drag_start = event.pos()
                    event.accept()
                    return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
        if self._resizing and self._resize_handle and self._drag_start:
            r = self.rect()
            pos = event.pos()
            if self._resize_handle == "tl":
                r.setTopLeft(pos)
            elif self._resize_handle == "tr":
                r.setTopRight(pos)
            elif self._resize_handle == "bl":
                r.setBottomLeft(pos)
            elif self._resize_handle == "br":
                r.setBottomRight(pos)
            self.setRect(r.normalized())
            self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)
        # Show snap guides while dragging
        scene = self.scene()
        if scene and hasattr(scene, "show_snap_guides"):
            scene.show_snap_guides(self)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        old_rect = self._rect_before_edit
        self._rect_before_edit = None
        if self._resizing:
            self._resizing = False
            self._resize_handle = None
            self._drag_start = None
            scene = self.scene()
            if scene and hasattr(scene, "bbox_changed"):
                scene.bbox_changed(self, old_rect)
            event.accept()
            return
        super().mouseReleaseEvent(event)
        scene = self.scene()
        if scene and hasattr(scene, "bbox_changed"):
            scene.bbox_changed(self, old_rect)

    def get_rect_in_scene(self) -> QRectF:
        """Get the bounding box rect in scene coordinates."""
        return self.mapRectToScene(self.rect())


VERTEX_RADIUS = 5


class PolygonItem(QGraphicsPolygonItem):
    """Interactive polygon item on the canvas."""

    def __init__(self, points: list[tuple[float, float]], color: QColor,
                 label_text: str = "", uid: str = ""):
        polygon = QPolygonF([QPointF(x, y) for x, y in points])
        super().__init__(polygon)
        self.uid = uid
        self.label_text = label_text
        self._color = color
        self._selected = False
        self._dragging_vertex: int | None = None
        self._points_before_edit: list[tuple[float, float]] | None = None

        pen = QPen(color, 2)
        pen.setCosmetic(True)
        self.setPen(pen)

        fill = QColor(color)
        fill.setAlpha(30)
        self.setBrush(QBrush(fill))

        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)

    def get_points(self) -> list[tuple[float, float]]:
        """Get polygon points in scene coordinates."""
        result = []
        poly = self.polygon()
        for i in range(poly.count()):
            sp = self.mapToScene(poly.at(i))
            result.append((sp.x(), sp.y()))
        return result

    def set_selected_style(self, selected: bool) -> None:
        self._selected = selected
        pen = QPen(self._color, 3 if selected else 2)
        pen.setCosmetic(True)
        if selected:
            pen.setStyle(Qt.PenStyle.DashLine)
        self.setPen(pen)
        self.update()

    def paint(self, painter: QPainter, option, widget=None):
        super().paint(painter, option, widget)
        poly = self.polygon()

        # Draw label text at top of bounding rect
        if self.label_text:
            br = poly.boundingRect()
            painter.setPen(Qt.GlobalColor.white)
            font = painter.font()
            font.setPointSize(10)
            painter.setFont(font)
            text_rect = painter.fontMetrics().boundingRect(self.label_text)
            bg_rect = QRectF(
                br.x(), br.y() - text_rect.height() - 4,
                text_rect.width() + 8, text_rect.height() + 4
            )
            painter.fillRect(bg_rect, QBrush(self._color))
            painter.drawText(bg_rect, Qt.AlignmentFlag.AlignCenter, self.label_text)

        # Draw vertex handles when selected
        if self._selected:
            painter.setPen(QPen(Qt.GlobalColor.white, 1))
            painter.setBrush(QBrush(self._color))
            for i in range(poly.count()):
                pt = poly.at(i)
                painter.drawEllipse(pt, VERTEX_RADIUS, VERTEX_RADIUS)

    def _vertex_at(self, pos: QPointF) -> int | None:
        poly = self.polygon()
        for i in range(poly.count()):
            pt = poly.at(i)
            if (pos - pt).manhattanLength() < VERTEX_RADIUS * 2:
                return i
        return None

    def hoverMoveEvent(self, event: QGraphicsSceneMouseEvent):
        if self._selected and self._vertex_at(event.pos()) is not None:
            self.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.setCursor(Qt.CursorShape.SizeAllCursor)
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            # Save state for undo
            self._points_before_edit = self.get_points()
            if self._selected:
                vertex = self._vertex_at(event.pos())
                if vertex is not None:
                    self._dragging_vertex = vertex
                    event.accept()
                    return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent):
        if self._dragging_vertex is not None:
            poly = self.polygon()
            poly.replace(self._dragging_vertex, event.pos())
            self.setPolygon(poly)
            self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent):
        old_points = self._points_before_edit
        self._points_before_edit = None
        if self._dragging_vertex is not None:
            self._dragging_vertex = None
            scene = self.scene()
            if scene and hasattr(scene, "polygon_changed"):
                scene.polygon_changed(self, old_points)
            event.accept()
            return
        super().mouseReleaseEvent(event)
        scene = self.scene()
        if scene and hasattr(scene, "polygon_changed"):
            scene.polygon_changed(self, old_points)

    def get_rect_in_scene(self) -> QRectF:
        """Get bounding rect in scene coordinates."""
        return self.mapRectToScene(self.polygon().boundingRect())
