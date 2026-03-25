from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.models.annotation import Annotation, AnnotationType, BoundingBox, Polygon
from src.models.label import LabelManager


@dataclass
class DetectionResult:
    class_name: str
    confidence: float
    bbox: tuple[float, float, float, float] | None = None  # x1, y1, x2, y2
    polygon: list[tuple[float, float]] | None = None


def check_ultralytics() -> bool:
    """Check if ultralytics is installed."""
    try:
        import ultralytics
        return True
    except ImportError:
        return False


def load_yolo_model(model_path: str) -> Any:
    """Load a YOLO model from path. Returns the model object."""
    from ultralytics import YOLO
    return YOLO(model_path)


def predict_image(model: Any, image_path: str, confidence: float = 0.25,
                  use_segmentation: bool = False) -> list[DetectionResult]:
    """Run YOLO prediction on a single image.

    Args:
        model: loaded YOLO model
        image_path: path to image
        confidence: minimum confidence threshold
        use_segmentation: if True, try to get polygon masks

    Returns:
        list of DetectionResult
    """
    results = model(image_path, conf=confidence, verbose=False)
    detections = []

    if not results:
        return detections

    result = results[0]
    names = result.names  # {0: 'person', 1: 'bicycle', ...}

    for i, box in enumerate(result.boxes):
        cls_id = int(box.cls[0])
        conf = float(box.conf[0])
        x1, y1, x2, y2 = box.xyxy[0].tolist()
        class_name = names.get(cls_id, f"class_{cls_id}")

        det = DetectionResult(
            class_name=class_name,
            confidence=conf,
            bbox=(x1, y1, x2, y2),
        )

        # Try to get segmentation mask if available
        if use_segmentation and result.masks is not None:
            try:
                mask_xy = result.masks.xy[i]
                if len(mask_xy) >= 3:
                    det.polygon = [(float(p[0]), float(p[1])) for p in mask_xy]
            except (IndexError, AttributeError):
                pass

        detections.append(det)

    return detections


def detections_to_annotations(
    detections: list[DetectionResult],
    label_manager: LabelManager,
) -> list[Annotation]:
    """Convert detection results to Annotation objects.

    Automatically adds new classes to label_manager if needed.
    """
    name_to_id: dict[str, int] = {l.name: l.class_id for l in label_manager.labels}
    annotations = []

    for det in detections:
        if det.class_name not in name_to_id:
            label = label_manager.add(det.class_name)
            name_to_id[det.class_name] = label.class_id

        class_id = name_to_id[det.class_name]

        if det.polygon and len(det.polygon) >= 3:
            ann = Annotation(
                label_id=class_id,
                ann_type=AnnotationType.POLYGON,
                polygon=Polygon(points=det.polygon),
            )
        elif det.bbox:
            x1, y1, x2, y2 = det.bbox
            ann = Annotation(
                label_id=class_id,
                ann_type=AnnotationType.BBOX,
                bbox=BoundingBox(x=x1, y=y1, width=x2 - x1, height=y2 - y1),
            )
        else:
            continue

        annotations.append(ann)

    return annotations
