"""Deterministic shallow textured-STL relief for a V5 structural shell."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import trimesh

from .contour import ContourDesign


def export_textured_stl(structural_stl: Path, destination: Path, design: ContourDesign) -> Path:
    """Displace only outward-facing shell vertices into a shallow, closed mesh texture.

    This is intentionally STL-only: the CadQuery STEP remains the exact untextured
    structural BREP. The displacement is continuous at every cell boundary, so the
    mesh remains one watertight shell rather than a collection of detached stones.
    """
    mesh = trimesh.load_mesh(structural_stl, force="mesh", process=True)
    if not isinstance(mesh, trimesh.Trimesh) or not mesh.is_watertight:
        raise ValueError("structural STL must be a watertight mesh before relief is added")
    vertices = mesh.vertices.copy()
    normals = mesh.vertex_normals
    radial = vertices[:, :2] - vertices[:, :2].mean(axis=0)
    radial_length = np.linalg.norm(radial, axis=1)
    radial_unit = np.divide(radial, radial_length[:, None], out=np.zeros_like(radial), where=radial_length[:, None] > 1e-6)
    exterior = (np.einsum("ij,ij->i", normals[:, :2], radial_unit) > 0.45) & (vertices[:, 2] > 1.0)
    rng = np.random.default_rng(design.appearance.relief_seed)
    phases = rng.uniform(0.0, 2.0 * np.pi, size=4)
    angle = np.arctan2(radial[:, 1], radial[:, 0])
    height = vertices[:, 2] / design.height
    scale = design.appearance.relief_scale
    pattern = (
        np.sin(angle * (5.0 * scale) + phases[0])
        + np.sin(height * (8.0 * scale) + phases[1])
        + 0.55 * np.sin(angle * (3.0 * scale) - height * (11.0 * scale) + phases[2])
        + 0.35 * np.sin(angle * (9.0 * scale) + height * (5.0 * scale) + phases[3])
    ) / 2.9
    # Rounded positive lobes preserve narrow shallow seams on the structural shell.
    relief = np.maximum(0.0, pattern - 0.16) / 0.84 * design.appearance.relief_depth
    vertices[exterior] += normals[exterior] * relief[exterior, None]
    mesh.vertices = vertices
    if not mesh.is_watertight or not np.isfinite(mesh.vertices).all():
        raise ValueError("textured STL relief is not watertight")
    destination.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(destination)
    return destination
