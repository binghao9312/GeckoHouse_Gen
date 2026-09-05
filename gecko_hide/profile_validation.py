"""Validation rules that keep editable profiles printable before OCC is invoked."""

from __future__ import annotations

import math

import numpy as np

from .profile_curve import boundary_derivatives, make_profile_curves

_MIN_INTERIOR_CLEARANCE = 30.0
_MIN_WALL_THICKNESS = 3.5
_MAX_SECTION_ANGLE_DEGREES = 55.0


def validate_profile(profile: object) -> None:
    """Raise a clear ValueError when profile controls cannot make a safe shell."""
    height = float(profile.height)
    if not math.isfinite(height) or height <= 0:
        raise ValueError("profile height must be greater than zero")
    arrays = (profile.z_levels, profile.x_left, profile.x_right, profile.y_front, profile.y_back)
    if len(profile.z_levels) < 2 or any(len(values) != len(profile.z_levels) for values in arrays[1:]):
        raise ValueError("all four profile boundary arrays must match z_levels and contain at least two values")
    try:
        raw = np.asarray(arrays, dtype=float)
    except (TypeError, ValueError) as error:
        raise ValueError("profile control values must be numeric") from error
    if not np.isfinite(raw).all():
        raise ValueError("profile control values must be finite")
    levels = raw[0]
    if abs(levels[0]) > 1e-8 or abs(levels[-1] - height) > 1e-8:
        raise ValueError("z_levels must start at 0 and end at profile height")
    if np.any(np.diff(levels) <= 0):
        raise ValueError("z_levels must be strictly ascending")
    if not 2.0 <= profile.section_power <= 4.5:
        raise ValueError("section_power must be between 2.0 and 4.5")
    if profile.wall_thickness < _MIN_WALL_THICKNESS:
        raise ValueError(f"wall_thickness must be at least {_MIN_WALL_THICKNESS:.1f} mm")
    if profile.roof_thickness < 3.0 or profile.roof_thickness >= height:
        raise ValueError("roof_thickness must be at least 3.0 mm and below profile height")
    if profile.entrance_width <= 0 or profile.entrance_height <= 0:
        raise ValueError("entrance dimensions must be greater than zero")
    if profile.entrance_height >= height - profile.roof_thickness:
        raise ValueError("entrance_height does not fit below the roof")

    curves = make_profile_curves(profile)
    sample_z = np.linspace(0.0, height, 257)
    xl, xr, yf, yb = curves.at(sample_z)
    min_dimension = 2.0 * profile.wall_thickness + _MIN_INTERIOR_CLEARANCE
    if np.any(xr - xl < min_dimension):
        raise ValueError("profile x boundaries cross or leave insufficient interior width")
    if np.any(yb - yf < min_dimension):
        raise ValueError("profile y boundaries cross or leave insufficient interior depth")

    entrance_z = np.linspace(0.0, profile.entrance_height, 65)
    entrance_left = profile.entrance_offset_x - profile.entrance_width / 2.0
    entrance_right = profile.entrance_offset_x + profile.entrance_width / 2.0
    local_left = curves.x_left(entrance_z) + profile.wall_thickness
    local_right = curves.x_right(entrance_z) - profile.wall_thickness
    if np.any(entrance_left <= local_left) or np.any(entrance_right >= local_right):
        raise ValueError("entrance does not fit inside the front profile side walls")

    slopes = boundary_derivatives(curves, sample_z)
    max_slope = max(float(np.max(np.abs(values))) for values in slopes.values())
    max_angle = math.degrees(math.atan(max_slope))
    if max_angle > _MAX_SECTION_ANGLE_DEGREES:
        raise ValueError(
            f"profile slope angle {max_angle:.1f}° exceeds {_MAX_SECTION_ANGLE_DEGREES:.0f}° relative to vertical"
        )


