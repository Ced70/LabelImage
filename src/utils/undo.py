from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Any


class UndoableAction(Protocol):
    def undo(self) -> None: ...
    def redo(self) -> None: ...
    def description(self) -> str: ...


@dataclass
class AddAnnotationAction:
    """Undo/redo for adding an annotation."""
    _add_fn: Any  # callable to add
    _remove_fn: Any  # callable to remove
    _annotation_data: dict
    _desc: str = "Ajouter annotation"

    def undo(self) -> None:
        self._remove_fn(self._annotation_data)

    def redo(self) -> None:
        self._add_fn(self._annotation_data)

    def description(self) -> str:
        return self._desc


@dataclass
class RemoveAnnotationAction:
    """Undo/redo for removing an annotation."""
    _add_fn: Any
    _remove_fn: Any
    _annotation_data: dict
    _desc: str = "Supprimer annotation"

    def undo(self) -> None:
        self._add_fn(self._annotation_data)

    def redo(self) -> None:
        self._remove_fn(self._annotation_data)

    def description(self) -> str:
        return self._desc


@dataclass
class MoveAnnotationAction:
    """Undo/redo for moving/resizing an annotation."""
    _update_fn: Any
    _uid: str
    _old_bbox: dict
    _new_bbox: dict
    _desc: str = "Déplacer annotation"

    def undo(self) -> None:
        self._update_fn(self._uid, self._old_bbox)

    def redo(self) -> None:
        self._update_fn(self._uid, self._new_bbox)

    def description(self) -> str:
        return self._desc


class UndoStack:
    """Simple undo/redo stack."""

    def __init__(self, max_size: int = 100):
        self._undo_stack: list[UndoableAction] = []
        self._redo_stack: list[UndoableAction] = []
        self._max_size = max_size

    def push(self, action: UndoableAction) -> None:
        self._undo_stack.append(action)
        if len(self._undo_stack) > self._max_size:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def undo(self) -> str | None:
        if not self._undo_stack:
            return None
        action = self._undo_stack.pop()
        action.undo()
        self._redo_stack.append(action)
        return action.description()

    def redo(self) -> str | None:
        if not self._redo_stack:
            return None
        action = self._redo_stack.pop()
        action.redo()
        self._undo_stack.append(action)
        return action.description()

    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    def clear(self) -> None:
        self._undo_stack.clear()
        self._redo_stack.clear()
