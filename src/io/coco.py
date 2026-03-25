from __future__ import annotations

import json
import os
from pathlib import Path

from src.models.annotation import Annotation, AnnotationType, BoundingBox, Polygon, ImageAnnotations
from src.models.label import LabelManager


def save_coco(
    all_annotations: dict[str, ImageAnnotations],
    label_manager: LabelManager,
    output_path: str,
) -> None:
    """Save all annotations as a single COCO JSON file.

    Args:
        all_annotations: dict mapping image_path -> ImageAnnotations
        label_manager: the label manager with class definitions
        output_path: path to write the JSON file
    """
    coco = {
        "images": [],
        "annotations": [],
        "categories": [],
    }

    # Categories
    for label in label_manager.labels:
        coco["categories"].append({
            "id": label.class_id,
            "name": label.name,
            "supercategory": "none",
        })

    ann_id = 1
    for img_id, (img_path, img_ann) in enumerate(all_annotations.items(), start=1):
        coco["images"].append({
            "id": img_id,
            "file_name": os.path.basename(img_path),
            "width": img_ann.image_width,
            "height": img_ann.image_height,
        })

        for ann in img_ann.annotations:
            coco_ann: dict = {
                "id": ann_id,
                "image_id": img_id,
                "category_id": ann.label_id,
                "iscrowd": 0,
            }

            if ann.ann_type == AnnotationType.BBOX and ann.bbox:
                b = ann.bbox
                coco_ann["bbox"] = [
                    round(b.x, 2), round(b.y, 2),
                    round(b.width, 2), round(b.height, 2),
                ]
                coco_ann["area"] = round(b.width * b.height, 2)
                coco_ann["segmentation"] = []

            elif ann.ann_type == AnnotationType.POLYGON and ann.polygon:
                pts = ann.polygon.points
                flat = []
                for px, py in pts:
                    flat.extend([round(px, 2), round(py, 2)])
                coco_ann["segmentation"] = [flat]

                x, y, w, h = ann.polygon.bounding_rect()
                coco_ann["bbox"] = [round(x, 2), round(y, 2), round(w, 2), round(h, 2)]
                coco_ann["area"] = round(w * h, 2)

            coco["annotations"].append(coco_ann)
            ann_id += 1

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(coco, f, indent=2, ensure_ascii=False)


def load_coco(
    json_path: str,
    image_dir: str,
    label_manager: LabelManager,
) -> dict[str, list[Annotation]]:
    """Load annotations from a COCO JSON file.

    Returns:
        dict mapping image filename -> list of Annotations
    """
    if not os.path.isfile(json_path):
        return {}

    with open(json_path, "r", encoding="utf-8") as f:
        coco = json.load(f)

    # Build category map
    cat_to_label: dict[int, int] = {}
    name_to_id = {l.name: l.class_id for l in label_manager.labels}

    for cat in coco.get("categories", []):
        cat_id = cat["id"]
        cat_name = cat["name"]
        if cat_name not in name_to_id:
            label = label_manager.add(cat_name)
            name_to_id[cat_name] = label.class_id
        cat_to_label[cat_id] = name_to_id[cat_name]

    # Build image id -> filename map
    img_id_to_name: dict[int, str] = {}
    for img in coco.get("images", []):
        img_id_to_name[img["id"]] = img["file_name"]

    # Parse annotations
    result: dict[str, list[Annotation]] = {}
    for ann in coco.get("annotations", []):
        img_name = img_id_to_name.get(ann["image_id"])
        if not img_name:
            continue

        label_id = cat_to_label.get(ann["category_id"], 0)

        segmentation = ann.get("segmentation", [])
        if segmentation and isinstance(segmentation[0], list) and len(segmentation[0]) >= 6:
            # Polygon annotation
            flat = segmentation[0]
            points = [(flat[i], flat[i + 1]) for i in range(0, len(flat) - 1, 2)]
            annotation = Annotation(
                label_id=label_id,
                ann_type=AnnotationType.POLYGON,
                polygon=Polygon(points=points),
            )
        elif "bbox" in ann:
            bx, by, bw, bh = ann["bbox"]
            annotation = Annotation(
                label_id=label_id,
                ann_type=AnnotationType.BBOX,
                bbox=BoundingBox(x=bx, y=by, width=bw, height=bh),
            )
        else:
            continue

        result.setdefault(img_name, []).append(annotation)

    return result
