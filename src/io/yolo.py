from __future__ import annotations

import os
from pathlib import Path

from src.models.annotation import Annotation, BoundingBox, ImageAnnotations


def save_yolo(annotations: ImageAnnotations) -> None:
    """Save annotations to a YOLO .txt file next to the image."""
    if not annotations.image_path:
        return

    txt_path = _yolo_txt_path(annotations.image_path)

    if not annotations.annotations:
        # Remove txt file if no annotations
        if os.path.isfile(txt_path):
            os.remove(txt_path)
        return

    lines = []
    for ann in annotations.annotations:
        lines.append(ann.to_yolo_line(annotations.image_width, annotations.image_height))

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    annotations.modified = False


def load_yolo(image_path: str, img_width: int, img_height: int) -> list[Annotation]:
    """Load annotations from a YOLO .txt file next to the image."""
    txt_path = _yolo_txt_path(image_path)
    if not os.path.isfile(txt_path):
        return []

    annotations = []
    with open(txt_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 5:
                continue
            class_id = int(parts[0])
            xc, yc, w, h = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
            bbox = BoundingBox.from_yolo(xc, yc, w, h, img_width, img_height)
            annotations.append(Annotation(label_id=class_id, bbox=bbox))

    return annotations


def has_yolo_annotations(image_path: str) -> bool:
    """Check if a YOLO annotation file exists for this image."""
    txt_path = _yolo_txt_path(image_path)
    return os.path.isfile(txt_path) and os.path.getsize(txt_path) > 0


def _yolo_txt_path(image_path: str) -> str:
    return str(Path(image_path).with_suffix(".txt"))
