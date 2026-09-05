"""Irregular polygonal rock solids; never spheres or regular bricks."""

from __future__ import annotations

import math
import random

import cadquery as cq

from .shell import safe_loft


def create_stone(
    width: float,
    height: float,
    depth: float,
    rng: random.Random,
    *,
    vertex_count: int | None = None,
    irregularity: float = 0.20,
    fillet_radius: float = 2.0,
    front_taper: tuple[float, float] = (0.72, 0.88),
    mid_bulge: tuple[float, float] = (1.02, 1.10),
    section_jitter: float = 0.06,
) -> cq.Shape:
    """Create a correlated multi-section lofted rock with a rounded exposed face."""
    if min(width, height, depth) <= 0:
        raise ValueError("stone dimensions must be positive")
    if not 0 < front_taper[0] <= front_taper[1] <= 1.0:
        raise ValueError("invalid stone front taper range")
    if not 1.0 <= mid_bulge[0] <= mid_bulge[1]:
        raise ValueError("invalid stone middle bulge range")
    if not 0.0 <= section_jitter <= 0.20:
        raise ValueError("stone section jitter must be between 0.0 and 0.20")
    count = vertex_count if vertex_count is not None else rng.randint(7, 12)
    if count < 5:
        raise ValueError("stone requires at least five vertices")

    angles = [
        2 * math.pi * index / count + rng.uniform(-0.14, 0.14)
        for index in range(count)
    ]
    base_radii = [rng.uniform(1.0 - irregularity, 1.0 + irregularity) for _ in range(count)]
    section_scales = (
        rng.uniform(0.90, 0.98),
        rng.uniform(1.00, 1.05),
        rng.uniform(mid_bulge[0], mid_bulge[1]),
        rng.uniform(0.90, 0.98),
        rng.uniform(front_taper[0], front_taper[1]),
    )
    section_depths = (0.0, depth * 0.20, depth * 0.55, depth * 0.82, depth)
    radial_variation = [
        [rng.uniform(-section_jitter, section_jitter) for _ in range(count)]
        for _ in section_scales
    ]

    def profiles(jitter_scale: float) -> list[cq.Shape]:
        wires: list[cq.Shape] = []
        for scale, z, variations in zip(section_scales, section_depths, radial_variation):
            points = [
                (
                    math.cos(angle) * width / 2 * radius * (scale + variation * jitter_scale),
                    math.sin(angle) * height / 2 * radius * (scale + variation * jitter_scale),
                )
                for angle, radius, variation in zip(angles, base_radii, variations)
            ]
            wires.append(cq.Workplane("XY", origin=(0, 0, z)).polyline(points).close().val())
        return wires

    # The smooth loft supplies the softness; applying another edge fillet here
    # is both visually redundant and fragile on closely spaced rock sections.
    return safe_loft(profiles, label="decorative stone")
