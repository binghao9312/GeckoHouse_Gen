"""CadQuery STL and STEP export."""

from __future__ import annotations

from pathlib import Path

import cadquery as cq

from .config import GeckoHideConfig


def export_model(
    shape: cq.Shape,
    config: GeckoHideConfig,
    output_dir: str | Path,
    *,
    stem: str | None = None,
) -> tuple[Path, Path]:
    """Export FDM-resolution STL and editable STEP, raising on any failure."""
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    stem = stem or f"gecko_hide_seed_{config.seed}"
    stl_path = destination / f"{stem}.stl"
    step_path = destination / f"{stem}.step"
    cq.exporters.export(shape, str(stl_path), tolerance=0.15, angularTolerance=0.1)
    cq.exporters.export(shape, str(step_path))
    if not stl_path.is_file() or stl_path.stat().st_size == 0:
        raise RuntimeError("STL export did not create a non-empty file")
    if not step_path.is_file() or step_path.stat().st_size == 0:
        raise RuntimeError("STEP export did not create a non-empty file")
    return stl_path, step_path
