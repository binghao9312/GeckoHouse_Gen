"""Load-bearing shell and defensive CadQuery Boolean helpers."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
import math
import random
import warnings

import cadquery as cq

from .config import GeckoHideConfig


def safe_fillet(shape: cq.Shape, radius: float, selector: str = "|Z") -> cq.Shape:
    """Apply a non-essential fillet, reducing its radius before giving up."""
    for candidate in (radius, radius * 0.65, radius * 0.35):
        if candidate <= 0.05:
            continue
        try:
            return cq.Workplane("XY").newObject([shape]).edges(selector).fillet(candidate).val()
        except Exception:
            pass
    return shape


def safe_cut(body: cq.Shape, cutter: cq.Shape) -> cq.Shape:
    """Structural cuts are mandatory: surface OCC failures to the caller."""
    result = body.cut(cutter)
    if not result.isValid():
        raise ValueError("CadQuery produced an invalid structural cut")
    return result.clean()


def safe_union(body: cq.Shape, additions: Iterable[cq.Shape]) -> cq.Shape:
    """Fuse overlapping decorative solids; skip an individual failed addition."""
    result = body
    for addition in additions:
        try:
            candidate = result.fuse(addition).clean()
            if candidate.isValid() and len(candidate.Solids()) == 1:
                result = candidate
            else:
                warnings.warn("skipping decorative rock that did not fuse into one solid", RuntimeWarning)
        except Exception as error:
            # An optional rock never compromises the printable structural body.
            warnings.warn(f"skipping decorative rock after Boolean failure: {error}", RuntimeWarning)
    return result


def _rounded_rectangle_points(width: float, depth: float, corner_radius: float) -> list[tuple[float, float]]:
    """Return a consistently ordered, gently rounded rectangular profile."""
    radius = min(corner_radius, width / 2 - 0.01, depth / 2 - 0.01)
    if radius <= 0:
        raise ValueError("rounded profile dimensions are too small for its corner radius")
    points: list[tuple[float, float]] = []
    for center_x, center_y, start_angle in (
        (width / 2 - radius, depth / 2 - radius, 0.0),
        (-width / 2 + radius, depth / 2 - radius, math.pi / 2),
        (-width / 2 + radius, -depth / 2 + radius, math.pi),
        (width / 2 - radius, -depth / 2 + radius, 3 * math.pi / 2),
    ):
        for index in range(7):
            angle = start_angle + index * math.pi / 12
            points.append((center_x + radius * math.cos(angle), center_y + radius * math.sin(angle)))
    return points


def create_rounded_profile(
    width: float,
    depth: float,
    corner_radius: float,
    z: float,
    x_offset: float = 0.0,
    y_offset: float = 0.0,
) -> cq.Shape:
    """Create a horizontal rounded profile wire for a stable multi-section loft."""
    if width <= 0 or depth <= 0:
        raise ValueError("rounded profile dimensions must be positive")
    return (
        cq.Workplane("XY", origin=(x_offset, y_offset, z))
        .polyline(_rounded_rectangle_points(width, depth, corner_radius))
        .close()
        .val()
    )


def safe_loft(
    profile_factory: Callable[[float], Sequence[cq.Shape]],
    *,
    label: str,
) -> cq.Shape:
    """Build and validate a smooth loft, reducing non-essential jitter on retry."""
    errors: list[Exception] = []
    for jitter_scale in (1.0, 0.5, 0.0):
        try:
            result = cq.Solid.makeLoft(list(profile_factory(jitter_scale)), ruled=False).clean()
            if result.isValid() and len(result.Solids()) == 1 and result.Volume() > 0:
                return result
            raise ValueError("loft was not one valid positive-volume solid")
        except Exception as error:
            errors.append(error)
    raise ValueError(f"{label} smooth loft failed after reduced-jitter retries: {errors[-1]}")


def create_shell(config: GeckoHideConfig, rng: random.Random | None = None) -> cq.Shape:
    """Return an open-bottom hollow shell with a subtly asymmetric domed shoulder."""
    config.validate()
    rng = rng or random.Random(config.seed)

    lower_width_scale = 1.0 + rng.uniform(config.shell_profile_jitter * 0.4, config.shell_profile_jitter)
    lower_depth_scale = 1.0 + rng.uniform(config.shell_profile_jitter * 0.4, config.shell_profile_jitter)
    upper_width_scale = rng.uniform(0.96, 0.99)
    upper_depth_scale = rng.uniform(0.95, 0.98)
    top_width_scale = rng.uniform(config.shell_top_shrink_min, config.shell_top_shrink_max)
    top_depth_scale = rng.uniform(config.shell_top_shrink_min, config.shell_top_shrink_max)
    profile_offsets = (
        (0.0, 0.0),
        (rng.uniform(-config.shell_center_offset_max, config.shell_center_offset_max),
         rng.uniform(-config.shell_center_offset_max, config.shell_center_offset_max)),
        (rng.uniform(-config.shell_center_offset_max, config.shell_center_offset_max),
         rng.uniform(-config.shell_center_offset_max, config.shell_center_offset_max)),
        (rng.uniform(-config.shell_center_offset_max, config.shell_center_offset_max),
         rng.uniform(-config.shell_center_offset_max, config.shell_center_offset_max)),
    )
    outer_dimensions = (
        (config.width, config.depth, 0.0),
        (config.width * lower_width_scale, config.depth * lower_depth_scale, config.height * 0.35),
        (config.width * upper_width_scale, config.depth * upper_depth_scale, config.height * 0.72),
        (config.width * top_width_scale, config.depth * top_depth_scale, config.height),
    )

    def profiles(jitter_scale: float, *, inner: bool = False) -> list[cq.Shape]:
        result: list[cq.Shape] = []
        for index, (width, depth, z) in enumerate(outer_dimensions):
            if inner:
                width -= 2 * config.wall_thickness
                depth -= 2 * config.wall_thickness
                if index == 0:
                    z = -0.75 if config.bottom_open else config.wall_thickness
                elif index == len(outer_dimensions) - 1:
                    z = config.height - config.roof_thickness
            x_offset, y_offset = profile_offsets[index]
            radius = min(16.0, width * 0.10, depth * 0.10)
            if inner:
                radius = max(2.0, radius - config.wall_thickness / 2)
            result.append(
                create_rounded_profile(
                    width,
                    depth,
                    radius,
                    z,
                    x_offset * jitter_scale,
                    y_offset * jitter_scale,
                )
            )
        return result

    outer = safe_loft(lambda jitter_scale: profiles(jitter_scale), label="structural outer shell")
    inner = safe_loft(lambda jitter_scale: profiles(jitter_scale, inner=True), label="structural cavity")
    shell = safe_cut(outer, inner)
    if not shell.isValid() or len(shell.Solids()) != 1:
        raise ValueError("structural shell is not one valid solid")
    return shell
