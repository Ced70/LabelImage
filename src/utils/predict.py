"""Predict annotations on a new image based on previously annotated images.

Two strategies:
1. Propagation: copy annotations from the previous image (good for video frames)
2. Template matching: extract annotated regions from recent images and search
   for similar regions in the current image using OpenCV template matching.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass

from src.models.annotation import Annotation, AnnotationType, BoundingBox, ImageAnnotations


def check_opencv() -> bool:
    try:
        import cv2
        return True
    except ImportError:
        return False


@dataclass
class PredictionResult:
    annotation: Annotation
    confidence: float
    source_image: str  # which image this was matched from


def propagate_from_previous(prev_annotations: ImageAnnotations,
                            target_width: int, target_height: int) -> list[Annotation]:
    """Copy annotations from previous image, scaling if dimensions differ."""
    if not prev_annotations.annotations:
        return []

    sx = target_width / prev_annotations.image_width if prev_annotations.image_width else 1
    sy = target_height / prev_annotations.image_height if prev_annotations.image_height else 1

    results = []
    for ann in prev_annotations.annotations:
        new_ann = _copy_and_scale(ann, sx, sy)
        if new_ann:
            results.append(new_ann)
    return results


def predict_by_template_matching(
    source_annotations_list: list[tuple[str, ImageAnnotations]],
    target_image_path: str,
    target_width: int,
    target_height: int,
    confidence_threshold: float = 0.6,
    max_sources: int = 5,
    scales: list[float] | None = None,
) -> list[PredictionResult]:
    """Find similar regions in target image using template matching.

    Args:
        source_annotations_list: list of (image_path, ImageAnnotations) from recent images
        target_image_path: path to the image to predict on
        target_width, target_height: dimensions of target image
        confidence_threshold: minimum matching confidence (0-1)
        max_sources: max number of source images to use
        scales: list of scales to try for multi-scale matching

    Returns:
        list of PredictionResult with matched annotations
    """
    import cv2
    import numpy as np

    if scales is None:
        scales = [0.8, 0.9, 1.0, 1.1, 1.2]

    target_img = cv2.imread(target_image_path)
    if target_img is None:
        return []

    target_gray = cv2.cvtColor(target_img, cv2.COLOR_BGR2GRAY)
    th, tw = target_gray.shape[:2]

    results: list[PredictionResult] = []
    seen_regions: list[tuple[float, float, float, float]] = []

    sources = source_annotations_list[-max_sources:]

    for src_path, src_ann in sources:
        src_img = cv2.imread(src_path)
        if src_img is None:
            continue
        src_gray = cv2.cvtColor(src_img, cv2.COLOR_BGR2GRAY)

        for ann in src_ann.annotations:
            if ann.ann_type != AnnotationType.BBOX or not ann.bbox:
                continue

            b = ann.bbox
            x1 = max(0, int(b.x))
            y1 = max(0, int(b.y))
            x2 = min(src_gray.shape[1], int(b.x + b.width))
            y2 = min(src_gray.shape[0], int(b.y + b.height))

            if x2 - x1 < 10 or y2 - y1 < 10:
                continue

            template = src_gray[y1:y2, x1:x2]

            best_val = -1
            best_loc = None
            best_scale = 1.0

            for scale in scales:
                sw = int(template.shape[1] * scale)
                sh = int(template.shape[0] * scale)
                if sw < 10 or sh < 10 or sw > tw or sh > th:
                    continue

                scaled_template = cv2.resize(template, (sw, sh))

                try:
                    match = cv2.matchTemplate(target_gray, scaled_template, cv2.TM_CCOEFF_NORMED)
                except cv2.error:
                    continue

                _, max_val, _, max_loc = cv2.minMaxLoc(match)

                if max_val > best_val:
                    best_val = max_val
                    best_loc = max_loc
                    best_scale = scale

            if best_val >= confidence_threshold and best_loc is not None:
                mx, my = best_loc
                mw = int(template.shape[1] * best_scale)
                mh = int(template.shape[0] * best_scale)

                # Check overlap with already found regions
                if _is_overlapping(mx, my, mw, mh, seen_regions, iou_threshold=0.5):
                    continue

                seen_regions.append((mx, my, mw, mh))

                new_ann = Annotation(
                    label_id=ann.label_id,
                    ann_type=AnnotationType.BBOX,
                    bbox=BoundingBox(x=mx, y=my, width=mw, height=mh),
                )
                results.append(PredictionResult(
                    annotation=new_ann,
                    confidence=best_val,
                    source_image=src_path,
                ))

    # Sort by confidence
    results.sort(key=lambda r: r.confidence, reverse=True)
    return results


def _copy_and_scale(ann: Annotation, sx: float, sy: float) -> Annotation | None:
    """Copy an annotation, scaling coordinates."""
    import uuid
    if ann.ann_type == AnnotationType.BBOX and ann.bbox:
        return Annotation(
            label_id=ann.label_id,
            ann_type=AnnotationType.BBOX,
            bbox=BoundingBox(
                x=ann.bbox.x * sx,
                y=ann.bbox.y * sy,
                width=ann.bbox.width * sx,
                height=ann.bbox.height * sy,
            ),
            uid=uuid.uuid4().hex[:8],
        )
    elif ann.ann_type == AnnotationType.POLYGON and ann.polygon:
        from src.models.annotation import Polygon
        return Annotation(
            label_id=ann.label_id,
            ann_type=AnnotationType.POLYGON,
            polygon=Polygon(points=[(x * sx, y * sy) for x, y in ann.polygon.points]),
            uid=uuid.uuid4().hex[:8],
        )
    return None


def _is_overlapping(x: float, y: float, w: float, h: float,
                    regions: list[tuple[float, float, float, float]],
                    iou_threshold: float = 0.5) -> bool:
    """Check if a region overlaps significantly with existing regions."""
    for rx, ry, rw, rh in regions:
        # Compute IoU
        ix1 = max(x, rx)
        iy1 = max(y, ry)
        ix2 = min(x + w, rx + rw)
        iy2 = min(y + h, ry + rh)

        if ix2 <= ix1 or iy2 <= iy1:
            continue

        inter = (ix2 - ix1) * (iy2 - iy1)
        area1 = w * h
        area2 = rw * rh
        union = area1 + area2 - inter

        if union > 0 and inter / union > iou_threshold:
            return True
    return False
