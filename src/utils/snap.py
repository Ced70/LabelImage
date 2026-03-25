from __future__ import annotations

from PySide6.QtCore import QRectF

SNAP_THRESHOLD = 8  # pixels (in scene coords)


def get_snap_edges(rect: QRectF) -> dict[str, float]:
    """Extract all snap-able edges and centers from a rect."""
    return {
        "left": rect.left(),
        "right": rect.right(),
        "top": rect.top(),
        "bottom": rect.bottom(),
        "cx": rect.center().x(),
        "cy": rect.center().y(),
    }


def find_snap_lines(
    moving_rect: QRectF,
    other_rects: list[QRectF],
    threshold: float = SNAP_THRESHOLD,
) -> tuple[list[float], list[float], float, float]:
    """Find snap guides for a moving rect against other rects.

    Returns:
        (vertical_lines, horizontal_lines, dx_snap, dy_snap)
        where dx_snap/dy_snap are the corrections to apply.
    """
    moving = get_snap_edges(moving_rect)
    v_lines: list[float] = []
    h_lines: list[float] = []
    dx_snap = 0.0
    dy_snap = 0.0

    best_dx = threshold + 1
    best_dy = threshold + 1

    h_keys = ["left", "right", "cx"]
    v_keys = ["top", "bottom", "cy"]

    for other_rect in other_rects:
        other = get_snap_edges(other_rect)

        # Horizontal alignment (vertical snap lines)
        for mk in h_keys:
            for ok in h_keys:
                diff = other[ok] - moving[mk]
                if abs(diff) < abs(best_dx) and abs(diff) < threshold:
                    best_dx = diff
                    dx_snap = diff
                    v_lines = [other[ok]]

        # Vertical alignment (horizontal snap lines)
        for mk in v_keys:
            for ok in v_keys:
                diff = other[ok] - moving[mk]
                if abs(diff) < abs(best_dy) and abs(diff) < threshold:
                    best_dy = diff
                    dy_snap = diff
                    h_lines = [other[ok]]

    return v_lines, h_lines, dx_snap, dy_snap
