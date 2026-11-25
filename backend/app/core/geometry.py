"""Geometri dasar: polygon, kotak (x1, y1, x2, y2), IoU, convex hull."""

from __future__ import annotations

Point = tuple[float, float]
Box = tuple[float, float, float, float]
Polygon = list[list[float]]


def point_in_polygon(pt: Point, poly: Polygon) -> bool:
    """Ray casting. poly = [[x, y], ...] dalam koordinat piksel frame."""
    x, y = pt
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y):
            if x < (xj - xi) * (y - yi) / (yj - yi) + xi:
                inside = not inside
        j = i
    return inside


def point_in_box(pt: Point, box: Box) -> bool:
    x, y = pt
    return box[0] <= x <= box[2] and box[1] <= y <= box[3]


def box_center(box: Box) -> Point:
    return ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)


def box_area(box: Box) -> float:
    return max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])


def iou(a: Box, b: Box) -> float:
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    inter = box_area((ix1, iy1, ix2, iy2))
    union = box_area(a) + box_area(b) - inter
    return inter / union if union > 0 else 0.0


def expand_box(box: Box, ratio: float) -> Box:
    w, h = box[2] - box[0], box[3] - box[1]
    return (box[0] - w * ratio, box[1] - h * ratio, box[2] + w * ratio, box[3] + h * ratio)


def box_to_polygon(box: Box) -> Polygon:
    x1, y1, x2, y2 = box
    return [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]


def convex_hull(points: list[Point]) -> Polygon:
    """Andrew monotone chain."""
    pts = sorted(set(points))
    if len(pts) <= 2:
        return [list(p) for p in pts]

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: list[Point] = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper: list[Point] = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return [list(p) for p in lower[:-1] + upper[:-1]]
