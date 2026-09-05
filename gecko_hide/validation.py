"""CadQuery and trimesh acceptance checks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import trimesh

from .config import GeckoHideConfig


@dataclass(frozen=True)
class MeshValidation:
    watertight: bool
    components: int
    volume: float
    bounds: tuple[tuple[float, float, float], tuple[float, float, float]]
    triangle_count: int


def validate_shape(shape: object) -> None:
    if not shape.isValid():
        raise ValueError("CadQuery shape is invalid")
    if len(shape.Solids()) != 1:
        raise ValueError("CadQuery shape does not contain exactly one solid")
    if shape.Volume() <= 0:
        raise ValueError("CadQuery shape has no volume")


def validate_stl(path: str | Path, config: GeckoHideConfig) -> MeshValidation:
    mesh = trimesh.load_mesh(Path(path), force="mesh", process=True)
    if not isinstance(mesh, trimesh.Trimesh) or len(mesh.faces) == 0:
        raise ValueError("STL has no triangle mesh")
    if not np.isfinite(mesh.vertices).all():
        raise ValueError("STL contains non-finite vertices")
    if not mesh.is_watertight:
        raise ValueError("STL is not watertight")
    components = len(mesh.split(only_watertight=False))
    if components != 1:
        raise ValueError(f"STL has {components} connected components, expected one")
    if mesh.volume <= 0:
        raise ValueError("STL has zero volume")
    lower, upper = mesh.bounds
    if abs(float(lower[2])) > 0.05:
        raise ValueError(f"STL bottom is not at Z=0: {lower[2]:.4f}")
    if upper[0] - lower[0] > config.width + 20.0 or upper[1] - lower[1] > config.depth + 20.0:
        raise ValueError("STL XY bounding box exceeds rock allowance")
    if upper[2] > config.height + 12.0 + 0.05:
        raise ValueError("STL height exceeds roof rock allowance")
    return MeshValidation(
        watertight=True,
        components=components,
        volume=float(mesh.volume),
        bounds=(tuple(map(float, lower)), tuple(map(float, upper))),
        triangle_count=len(mesh.faces),
    )


def validate_step(path: str | Path, source_shape: object) -> None:
    """Round-trip a STEP file through OpenCascade before it is offered to users."""
    import cadquery as cq

    source_volume = float(source_shape.Volume())
    try:
        imported = cq.importers.importStep(str(path)).val()
    except Exception as error:
        raise ValueError(f"STEP cannot be imported after export: {error}") from error
    validate_shape(imported)
    if not np.isfinite(imported.Volume()):
        raise ValueError("STEP has a non-finite volume")
    if not np.isclose(imported.Volume(), source_volume, rtol=1e-4, atol=0.1):
        raise ValueError(
            f"STEP round-trip volume differs from source: {imported.Volume():.3f} vs {source_volume:.3f}"
        )
