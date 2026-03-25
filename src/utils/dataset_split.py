"""Export dataset with train/val/test split in YOLO format."""
from __future__ import annotations

import os
import random
import shutil
from pathlib import Path

from src.models.annotation import ImageAnnotations
from src.models.label import LabelManager
from src.io.yolo import save_yolo


def export_yolo_split(
    image_dir: str,
    image_files: list[str],
    annotations_cache: dict[str, ImageAnnotations],
    label_manager: LabelManager,
    output_dir: str,
    train_ratio: float = 0.7,
    val_ratio: float = 0.2,
    test_ratio: float = 0.1,
    shuffle: bool = True,
) -> dict[str, int]:
    """Export dataset in YOLO directory structure with splits.

    Creates:
        output_dir/
            train/images/ + train/labels/
            val/images/ + val/labels/
            test/images/ + test/labels/
            data.yaml

    Returns dict with counts per split.
    """
    # Filter to only annotated images
    annotated = []
    for fname in image_files:
        img_path = os.path.join(image_dir, fname)
        if img_path in annotations_cache and annotations_cache[img_path].annotations:
            annotated.append(fname)

    if not annotated:
        return {"train": 0, "val": 0, "test": 0}

    if shuffle:
        random.shuffle(annotated)

    n = len(annotated)
    n_train = int(n * train_ratio)
    n_val = int(n * val_ratio)

    splits = {
        "train": annotated[:n_train],
        "val": annotated[n_train:n_train + n_val],
        "test": annotated[n_train + n_val:],
    }

    counts = {}
    for split_name, files in splits.items():
        img_dir = os.path.join(output_dir, split_name, "images")
        lbl_dir = os.path.join(output_dir, split_name, "labels")
        os.makedirs(img_dir, exist_ok=True)
        os.makedirs(lbl_dir, exist_ok=True)

        for fname in files:
            src_img = os.path.join(image_dir, fname)
            dst_img = os.path.join(img_dir, fname)
            shutil.copy2(src_img, dst_img)

            # Write label file
            img_path = os.path.join(image_dir, fname)
            if img_path in annotations_cache:
                ann = annotations_cache[img_path]
                txt_name = Path(fname).with_suffix(".txt").name
                lines = []
                for a in ann.annotations:
                    line = a.to_yolo_line(ann.image_width, ann.image_height)
                    if line:
                        lines.append(line)
                if lines:
                    with open(os.path.join(lbl_dir, txt_name), "w") as f:
                        f.write("\n".join(lines) + "\n")

        counts[split_name] = len(files)

    # Write data.yaml
    class_names = label_manager.names()
    yaml_content = f"""# LabelImage dataset export
path: {output_dir}
train: train/images
val: val/images
test: test/images

nc: {len(class_names)}
names: {class_names}
"""
    with open(os.path.join(output_dir, "data.yaml"), "w") as f:
        f.write(yaml_content)

    # Write classes.txt
    with open(os.path.join(output_dir, "classes.txt"), "w") as f:
        f.write("\n".join(class_names))

    return counts
