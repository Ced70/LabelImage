"""Export annotated regions as individual cropped images."""
from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtGui import QImage

from src.models.annotation import ImageAnnotations, AnnotationType
from src.models.label import LabelManager


def export_crops(
    annotations_cache: dict[str, ImageAnnotations],
    label_manager: LabelManager,
    output_dir: str,
    padding: int = 0,
) -> int:
    """Export all annotated bbox regions as cropped images.

    Creates subdirectories per class name.
    Returns total number of crops exported.
    """
    count = 0

    for img_path, ann_data in annotations_cache.items():
        if not ann_data.annotations:
            continue

        img = QImage(img_path)
        if img.isNull():
            continue

        stem = Path(img_path).stem

        for i, ann in enumerate(ann_data.annotations):
            if ann.ann_type == AnnotationType.POLYGON and ann.polygon:
                x, y, w, h = ann.polygon.bounding_rect()
            elif ann.ann_type == AnnotationType.BBOX and ann.bbox:
                x, y, w, h = ann.bbox.x, ann.bbox.y, ann.bbox.width, ann.bbox.height
            else:
                continue

            # Apply padding
            x1 = max(0, int(x - padding))
            y1 = max(0, int(y - padding))
            x2 = min(img.width(), int(x + w + padding))
            y2 = min(img.height(), int(y + h + padding))

            if x2 - x1 < 2 or y2 - y1 < 2:
                continue

            crop = img.copy(x1, y1, x2 - x1, y2 - y1)

            # Get class name for subdirectory
            label = label_manager.get(ann.label_id)
            class_name = label.name if label else f"class_{ann.label_id}"
            class_dir = os.path.join(output_dir, class_name)
            os.makedirs(class_dir, exist_ok=True)

            filename = f"{stem}_{i:04d}.jpg"
            crop.save(os.path.join(class_dir, filename))
            count += 1

    return count
