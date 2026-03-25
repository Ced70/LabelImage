from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import uuid


class AnnotationType(Enum):
    BBOX = "bbox"
    POLYGON = "polygon"


@dataclass
class BoundingBox:
    """A bounding box annotation in pixel coordinates."""
    x: float  # top-left x
    y: float  # top-left y
    width: float
    height: float

    def center_x(self) -> float:
        return self.x + self.width / 2

    def center_y(self) -> float:
        return self.y + self.height / 2

    def to_yolo(self, img_width: int, img_height: int) -> tuple[float, float, float, float]:
        """Convert to YOLO format (normalized x_center, y_center, width, height)."""
        return (
            self.center_x() / img_width,
            self.center_y() / img_height,
            self.width / img_width,
            self.height / img_height,
        )

    @classmethod
    def from_yolo(cls, x_center: float, y_center: float, w: float, h: float,
                  img_width: int, img_height: int) -> BoundingBox:
        """Create from YOLO normalized coordinates."""
        pw = w * img_width
        ph = h * img_height
        px = x_center * img_width - pw / 2
        py = y_center * img_height - ph / 2
        return cls(x=px, y=py, width=pw, height=ph)


@dataclass
class Polygon:
    """A polygon annotation as a list of (x, y) points in pixel coordinates."""
    points: list[tuple[float, float]] = field(default_factory=list)

    def to_yolo_seg(self, img_width: int, img_height: int) -> list[float]:
        """Convert to YOLO-seg format (normalized x1 y1 x2 y2 ...)."""
        result = []
        for x, y in self.points:
            result.append(x / img_width)
            result.append(y / img_height)
        return result

    @classmethod
    def from_yolo_seg(cls, values: list[float], img_width: int, img_height: int) -> Polygon:
        """Create from YOLO-seg normalized coordinates."""
        points = []
        for i in range(0, len(values) - 1, 2):
            points.append((values[i] * img_width, values[i + 1] * img_height))
        return cls(points=points)

    def bounding_rect(self) -> tuple[float, float, float, float]:
        """Return (x, y, w, h) bounding rectangle."""
        if not self.points:
            return (0, 0, 0, 0)
        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)
        return (x_min, y_min, x_max - x_min, y_max - y_min)


@dataclass
class Annotation:
    """A single annotation on an image."""
    label_id: int  # class index
    ann_type: AnnotationType = AnnotationType.BBOX
    bbox: BoundingBox | None = None
    polygon: Polygon | None = None
    uid: str = field(default_factory=lambda: uuid.uuid4().hex[:8])

    def to_yolo_line(self, img_width: int, img_height: int) -> str:
        if self.ann_type == AnnotationType.POLYGON and self.polygon:
            values = self.polygon.to_yolo_seg(img_width, img_height)
            coords = " ".join(f"{v:.6f}" for v in values)
            return f"{self.label_id} {coords}"
        elif self.bbox:
            xc, yc, w, h = self.bbox.to_yolo(img_width, img_height)
            return f"{self.label_id} {xc:.6f} {yc:.6f} {w:.6f} {h:.6f}"
        return ""

    def display_info(self) -> str:
        """Short display string for annotation list."""
        if self.ann_type == AnnotationType.POLYGON and self.polygon:
            n = len(self.polygon.points)
            x, y, w, h = self.polygon.bounding_rect()
            return f"poly({n}pts) [{x:.0f},{y:.0f} {w:.0f}x{h:.0f}]"
        elif self.bbox:
            b = self.bbox
            return f"[{b.x:.0f},{b.y:.0f} {b.width:.0f}x{b.height:.0f}]"
        return ""


@dataclass
class ImageAnnotations:
    """All annotations for a single image."""
    image_path: str
    image_width: int = 0
    image_height: int = 0
    annotations: list[Annotation] = field(default_factory=list)
    modified: bool = False

    def add(self, annotation: Annotation) -> None:
        self.annotations.append(annotation)
        self.modified = True

    def remove(self, uid: str) -> Optional[Annotation]:
        for i, ann in enumerate(self.annotations):
            if ann.uid == uid:
                self.modified = True
                return self.annotations.pop(i)
        return None

    def clear(self) -> None:
        self.annotations.clear()
        self.modified = True
