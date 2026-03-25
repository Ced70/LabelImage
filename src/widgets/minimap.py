from __future__ import annotations

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene


class MiniMapWidget(QGraphicsView):
    """Small overview widget showing the full image with viewport indicator."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(200, 150)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet("border: 1px solid #555; background-color: #1e1e1e;")
        self._main_view: QGraphicsView | None = None
        self._viewport_rect = QRectF()

    def set_scene(self, scene: QGraphicsScene) -> None:
        self.setScene(scene)
        self.fitInView(scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def set_main_view(self, view: QGraphicsView) -> None:
        self._main_view = view

    def update_viewport(self) -> None:
        if not self._main_view or not self.scene():
            return
        # Get the visible area of the main view in scene coords
        visible = self._main_view.mapToScene(self._main_view.viewport().rect()).boundingRect()
        self._viewport_rect = visible
        self.fitInView(self.scene().sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self.viewport().update()

    def drawForeground(self, painter: QPainter, rect: QRectF) -> None:
        super().drawForeground(painter, rect)
        if not self._viewport_rect.isNull():
            pen = QPen(QColor(0, 120, 215), 2)
            pen.setCosmetic(True)
            painter.setPen(pen)
            fill = QColor(0, 120, 215, 30)
            painter.setBrush(QBrush(fill))
            painter.drawRect(self._viewport_rect)

    def mousePressEvent(self, event):
        """Click on minimap to navigate."""
        if self._main_view and event.button() == Qt.MouseButton.LeftButton:
            scene_pos = self.mapToScene(event.position().toPoint())
            self._main_view.centerOn(scene_pos)
            self.update_viewport()
        super().mousePressEvent(event)
