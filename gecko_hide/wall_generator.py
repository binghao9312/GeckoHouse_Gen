"""Jittered-row rock layouts for every vertical wall."""

from __future__ import annotations

import random

import cadquery as cq

from .config import GeckoHideConfig
from .stone import create_stone


def _intersects_keepout(
    x0: float, x1: float, z0: float, z1: float, keepout: tuple[float, float, float, float] | None
) -> bool:
    if keepout is None:
        return False
    kx0, kx1, kz0, kz1 = keepout
    return x0 < kx1 and x1 > kx0 and z0 < kz1 and z1 > kz0


def _oriented_stone(
    stone: cq.Shape, side: str, lateral: float, z0: float, embed: float, config: GeckoHideConfig, height: float) -> cq.Shape:
    if side == "front":
        return stone.rotate((0, 0, 0), (1, 0, 0), 90).translate((lateral, -config.depth / 2 + embed, z0 + height / 2))
    if side == "back":
        return stone.rotate((0, 0, 0), (1, 0, 0), -90).translate((lateral, config.depth / 2 - embed, z0 + height / 2))
    if side == "left":
        return stone.rotate((0, 0, 0), (1, 0, 0), 90).rotate((0, 0, 0), (0, 0, 1), -90).translate((-config.width / 2 + embed, lateral, z0 + height / 2))
    if side == "right":
        return stone.rotate((0, 0, 0), (1, 0, 0), 90).rotate((0, 0, 0), (0, 0, 1), 90).translate((config.width / 2 - embed, lateral, z0 + height / 2))
    raise ValueError(f"unsupported wall side: {side}")


def generate_wall_stones(
    body: cq.Shape,
    side: str,
    config: GeckoHideConfig,
    rng: random.Random,
    entrance_keepout: tuple[float, float, float, float] | None = None,
) -> cq.Shape:
    """Return a compound of overlapping irregular rocks in staggered rows."""
    if side not in {"front", "back", "left", "right"}:
        raise ValueError(f"unsupported wall side: {side}")
    span = config.width if side in {"front", "back"} else config.depth
    z_limit = config.height - config.roof_thickness - 1.0
    stones: list[cq.Shape] = []
    # Radial polygon jitter can extend a profile by ``irregularity``.  Start
    # above that allowance so decorative rocks never become the lowest plane.
    z = max(1.0, config.stone_height_max * config.stone_irregularity + 0.5)
    row = 0
    while z < z_limit - config.stone_height_min * 0.35:
        row_height = min(rng.uniform(config.stone_height_min, config.stone_height_max), z_limit - z)
        x = -span / 2 + rng.uniform(-4.0, 4.0) + (row % 2) * rng.uniform(3.0, 9.0)
        while x < span / 2 - config.stone_width_min * 0.25:
            width = min(rng.uniform(config.stone_width_min, config.stone_width_max), span / 2 - x)
            if width < config.stone_width_min * 0.40:
                break
            height = min(row_height * rng.uniform(0.82, 1.08), z_limit - z)
            gap = rng.uniform(config.stone_gap_min, config.stone_gap_max)
            x0, x1 = x + gap / 2, x + width - gap / 2
            if x1 > x0 and not (side == "front" and _intersects_keepout(x0, x1, z, z + height, entrance_keepout)):
                rock_depth = rng.uniform(max(2.1, config.stone_depth_min), config.stone_depth_max)
                embed = min(1.0, rock_depth - 1.2)
                stone = create_stone(
                    x1 - x0,
                    height,
                    rock_depth,
                    rng,
                    vertex_count=rng.randint(config.stone_vertex_count_min, config.stone_vertex_count_max),
                    irregularity=config.stone_irregularity,
                    fillet_radius=rng.uniform(config.stone_fillet_min, config.stone_fillet_max),
                )
                stone = stone.rotate((0, 0, 0), (0, 0, 1), rng.uniform(-8.0, 8.0))
                stones.append(_oriented_stone(stone, side, (x0 + x1) / 2, z, embed, config, height))
            x += width + gap
        z += row_height + rng.uniform(config.stone_gap_min, config.stone_gap_max)
        row += 1
    return cq.Compound.makeCompound(stones)
