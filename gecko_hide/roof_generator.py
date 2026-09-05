"""Large irregular rocks that break up the structural roof plane."""

from __future__ import annotations

import random

import cadquery as cq

from .config import GeckoHideConfig
from .stone import create_stone


def generate_roof_stones(body: cq.Shape, config: GeckoHideConfig, rng: random.Random) -> cq.Shape:
    """Return a connected-ready compound of 3–7 broad, low roof rocks."""
    rocks: list[cq.Shape] = []
    count = rng.randint(config.roof_rock_count_min, config.roof_rock_count_max)
    for _ in range(count):
        width = min(rng.uniform(40.0, 100.0), config.width * 0.62)
        depth = min(rng.uniform(30.0, 80.0), config.depth * 0.72)
        visible_height = rng.uniform(3.0, 9.0)
        embed = 1.2
        # Keep each rock inside the +10 mm XY and +12 mm Z allowance.
        x_extent = max(0.0, config.width / 2 + 6.0 - width / 2)
        y_extent = max(0.0, config.depth / 2 + 6.0 - depth / 2)
        rock = create_stone(
            width,
            depth,
            visible_height + embed,
            rng,
            vertex_count=rng.randint(config.stone_vertex_count_min, config.stone_vertex_count_max),
            irregularity=config.stone_irregularity,
            fillet_radius=min(rng.uniform(config.stone_fillet_min, config.stone_fillet_max), 2.5),
        )
        rock = rock.rotate((0, 0, 0), (0, 0, 1), rng.uniform(-10.0, 10.0))
        rocks.append(rock.translate((rng.uniform(-x_extent, x_extent), rng.uniform(-y_extent, y_extent), config.height - embed)))
    return cq.Compound.makeCompound(rocks)
