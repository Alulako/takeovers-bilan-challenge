from __future__ import annotations

import math
from collections.abc import Iterable, Sequence

from .models import OCRLine

DPI_OF_OCR = 300.0
POINTS_PER_INCH = 72.0


def polygon_envelope(polygon: Sequence[Sequence[float]]) -> tuple[float, float, float, float]:
    if len(polygon) < 2:
        raise ValueError("polygon must contain at least two points")
    xs = [float(p[0]) for p in polygon]
    ys = [float(p[1]) for p in polygon]
    if not all(math.isfinite(v) for v in xs + ys):
        raise ValueError("polygon contains a non-finite coordinate")
    return min(xs), min(ys), max(xs), max(ys)


def normalize_box(
    box_px: Sequence[float], page_w_pt: float, page_h_pt: float
) -> tuple[float, float, float, float]:
    if page_w_pt <= 0 or page_h_pt <= 0:
        raise ValueError("page dimensions must be positive")
    if len(box_px) != 4:
        raise ValueError("box must be [x0, y0, x1, y1]")
    x0, y0, x1, y1 = map(float, box_px)
    if not all(math.isfinite(v) for v in (x0, y0, x1, y1)):
        raise ValueError("box contains a non-finite coordinate")
    if x1 < x0 or y1 < y0:
        raise ValueError("box coordinates are reversed")
    scale = DPI_OF_OCR / POINTS_PER_INCH
    result = (x0 / (page_w_pt * scale), y0 / (page_h_pt * scale), x1 / (page_w_pt * scale), y1 / (page_h_pt * scale))
    if any(v < -1e-6 or v > 1.000001 for v in result):
        raise ValueError(f"normalized box outside page: {result}")
    return tuple(min(1.0, max(0.0, v)) for v in result)  # numeric noise only


def polygon_to_norm(
    polygon: Sequence[Sequence[float]], page_w_pt: float, page_h_pt: float
) -> tuple[float, float, float, float]:
    return normalize_box(polygon_envelope(polygon), page_w_pt, page_h_pt)


def union_boxes(boxes: Iterable[Sequence[float]]) -> tuple[float, float, float, float]:
    materialized = [tuple(map(float, box)) for box in boxes]
    if not materialized:
        raise ValueError("cannot union an empty box sequence")
    return (
        min(b[0] for b in materialized),
        min(b[1] for b in materialized),
        max(b[2] for b in materialized),
        max(b[3] for b in materialized),
    )


def union_line_box(lines: Sequence[OCRLine]) -> tuple[float, float, float, float]:
    if not lines:
        raise ValueError("cannot union an empty line sequence")
    return union_boxes((line.x0, line.y0, line.x1, line.y1) for line in lines)


def vertical_overlap(a: OCRLine, b: OCRLine) -> float:
    overlap = max(0.0, min(a.y1, b.y1) - max(a.y0, b.y0))
    denom = max(1.0, min(a.height, b.height))
    return overlap / denom


def same_row(a: OCRLine, b: OCRLine, tolerance_px: float | None = None) -> bool:
    if vertical_overlap(a, b) >= 0.35:
        return True
    tol = tolerance_px if tolerance_px is not None else max(16.0, 0.65 * max(a.height, b.height))
    return abs(a.cy - b.cy) <= tol


def rotate_point_clockwise(
    x: float, y: float, width: float, height: float, degrees: int
) -> tuple[float, float]:
    """Rotate a point into a temporary working frame.

    This helper is intentionally independent from output provenance: callers must keep
    original OCR polygons for final bboxes. It is useful for sideways scans where row
    matching is easier after a 90/180/270 degree transform.
    """
    degrees %= 360
    if degrees == 0:
        return x, y
    if degrees == 90:
        return height - y, x
    if degrees == 180:
        return width - x, height - y
    if degrees == 270:
        return y, width - x
    raise ValueError("only right-angle working rotations are supported")


def rotated_envelope(
    polygon: Sequence[Sequence[float]], width: float, height: float, degrees: int
) -> tuple[float, float, float, float]:
    points = [rotate_point_clockwise(float(x), float(y), width, height, degrees) for x, y in polygon]
    return polygon_envelope(points)
