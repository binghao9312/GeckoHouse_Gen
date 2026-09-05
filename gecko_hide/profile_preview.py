"""Static inspection renders for authored profile curves."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .profile import ProfileDesign
from .profile_curve import make_profile_curves


def export_profile_plots(profile: ProfileDesign, output_dir: str | Path) -> tuple[Path, Path]:
    """Write front and side control-point plus PCHIP-curve PNGs."""
    profile.validate()
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    curves = make_profile_curves(profile)
    z = np.linspace(0.0, profile.height, 512)

    front_path = destination / "front_profile.png"
    figure, axes = plt.subplots(figsize=(8, 6), layout="constrained")
    axes.plot(curves.x_left(z), z, color="#286a9f", label="left boundary")
    axes.plot(curves.x_right(z), z, color="#286a9f", label="right boundary")
    axes.scatter(profile.x_left, profile.z_levels, color="#123c5a", zorder=3)
    axes.scatter(profile.x_right, profile.z_levels, color="#123c5a", zorder=3)
    left = profile.entrance_offset_x - profile.entrance_width / 2.0
    axes.add_patch(plt.Rectangle((left, 0.0), profile.entrance_width, profile.entrance_height,
                                 fill=False, linestyle="--", edgecolor="#b44428", label="entrance"))
    axes.set(xlabel="X (mm)", ylabel="Z (mm)", title="Front Profile", aspect="equal")
    axes.grid(alpha=0.25)
    axes.legend()
    figure.savefig(front_path, dpi=180)
    plt.close(figure)

    side_path = destination / "side_profile.png"
    figure, axes = plt.subplots(figsize=(8, 6), layout="constrained")
    axes.plot(curves.y_front(z), z, color="#3b8654", label="front boundary")
    axes.plot(curves.y_back(z), z, color="#3b8654", label="back boundary")
    axes.scatter(profile.y_front, profile.z_levels, color="#1d5230", zorder=3)
    axes.scatter(profile.y_back, profile.z_levels, color="#1d5230", zorder=3)
    axes.set(xlabel="Y (mm)", ylabel="Z (mm)", title="Side Profile", aspect="equal")
    axes.grid(alpha=0.25)
    axes.legend()
    figure.savefig(side_path, dpi=180)
    plt.close(figure)

    if not front_path.is_file() or not side_path.is_file():
        raise RuntimeError("profile preview export failed")
    return front_path, side_path
