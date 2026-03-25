from __future__ import annotations

import os
from pathlib import Path

from src.models.annotation import Annotation, BoundingBox, Polygon, AnnotationType, ImageAnnotations


def save_yolo(annotations: ImageAnnotations, output_dir: str = "") -> None:
    """Save annotations to a YOLO .txt file.

    Args:
        annotations: the image annotations to save
        output_dir: directory to write the .txt file.
                    If empty, writes next to the image.
    """
    if not annotations.image_path:
        return

    txt_path = _yolo_txt_path(annotations.image_path, output_dir)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    if not annotations.annotations:
        if os.path.isfile(txt_path):
            os.remove(txt_path)
        return

    lines = []
    for ann in annotations.annotations:
        line = ann.to_yolo_line(annotations.image_width, annotations.image_height)
        if line:
            lines.append(line)

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    annotations.modified = False


def load_yolo(image_path: str, img_width: int, img_height: int,
              annotations_dir: str = "") -> list[Annotation]:
    """Load annotations from a YOLO .txt file.

    Args:
        image_path: path to the image
        img_width, img_height: image dimensions
        annotations_dir: directory to look for .txt file.
                         If empty, looks next to the image.
    """
    txt_path = _yolo_txt_path(image_path, annotations_dir)
    if not os.path.isfile(txt_path):
        # Fallback: try next to the image
        if annotations_dir:
            txt_path = _yolo_txt_path(image_path, "")
            if not os.path.isfile(txt_path):
                return []
        else:
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
            values = [float(v) for v in parts[1:]]

            if len(values) == 4:
                bbox = BoundingBox.from_yolo(values[0], values[1], values[2], values[3],
                                             img_width, img_height)
                annotations.append(Annotation(
                    label_id=class_id,
                    ann_type=AnnotationType.BBOX,
                    bbox=bbox,
                ))
            elif len(values) >= 6 and len(values) % 2 == 0:
                polygon = Polygon.from_yolo_seg(values, img_width, img_height)
                annotations.append(Annotation(
                    label_id=class_id,
                    ann_type=AnnotationType.POLYGON,
                    polygon=polygon,
                ))

    return annotations


def has_yolo_annotations(image_path: str, annotations_dir: str = "") -> bool:
    """Check if a YOLO annotation file exists for this image."""
    txt_path = _yolo_txt_path(image_path, annotations_dir)
    if os.path.isfile(txt_path) and os.path.getsize(txt_path) > 0:
        return True
    # Fallback: check next to image
    if annotations_dir:
        txt_path = _yolo_txt_path(image_path, "")
        return os.path.isfile(txt_path) and os.path.getsize(txt_path) > 0
    return False


def _yolo_txt_path(image_path: str, output_dir: str = "") -> str:
    """Get the .txt annotation file path.

    If output_dir is set, the .txt goes in output_dir with the same basename.
    Otherwise, it goes next to the image.
    """
    txt_name = Path(image_path).with_suffix(".txt").name
    if output_dir:
        return os.path.join(output_dir, txt_name)
    return str(Path(image_path).with_suffix(".txt"))
