"""PCHIP interpolation and superellipse sampling for profile-driven geometry."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

import numpy as np
from scipy.interpolate import PchipInterpolator

from .profile import ProfileDesign


@dataclass(frozen=True)
class ProfileCurves:
    """Monotone cubic boundary interpolators with local control-point behavior."""

    x_left: PchipInterpolator
    x_right: PchipInterpolator
    y_front: PchipInterpolator
    y_back: PchipInterpolator

    def at(self, z: float | np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Evaluate all four boundaries at one or more heights."""
        return self.x_left(z), self.x_right(z), self.y_front(z), self.y_back(z)


def make_profile_curves(profile: ProfileDesign) -> ProfileCurves:
    """Create non-overshooting local cubic interpolators for a validated profile."""
    levels = np.asarray(profile.z_levels, dtype=float)
    return ProfileCurves(
        x_left=PchipInterpolator(levels, profile.x_left),
        x_right=PchipInterpolator(levels, profile.x_right),
        y_front=PchipInterpolator(levels, profile.y_front),
        y_back=PchipInterpolator(levels, profile.y_back),
    )


def sample_heights(profile: ProfileDesign, resolution: str) -> np.ndarray:
    """Return the documented vertical sampling density for a preview or final shell."""
    if resolution == "preview":
        count = 18
    elif resolution == "final":
        count = 32
    else:
        raise ValueError("resolution must be 'preview' or 'final'")
    return np.linspace(0.0, profile.height, count)


def superellipse_points(
    center_x: float,
    center_y: float,
    half_width: float,
    half_depth: float,
    power: float,
    *,
    samples: int = 64,
) -> list[tuple[float, float]]:
    """Return a consistently ordered closed superellipse polygon without repetition."""
    if samples < 48:
        raise ValueError("superellipse requires at least 48 theta samples")
    if half_width <= 0 or half_depth <= 0:
        raise ValueError("superellipse half dimensions must be positive")
    if power < 2.0:
        raise ValueError("superellipse power must be at least 2.0")
    exponent = 2.0 / power
    points: list[tuple[float, float]] = []
    for theta in np.linspace(0.0, 2.0 * math.pi, samples, endpoint=False):
        cosine = math.cos(float(theta))
        sine = math.sin(float(theta))
        points.append((
            center_x + half_width * math.copysign(abs(cosine) ** exponent, cosine),
            center_y + half_depth * math.copysign(abs(sine) ** exponent, sine),
        ))
    return points


def boundary_derivatives(curves: ProfileCurves, heights: Iterable[float]) -> dict[str, np.ndarray]:
    """Evaluate the four profile slopes at heights for safety validation."""
    z = np.asarray(list(heights), dtype=float)
    return {
        "x_left": curves.x_left.derivative()(z),
        "x_right": curves.x_right.derivative()(z),
        "y_front": curves.y_front.derivative()(z),
        "y_back": curves.y_back.derivative()(z),
    }
