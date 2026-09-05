from dataclasses import replace

import pytest

from gecko_hide.contour import ContourDesign, ContourLevel


def test_self_intersecting_contour_is_rejected_before_lofting():
    design = ContourDesign.default()
    broken = replace(design.levels[0], points=[
        [-60, -45], [60, 45], [-60, 45], [60, -45],
        [-40, -55], [40, -55], [55, 0], [-55, 0],
    ])
    design.levels[0] = broken
    with pytest.raises(ValueError, match="Contour self-intersects"):
        design.validate()


def test_higher_contour_must_remain_inside_lower_clearance():
    design = ContourDesign.default()
    expanded = [[x * 1.3, y * 1.3] for x, y in design.levels[1].points]
    design.levels[1] = ContourLevel(design.levels[1].z, expanded)
    with pytest.raises(ValueError, match="outside contour 0 clearance"):
        design.validate()


def test_only_smooth_or_ledge_surface_modes_are_accepted():
    design = ContourDesign.default()
    design.levels[2].surface_mode = "invalid"
    with pytest.raises(ValueError, match="surface mode must be smooth or ledge"):
        design.validate()
