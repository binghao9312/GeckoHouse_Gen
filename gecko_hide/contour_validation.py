"""Fast 2D safety checks for V4 editable topographic contours."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Sequence

import numpy as np
from shapely.geometry import Polygon

if TYPE_CHECKING:
    from .contour import ContourDesign

MIN_CONTROL_POINTS = 8
MAX_CONTROL_POINTS = 20
MIN_AREA = 100.0


def sampled_polygon(points: Sequence[Sequence[float]], *, count: int = 192) -> Polygon:
    """Return a sampled periodic-spline polygon, rejecting invalid control data."""
    from .contour_shell import sample_contour

    array = np.asarray(points, dtype=float)
    if array.shape != (len(points), 2) or not np.isfinite(array).all():
        raise ValueError("contour points must be finite XY pairs")
    polygon = Polygon(sample_contour(array, count=count))
    if not polygon.is_valid:
        raise ValueError("Contour self-intersects")
    if polygon.area <= MIN_AREA:
        raise ValueError("contour area is too small")
    return polygon


def validate_contour_design(design: "ContourDesign") -> None:
    """Validate ordered, nested loops and print-safe wall and slope parameters."""
    finite = (design.height, design.wall_thickness, design.roof_thickness, design.ring_clearance,
              design.max_local_slope_deg, design.entrance_width, design.entrance_height, design.entrance_offset,
              *design.summit)
    if not all(math.isfinite(value) for value in finite):
        raise ValueError("contour design values must be finite")
    if design.height <= 0:
        raise ValueError("height must be greater than zero")
    if design.wall_thickness < 3.5:
        raise ValueError("wall thickness must be at least 3.5 mm")
    if not 0 < design.roof_thickness < design.height:
        raise ValueError("roof thickness must be positive and less than height")
    if not 1.0 <= design.ring_clearance <= 3.0:
        raise ValueError("ring clearance must be between 1 and 3 mm")
    if not 0 < design.max_local_slope_deg < 90:
        raise ValueError("max local slope must be between 0 and 90 degrees")
    if design.entrance_width <= 0 or design.entrance_height <= 0:
        raise ValueError("entrance dimensions must be greater than zero")
    if len(design.levels) < 2:
        raise ValueError("at least two contour levels are required")

    polygons: list[Polygon] = []
    previous_z = -math.inf
    orientation: bool | None = None
    for index, level in enumerate(design.levels):
        if not math.isfinite(level.z) or level.z <= previous_z:
            raise ValueError("contour heights must be strictly ascending")
        if not MIN_CONTROL_POINTS <= len(level.points) <= MAX_CONTROL_POINTS:
            raise ValueError(f"contour {index} must contain {MIN_CONTROL_POINTS} to {MAX_CONTROL_POINTS} control points")
        if level.surface_mode not in {"smooth", "step"}:
            raise ValueError(f"contour {index} surface mode must be smooth or step")
        if index == 0 and level.surface_mode != "smooth":
            raise ValueError("base contour surface mode must be smooth")
        polygon = sampled_polygon(level.points)
        is_ccw = polygon.exterior.is_ccw
        if orientation is None:
            orientation = is_ccw
        elif is_ccw != orientation:
            raise ValueError("contour orientations must match")
        polygons.append(polygon)
        previous_z = level.z

    if abs(design.levels[0].z) > 1e-7:
        raise ValueError("bottom contour must be at Z=0")
    if abs(design.levels[-1].z - design.height) > 1e-7:
        raise ValueError("top contour must be at design height")
    if design.entrance_height >= design.height - design.roof_thickness:
        raise ValueError("entrance must remain below the roof")

    for index, (outer, inner) in enumerate(zip(polygons, polygons[1:], strict=False)):
        cleared = outer.buffer(-design.ring_clearance)
        if cleared.is_empty or not cleared.contains(inner):
            raise ValueError(f"contour {index + 1} is outside contour {index} clearance")

    from .contour_shell import align_contours, sample_contour

    sampled = [sample_contour(level.points, count=96) for level in design.levels]
    aligned = align_contours(sampled)
    maximum_tangent = math.tan(math.radians(design.max_local_slope_deg))
    for index, (lower, upper) in enumerate(zip(aligned, aligned[1:], strict=False)):
        vertical = design.levels[index + 1].z - design.levels[index].z
        horizontal = np.linalg.norm(upper - lower, axis=1).max()
        if horizontal / vertical > maximum_tangent:
            raise ValueError(f"contour {index + 1} exceeds the {design.max_local_slope_deg:g} degree local slope limit")
