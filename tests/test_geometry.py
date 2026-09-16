from __future__ import annotations

import math

import pytest

from bilan.geometry import normalize_box, polygon_to_norm, rotate_point_clockwise, rotated_envelope


def test_bbox_normalization_matches_viewer_formula() -> None:
    # A4-ish 595x842 pt page at 300 dpi => about 2479x3508 OCR pixels.
    box = normalize_box((247.9167, 350.8333, 1239.5833, 1754.1667), 595, 842)
    assert box[0] == pytest.approx(0.1, abs=1e-4)
    assert box[1] == pytest.approx(0.1, abs=1e-4)
    assert box[2] == pytest.approx(0.5, abs=1e-4)
    assert box[3] == pytest.approx(0.5, abs=1e-4)


def test_polygon_to_norm_uses_envelope() -> None:
    polygon = [[100, 200], [300, 180], [320, 400], [90, 410]]
    box = polygon_to_norm(polygon, 600, 900)
    assert box[0] < box[2]
    assert box[1] < box[3]
    assert all(0 <= value <= 1 for value in box)


def test_invalid_bbox_is_rejected_not_silently_clipped() -> None:
    with pytest.raises(ValueError):
        normalize_box((0, 0, 3000, 100), 500, 500)
    with pytest.raises(ValueError):
        normalize_box((100, 100, 50, 120), 500, 500)


def test_working_rotation_round_trip_for_right_angles() -> None:
    width, height = 1000.0, 2000.0
    x, y = 125.0, 400.0
    x90, y90 = rotate_point_clockwise(x, y, width, height, 90)
    assert (x90, y90) == pytest.approx((1600.0, 125.0))
    # Applying the complementary transform in the rotated frame returns the point.
    xr, yr = rotate_point_clockwise(x90, y90, height, width, 270)
    assert math.isclose(xr, x)
    assert math.isclose(yr, y)


def test_rotated_envelope_is_ordered() -> None:
    polygon = [[10, 20], [60, 20], [60, 40], [10, 40]]
    box = rotated_envelope(polygon, 100, 200, 90)
    assert box[0] <= box[2]
    assert box[1] <= box[3]
