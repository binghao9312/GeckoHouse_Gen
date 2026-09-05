"""Render an isometric PNG preview of a generated gecko-hide STL."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import trimesh


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render an isometric gecko-hide STL preview.")
    parser.add_argument("stl", type=Path)
    parser.add_argument("--output", type=Path)
    return parser


def render_preview(stl_path: Path, output_path: Path | None = None) -> Path:
    """Render a front/side/roof isometric image without opening a GUI."""
    mesh = trimesh.load_mesh(stl_path, force="mesh", process=False)
    if not isinstance(mesh, trimesh.Trimesh) or len(mesh.faces) == 0:
        raise ValueError("STL has no triangle mesh to render")
    output_path = output_path or stl_path.with_name(f"{stl_path.stem}_preview.png")
    points, face_indices = trimesh.sample.sample_surface(mesh, 300_000, seed=12_345)
    normals = mesh.face_normals[face_indices]
    light = np.array((-0.45, -0.35, 0.82))
    light /= np.linalg.norm(light)
    intensity = np.clip(0.25 + 0.75 * (normals @ light + 1.0) / 2.0, 0.16, 0.94)
    colors = np.column_stack((0.18 * intensity, 0.34 * intensity, 0.23 * intensity, np.ones_like(intensity)))

    figure = plt.figure(figsize=(10, 8), facecolor="#f5f1e8")
    axes = figure.add_subplot(111, projection="3d", facecolor="#f5f1e8")
    # Area-weighted sampling retains both broad shell surfaces and fine rock
    # curvature while avoiding a heavyweight interactive renderer.
    axes.scatter(points[:, 0], points[:, 1], points[:, 2], c=colors, marker="s", s=1.0, depthshade=False)
    lower, upper = mesh.bounds
    axes.set_xlim(lower[0], upper[0])
    axes.set_ylim(lower[1], upper[1])
    axes.set_zlim(lower[2], upper[2])
    axes.set_box_aspect(upper - lower)
    axes.view_init(elev=26, azim=-54)
    axes.set_axis_off()
    figure.subplots_adjust(0, 0, 1, 1)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=180, facecolor=figure.get_facecolor(), bbox_inches="tight", pad_inches=0.02)
    plt.close(figure)
    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise RuntimeError("preview renderer did not create a non-empty PNG")
    return output_path


def main() -> int:
    args = _parser().parse_args()
    print(render_preview(args.stl, args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
