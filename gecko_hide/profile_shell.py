"""Continuous, profile-driven structural shell construction."""

from __future__ import annotations

import cadquery as cq
import numpy as np

from .profile import ProfileDesign
from .profile_curve import make_profile_curves, sample_heights, superellipse_points
from .shell import safe_cut
from .validation import validate_shape


def _wire_at(
    z: float,
    *,
    x_left: float,
    x_right: float,
    y_front: float,
    y_back: float,
    section_power: float,
) -> cq.Shape:
    """Build one consistently ordered XY superellipse wire at a sampled height."""
    center_x = (x_left + x_right) / 2.0
    center_y = (y_front + y_back) / 2.0
    return (
        cq.Workplane("XY", origin=(0.0, 0.0, z))
        .polyline(superellipse_points(center_x, center_y, (x_right - x_left) / 2.0, (y_back - y_front) / 2.0, section_power))
        .close()
        .val()
    )


def _loft(wires: list[cq.Shape], label: str) -> cq.Shape:
    """Create one smooth, valid CadQuery solid from matching closed wires."""
    try:
        result = cq.Solid.makeLoft(wires, ruled=False).clean()
    except Exception as error:
        raise ValueError(f"{label} loft failed: {error}") from error
    if not result.isValid() or len(result.Solids()) != 1 or result.Volume() <= 0:
        raise ValueError(f"{label} loft is not one valid positive-volume solid")
    return result


def build_outer_from_profiles(profile: ProfileDesign, resolution: str = "final") -> cq.Shape:
    """Loft PCHIP-sampled superellipses into the deterministic outer structural body."""
    profile.validate()
    curves = make_profile_curves(profile)
    heights = sample_heights(profile, resolution)
    xl, xr, yf, yb = curves.at(heights)
    wires = [
        _wire_at(
            float(z), x_left=float(left), x_right=float(right), y_front=float(front), y_back=float(back),
            section_power=profile.section_power,
        )
        for z, left, right, front, back in zip(heights, xl, xr, yf, yb, strict=True)
    ]
    return _loft(wires, "profile outer shell")


def build_inner_from_profiles(profile: ProfileDesign, resolution: str = "final") -> cq.Shape:
    """Loft the inward-offset profile cavity from below the open bottom to its roof."""
    profile.validate()
    curves = make_profile_curves(profile)
    count = len(sample_heights(profile, resolution))
    top = profile.height - profile.roof_thickness
    heights = np.linspace(-0.5, top, count)
    curve_heights = np.maximum(heights, 0.0)
    xl, xr, yf, yb = curves.at(curve_heights)
    wall = profile.wall_thickness
    wires = [
        _wire_at(
            float(z), x_left=float(left + wall), x_right=float(right - wall),
            y_front=float(front + wall), y_back=float(back - wall), section_power=profile.section_power,
        )
        for z, left, right, front, back in zip(heights, xl, xr, yf, yb, strict=True)
    ]
    return _loft(wires, "profile inner cavity")


def build_profile_shell(profile: ProfileDesign, resolution: str = "final") -> cq.Shape:
    """Return a monolithic, smooth, open-bottom shell with a continuous roof."""
    outer = build_outer_from_profiles(profile, resolution)
    inner = build_inner_from_profiles(profile, resolution)
    shell = safe_cut(outer, inner)
    validate_shape(shell)
    return shell
