from __future__ import annotations

from dataclasses import dataclass, field
from PySide6.QtGui import QColor

# Default palette for new labels
DEFAULT_COLORS = [
    "#e6194b", "#3cb44b", "#ffe119", "#4363d8", "#f58231",
    "#911eb4", "#42d4f4", "#f032e6", "#bfef45", "#fabed4",
    "#469990", "#dcbeff", "#9a6324", "#fffac8", "#800000",
    "#aaffc3", "#808000", "#ffd8b1", "#000075", "#a9a9a9",
]


@dataclass
class Label:
    """A class/label definition."""
    name: str
    color: str  # hex color string
    class_id: int

    def qcolor(self) -> QColor:
        return QColor(self.color)


@dataclass
class LabelManager:
    """Manages the list of labels/classes."""
    labels: list[Label] = field(default_factory=list)

    def add(self, name: str, color: str | None = None) -> Label:
        class_id = len(self.labels)
        if color is None:
            color = DEFAULT_COLORS[class_id % len(DEFAULT_COLORS)]
        label = Label(name=name, color=color, class_id=class_id)
        self.labels.append(label)
        return label

    def get(self, class_id: int) -> Label | None:
        if 0 <= class_id < len(self.labels):
            return self.labels[class_id]
        return None

    def names(self) -> list[str]:
        return [l.name for l in self.labels]

    def remove(self, class_id: int) -> None:
        self.labels = [l for l in self.labels if l.class_id != class_id]
        # Re-index
        for i, l in enumerate(self.labels):
            l.class_id = i

    def to_classes_txt(self) -> str:
        """Export as classes.txt (one class name per line)."""
        return "\n".join(self.names())

    @classmethod
    def from_classes_txt(cls, text: str) -> LabelManager:
        """Import from classes.txt content."""
        mgr = cls()
        for line in text.strip().splitlines():
            name = line.strip()
            if name:
                mgr.add(name)
        return mgr
