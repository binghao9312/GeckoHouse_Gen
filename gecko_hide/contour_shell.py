"""Periodic contour sampling, alignment, and CadQuery V4 shell construction."""

from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

import cadquery as cq
import numpy as np
from scipy.interpolate import splprep, splev
from shapely.geometry import Polygon

from .shell import safe_cut
from .validation import validate_shape

if TYPE_CHECKING:
    from .contour import ContourDesign

SAMPLES_BY_RESOLUTION = {"preview": 48, "final": 96}


def sample_contour(points: Sequence[Sequence[float]], *, count: int = 96) -> np.ndarray:
    """Evaluate an ordered control loop as a periodic cubic B-spline by arc length."""
    controls = np.asarray(points, dtype=float)
    if controls.ndim != 2 or controls.shape[1] != 2 or len(controls) < 4:
        raise ValueError("a contour requires at least four XY control points")
    if count < 4:
        raise ValueError("contour sample count must be at least four")
    # Explicit closure gives splprep an exact seam; evaluation excludes that duplicate.
    closed = np.vstack((controls, controls[0]))
    try:
        knots, _ = splprep(closed.T, s=0.0, per=True, k=min(3, len(controls) - 1))
    except (TypeError, ValueError) as error:
        raise ValueError(f"cannot construct periodic contour spline: {error}") from error
    dense_u = np.linspace(0.0, 1.0, max(count * 16, 512), endpoint=False)
    dense = np.column_stack(splev(dense_u, knots))
    distances = np.linalg.norm(np.diff(np.vstack((dense, dense[0])), axis=0), axis=1)
    cumulative = np.concatenate(([0.0], np.cumsum(distances)))
    targets = np.linspace(0.0, cumulative[-1], count, endpoint=False)
    # Map equal arc-length targets back into the periodic spline parameter domain.
    parameters = np.interp(targets, cumulative, np.concatenate((dense_u, [1.0])))
    return np.column_stack(splev(parameters, knots))


def align_contours(contours: Sequence[np.ndarray]) -> list[np.ndarray]:
    """Orient and cyclically phase equal-size sampled rings to prevent loft twisting."""
    if not contours:
        return []
    aligned = [np.asarray(contours[0], dtype=float).copy()]
    if aligned[0].ndim != 2 or aligned[0].shape[1] != 2:
        raise ValueError("contours must contain XY arrays")
    for candidate in contours[1:]:
        ring = np.asarray(candidate, dtype=float).copy()
        previous = aligned[-1]
        if ring.shape != previous.shape:
            raise ValueError("contours must have the same sample count")
        if _signed_area(ring) * _signed_area(previous) < 0:
            ring = ring[::-1]
        scores = np.sum((previous[None, :, :] - np.stack([np.roll(ring, shift, axis=0) for shift in range(len(ring))])) ** 2,
                        axis=(1, 2))
        aligned.append(np.roll(ring, int(np.argmin(scores)), axis=0))
    return aligned


def _signed_area(ring: np.ndarray) -> float:
    return float(np.dot(ring[:, 0], np.roll(ring[:, 1], -1)) - np.dot(ring[:, 1], np.roll(ring[:, 0], -1)))


def _wire_at(points: np.ndarray, z: float) -> cq.Shape:
    return cq.Workplane("XY", origin=(0.0, 0.0, z)).polyline([tuple(point) for point in points]).close().val()


def _loft(rings: Sequence[np.ndarray], heights: Sequence[float], label: str) -> cq.Shape:
    wires = [_wire_at(ring, float(z)) for ring, z in zip(rings, heights, strict=True)]
    try:
        solid = cq.Solid.makeLoft(wires, ruled=False).clean()
    except Exception as error:
        raise ValueError(f"{label} loft failed: {error}") from error
    if not solid.isValid() or len(solid.Solids()) != 1 or solid.Volume() <= 0:
        raise ValueError(f"{label} loft is not one valid positive-volume solid")
    return solid


def _vertical_prism(ring: np.ndarray, lower_z: float, upper_z: float) -> cq.Shape:
    """Extrude a ring straight upward, creating one horizontal contour ledge."""
    return (
        cq.Workplane("XY", origin=(0.0, 0.0, lower_z))
        .polyline([tuple(point) for point in ring])
        .close()
        .extrude(upper_z - lower_z)
        .val()
        .clean()
    )


def _build_sectioned(rings: Sequence[np.ndarray], heights: Sequence[float], modes: Sequence[str], label: str) -> cq.Shape:
    """Fuse smooth lofts and optional advanced ledge prisms into one solid."""
    if len(rings) != len(heights) or len(rings) != len(modes):
        raise ValueError("section rings, heights, and modes must have matching lengths")
    result: cq.Shape | None = None
    for index in range(1, len(rings)):
        segment = (
            _vertical_prism(rings[index - 1], heights[index - 1], heights[index])
            if modes[index] == "ledge"
            else _loft((rings[index - 1], rings[index]), (heights[index - 1], heights[index]), f"{label} section {index}")
        )
        result = segment if result is None else result.fuse(segment).clean()
        if not result.isValid() or len(result.Solids()) != 1:
            raise ValueError(f"{label} sections did not fuse into one solid")
    if result is None or result.Volume() <= 0:
        raise ValueError(f"{label} has no sections")
    return result


def _sampled_levels(design: "ContourDesign", *, count: int) -> tuple[list[np.ndarray], list[float], list[str]]:
    rings = [sample_contour(level.points, count=count) for level in design.levels]
    return align_contours(rings), [level.z for level in design.levels], [level.surface_mode for level in design.levels]


def build_outer_from_contours(design: "ContourDesign", resolution: str = "final") -> cq.Shape:
    """Loft all aligned V4 closed contour rings into the continuous outer solid."""
    if resolution not in SAMPLES_BY_RESOLUTION:
        raise ValueError(f"unknown contour resolution: {resolution}")
    design.validate()
    rings, heights, modes = _sampled_levels(design, count=SAMPLES_BY_RESOLUTION[resolution])
    return _loft(rings, heights, "contour outer shell") if all(mode == "smooth" for mode in modes[1:]) else _build_sectioned(
        rings, heights, modes, "contour outer shell"
    )


def _ring_at_height(rings: Sequence[np.ndarray], heights: Sequence[float], modes: Sequence[str], z: float) -> np.ndarray:
    for index, (lower, upper) in enumerate(zip(heights, heights[1:], strict=False)):
        if lower <= z <= upper:
            if modes[index + 1] == "ledge":
                return rings[index]
            amount = (z - lower) / (upper - lower)
            return rings[index] * (1.0 - amount) + rings[index + 1] * amount
    raise ValueError("cavity roof is outside contour height range")


def _inward_ring(outer: np.ndarray, wall: float, *, count: int) -> np.ndarray:
    polygon = Polygon(outer)
    inner = polygon.buffer(-wall)
    if inner.is_empty or inner.geom_type != "Polygon" or not inner.is_valid:
        raise ValueError("inward contour offset collapsed or split into multiple regions")
    coordinates = np.asarray(inner.exterior.coords[:-1], dtype=float)
    return sample_contour(coordinates, count=count)


def build_inner_from_contours(design: "ContourDesign", resolution: str = "final") -> cq.Shape:
    """Loft the cavity from its open bottom or optional solid base to the roof."""
    if resolution not in SAMPLES_BY_RESOLUTION:
        raise ValueError(f"unknown contour resolution: {resolution}")
    design.validate()
    count = SAMPLES_BY_RESOLUTION[resolution]
    outer_rings, outer_heights, outer_modes = _sampled_levels(design, count=count)
    cavity_top = design.height - design.roof_thickness
    if design.base_thickness == 0:
        selected_rings = [outer_rings[0]]
        selected_heights = [-0.5]
    else:
        selected_rings = [_ring_at_height(outer_rings, outer_heights, outer_modes, design.base_thickness)]
        selected_heights = [design.base_thickness]
    for ring, z in zip(outer_rings, outer_heights, strict=True):
        if design.base_thickness < z < cavity_top:
            selected_rings.append(ring)
            selected_heights.append(z)
    # The cavity remains smooth through an exterior ledge so it cannot create
    # an interior shelf that disconnects the printable open volume.
    selected_rings.append(_ring_at_height(outer_rings, outer_heights, ["smooth"] * len(outer_rings), cavity_top))
    selected_heights.append(cavity_top)
    inner = align_contours([_inward_ring(ring, design.wall_thickness, count=count) for ring in selected_rings])
    return _loft(inner, selected_heights, "contour inner cavity")


def build_contour_shell(design: "ContourDesign", resolution: str = "final") -> cq.Shape:
    """Build the V4 open-bottom shell with a continuous roof from contour offsets."""
    outer = build_outer_from_contours(design, resolution)
    inner = build_inner_from_contours(design, resolution)
    shell = safe_cut(outer, inner)
    validate_shape(shell)
    return shell
