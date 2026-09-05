"""Large irregular rocks that break up the structural roof plane."""

from __future__ import annotations

import random
import warnings

import cadquery as cq

from .config import GeckoHideConfig
from .stone import create_stone


def _create_roof_blob(
    width: float,
    depth: float,
    visible_height: float,
    embed: float,
    config: GeckoHideConfig,
    rng: random.Random,
) -> cq.Shape | None:
    try:
        return create_stone(
            width,
            depth,
            visible_height + embed,
            rng,
            vertex_count=rng.randint(config.stone_vertex_count_min, config.stone_vertex_count_max),
            irregularity=config.stone_irregularity,
            fillet_radius=min(rng.uniform(config.stone_fillet_min, config.stone_fillet_max), 2.5),
            front_taper=(config.stone_front_taper_min, config.stone_front_taper_max),
            mid_bulge=(config.stone_mid_bulge_min, config.stone_mid_bulge_max),
            section_jitter=config.stone_section_jitter,
        )
    except ValueError as error:
        warnings.warn(f"skipping roof rock after loft failure: {error}", RuntimeWarning)
        return None


def generate_roof_stones(body: cq.Shape, config: GeckoHideConfig, rng: random.Random) -> cq.Shape:
    """Return one dominant domed cap plus a few connected secondary roof blobs."""
    del body  # Geometry is positioned from the deterministic structural dimensions.
    rocks: list[cq.Shape] = []
    embed = 1.5
    cap = _create_roof_blob(
        config.width * rng.uniform(0.65, 0.88),
        config.depth * rng.uniform(0.60, 0.86),
        rng.uniform(7.0, 11.0),
        embed,
        config,
        rng,
    )
    if cap is not None:
        cap = cap.rotate((0, 0, 0), (0, 0, 1), rng.uniform(-8.0, 8.0))
        rocks.append(
            cap.translate(
                (
                    rng.uniform(-8.0, 8.0),
                    rng.uniform(-6.0, 6.0),
                    config.height - embed,
                )
            )
        )

    secondary_min = max(2, config.roof_rock_count_min - 1)
    secondary_max = max(secondary_min, min(4, config.roof_rock_count_max - 1))
    for _ in range(rng.randint(secondary_min, secondary_max)):
        width = config.width * rng.uniform(0.18, 0.34)
        depth = config.depth * rng.uniform(0.20, 0.38)
        rock = _create_roof_blob(width, depth, rng.uniform(3.0, 7.0), embed, config, rng)
        if rock is None:
            continue
        x_extent = max(0.0, config.width * config.shell_top_shrink_max / 2 - width / 2 + 3.0)
        y_extent = max(0.0, config.depth * config.shell_top_shrink_max / 2 - depth / 2 + 3.0)
        rock = rock.rotate((0, 0, 0), (0, 0, 1), rng.uniform(-12.0, 12.0))
        rocks.append(
            rock.translate(
                (
                    rng.uniform(-x_extent, x_extent),
                    rng.uniform(-y_extent, y_extent),
                    config.height - embed,
                )
            )
        )
    return cq.Compound.makeCompound(rocks)
