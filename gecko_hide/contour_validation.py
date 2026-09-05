"""Fast V5 transition safety checks for the canonical contour stack."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Sequence

import numpy as np
from shapely.geometry import Point, Polygon

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


def _maximum_overhang(lower: Polygon, upper: Polygon) -> float:
    """Return the farthest sampled upper boundary distance outside the lower ring."""
    distances = []
    for coordinate in upper.exterior.coords:
        point = Point(coordinate)
        if not lower.covers(point):
            distances.append(lower.exterior.distance(point))
    return max(distances, default=0.0)


def validate_contour_design(design: "ContourDesign") -> None:
    """Validate safe adjacent transitions, allowing only controlled roof-shoulder overhang."""
    finite = (
        design.height, design.wall_thickness, design.roof_thickness, design.ring_clearance,
        design.max_local_slope_deg, design.entrance_width, design.entrance_height, design.entrance_offset,
        design.max_overhang_xy, design.max_overhang_ratio, design.min_level_spacing, *design.summit,
    )
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
    if not 0 < design.max_overhang_xy <= 20:
        raise ValueError("maximum roof overhang must be between 0 and 20 mm")
    if not 0 < design.max_overhang_ratio <= 0.2:
        raise ValueError("maximum roof overhang ratio must be between 0 and 0.2")
    if design.min_level_spacing < 1:
        raise ValueError("minimum level spacing must be at least 1 mm")
    if len(design.levels) < 2:
        raise ValueError("at least two contour levels are required")
    if not 0.8 <= design.appearance.relief_depth <= 2.5:
        raise ValueError("relief depth must be between 0.8 and 2.5 mm")
    if not 1.0 <= design.appearance.relief_gap <= 2.0:
        raise ValueError("relief gap must be between 1 and 2 mm")
    if design.appearance.relief_scale <= 0:
        raise ValueError("relief scale must be positive")

    polygons: list[Polygon] = []
    previous_z = -math.inf
    orientation: bool | None = None
    valid_roles = {"wall", "roof_shoulder", "roof_top"}
    for index, level in enumerate(design.levels):
        if not math.isfinite(level.z) or level.z <= previous_z:
            raise ValueError("contour heights must be strictly ascending")
        if index and level.z - previous_z < design.min_level_spacing - 1e-7:
            raise ValueError(f"contour {index} is closer than the {design.min_level_spacing:g} mm minimum spacing")
        if not MIN_CONTROL_POINTS <= len(level.points) <= MAX_CONTROL_POINTS:
            raise ValueError(f"contour {index} must contain {MIN_CONTROL_POINTS} to {MAX_CONTROL_POINTS} control points")
        if level.surface_mode not in {"smooth", "ledge"}:
            raise ValueError(f"contour {index} surface mode must be smooth or ledge")
        if index == 0 and level.surface_mode != "smooth":
            raise ValueError("base contour surface mode must be smooth")
        if level.role not in valid_roles:
            raise ValueError(f"contour {index} has an invalid role")
        if level.role == "roof_shoulder" and index == 0:
            raise ValueError("roof shoulder cannot be the base contour")
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
    _validate_entrance(design)

    for index, (lower, upper) in enumerate(zip(polygons, polygons[1:], strict=False)):
        upper_level = design.levels[index + 1]
        if upper_level.role == "roof_shoulder":
            lower_width = lower.bounds[2] - lower.bounds[0]
            lower_depth = lower.bounds[3] - lower.bounds[1]
            permitted = min(design.max_overhang_xy, max(lower_width, lower_depth) * design.max_overhang_ratio)
            overhang = _maximum_overhang(lower, upper)
            if overhang > permitted + 1e-7:
                raise ValueError(
                    f"roof shoulder overhang {overhang:.2f} mm exceeds the {permitted:.2f} mm transition limit"
                )
        else:
            # Wall rings remain nested by default, while a clearance-sized organic
            # swell is safe and required by the authored lower wall silhouette.
            permitted = design.ring_clearance if upper_level.role == "wall" else 0.0
            if not lower.buffer(permitted).contains(upper):
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


def _validate_entrance(design: "ContourDesign") -> None:
    profile = np.asarray(design.entrance_profile, dtype=float)
    if profile.shape != (len(design.entrance_profile), 2) or not 6 <= len(profile) <= 8 or not np.isfinite(profile).all():
        raise ValueError("entrance profile must contain 6 to 8 finite XZ handles")
    if abs(profile[0, 1]) > 1e-7 or abs(profile[-1, 1]) > 1e-7:
        raise ValueError("entrance profile must remain open at Z=0")
    arch = Polygon(profile)
    if not arch.is_valid or arch.area <= 1:
        raise ValueError("entrance profile must be a valid arch")
    if float(profile[:, 1].max()) >= design.height - design.roof_thickness:
        raise ValueError("entrance must remain below the roof")
