"""Irregular polygonal rock solids; never spheres or regular bricks."""

from __future__ import annotations

import math
import random

import cadquery as cq

from .shell import safe_fillet


def create_stone(
    width: float,
    height: float,
    depth: float,
    rng: random.Random,
    *,
    vertex_count: int | None = None,
    irregularity: float = 0.20,
    fillet_radius: float = 2.0,
) -> cq.Shape:
    """Extrude a deterministic irregular radial polygon into one rounded solid."""
    if min(width, height, depth) <= 0:
        raise ValueError("stone dimensions must be positive")
    count = vertex_count if vertex_count is not None else rng.randint(7, 12)
    if count < 5:
        raise ValueError("stone requires at least five vertices")
    points: list[tuple[float, float]] = []
    for index in range(count):
        base_angle = 2 * math.pi * index / count
        angle = base_angle + rng.uniform(-0.14, 0.14)
        radius = rng.uniform(1.0 - irregularity, 1.0 + irregularity)
        points.append((
            math.cos(angle) * width / 2 * radius,
            math.sin(angle) * height / 2 * radius,
        ))
    stone = cq.Workplane("XY").polyline(points).close().extrude(depth).val()
    # Vertical-edge fillets soften the outline without thinning the wall-facing face.
    return safe_fillet(stone, min(fillet_radius, depth * 0.45, width * 0.12, height * 0.12))
