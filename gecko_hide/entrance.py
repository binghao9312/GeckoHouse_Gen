"""Seeded irregular front entrance construction."""

from __future__ import annotations

import math
import random

import cadquery as cq

from .config import GeckoHideConfig


def entrance_keepout(config: GeckoHideConfig) -> tuple[float, float, float, float]:
    """Return front layout keepout bounds as (min_x, max_x, min_z, max_z)."""
    half_width = config.entrance_width / 2 + 8.0
    return (
        config.entrance_offset_x - half_width,
        config.entrance_offset_x + half_width,
        0.0,
        config.entrance_height + 6.0,
    )


def create_entrance_cutout(config: GeckoHideConfig, rng: random.Random) -> cq.Shape:
    """Make an asymmetric arched prism that completely crosses the front wall."""
    width = config.entrance_width
    height = config.entrance_height
    left = -width / 2 * rng.uniform(0.97, 1.02)
    right = width / 2 * rng.uniform(0.97, 1.02)
    shoulder = height * rng.uniform(0.43, 0.53)
    points: list[tuple[float, float]] = [(left, 0.0), (left, shoulder)]
    # Ordered ellipse samples preserve a simple, non-self-intersecting profile.
    for index in range(7):
        angle = math.pi - math.pi * index / 6
        x = math.cos(angle) * (right - left) / 2
        z = shoulder + math.sin(angle) * (height - shoulder)
        if index not in (0, 6):
            z *= rng.uniform(0.97, 1.03)
            x *= rng.uniform(0.98, 1.02)
        points.append((x, z))
    points.extend([(right, 0.0), (left, 0.0)])
    # Start beyond the lower-wall bulge and traverse the full local wall
    # thickness rather than assuming the former flat front plane.
    front_start = -config.depth / 2 * (1 + config.shell_profile_jitter) - 3.0
    return (
        cq.Workplane("XZ", origin=(config.entrance_offset_x, front_start, 0.0))
        .polyline(points)
        .close()
        .extrude(-(config.wall_thickness + 8.0))
        .val()
    )
