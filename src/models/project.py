from __future__ import annotations

import os
from pathlib import Path
from dataclasses import dataclass, field

from PySide6.QtGui import QImage

from src.models.annotation import ImageAnnotations
from src.models.label import LabelManager

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}


@dataclass
class Project:
    """Manages the current working directory of images."""
    image_dir: str = ""
    annotations_dir: str = ""  # empty = same as image_dir
    image_files: list[str] = field(default_factory=list)
    current_index: int = -1
    label_manager: LabelManager = field(default_factory=LabelManager)
    _annotations_cache: dict[str, ImageAnnotations] = field(default_factory=dict)

    def open_directory(self, directory: str, annotations_dir: str = "") -> None:
        self.image_dir = directory
        self.annotations_dir = annotations_dir or directory
        self.image_files = sorted(
            f for f in os.listdir(directory)
            if Path(f).suffix.lower() in IMAGE_EXTENSIONS
        )
        self._annotations_cache.clear()
        self.current_index = 0 if self.image_files else -1

        # Load classes.txt from annotations dir first, then image dir
        for d in (self.annotations_dir, directory):
            classes_path = os.path.join(d, "classes.txt")
            if os.path.isfile(classes_path):
                with open(classes_path, "r", encoding="utf-8") as f:
                    self.label_manager = LabelManager.from_classes_txt(f.read())
                break

    def get_annotations_dir(self) -> str:
        return self.annotations_dir or self.image_dir

    def current_image_path(self) -> str | None:
        if 0 <= self.current_index < len(self.image_files):
            return os.path.join(self.image_dir, self.image_files[self.current_index])
        return None

    def current_image_name(self) -> str | None:
        if 0 <= self.current_index < len(self.image_files):
            return self.image_files[self.current_index]
        return None

    def get_annotations(self, image_path: str) -> ImageAnnotations:
        if image_path not in self._annotations_cache:
            img = QImage(image_path)
            self._annotations_cache[image_path] = ImageAnnotations(
                image_path=image_path,
                image_width=img.width(),
                image_height=img.height(),
            )
        return self._annotations_cache[image_path]

    def current_annotations(self) -> ImageAnnotations | None:
        path = self.current_image_path()
        if path:
            return self.get_annotations(path)
        return None

    def go_next(self) -> bool:
        if self.current_index < len(self.image_files) - 1:
            self.current_index += 1
            return True
        return False

    def go_prev(self) -> bool:
        if self.current_index > 0:
            self.current_index -= 1
            return True
        return False

    def go_to(self, index: int) -> bool:
        if 0 <= index < len(self.image_files):
            self.current_index = index
            return True
        return False

    def total_images(self) -> int:
        return len(self.image_files)

    def save_classes_txt(self) -> None:
        if self.image_dir and self.label_manager.labels:
            ann_dir = self.get_annotations_dir()
            os.makedirs(ann_dir, exist_ok=True)
            path = os.path.join(ann_dir, "classes.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.label_manager.to_classes_txt())
