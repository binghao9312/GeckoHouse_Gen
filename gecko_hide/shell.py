"""Load-bearing shell and defensive CadQuery Boolean helpers."""

from __future__ import annotations

from collections.abc import Iterable
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


def create_shell(config: GeckoHideConfig) -> cq.Shape:
    """Return an open-bottom hollow rounded rectangular structural shell."""
    config.validate()
    outer = cq.Workplane("XY").box(
        config.width, config.depth, config.height, centered=(True, True, False)
    ).val()
    outer_radius = min(8.0, config.width * 0.04, config.depth * 0.04)
    outer = safe_fillet(outer, outer_radius, "|Z")

    inner_height = config.height - config.roof_thickness
    inner_z = -0.5 if config.bottom_open else config.wall_thickness
    if config.bottom_open:
        inner_height += 1.0
    else:
        inner_height -= config.wall_thickness
    inner = cq.Workplane("XY").box(
        config.width - 2 * config.wall_thickness,
        config.depth - 2 * config.wall_thickness,
        inner_height,
        centered=(True, True, False),
    ).translate((0, 0, inner_z)).val()
    shell = safe_cut(outer, inner)
    if not shell.isValid() or len(shell.Solids()) != 1:
        raise ValueError("structural shell is not one valid solid")
    return shell
