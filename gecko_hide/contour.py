"""Editable V4 topographic contour design data."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

CONTOUR_VERSION = 2
DEFAULT_LEVEL_RATIOS = (0.00, 0.18, 0.36, 0.54, 0.70, 0.85, 1.00)


@dataclass
class ContourLevel:
    """One closed XY control loop at a fixed height."""

    z: float
    points: list[list[float]]
    # Mode describes the transition from the preceding level into this one.
    # The base has no preceding transition and is always smooth.
    surface_mode: str = "smooth"
    manually_modified: bool = False

    def copy(self) -> "ContourLevel":
        return replace(self, points=[point.copy() for point in self.points])


@dataclass
class ContourDesign:
    """V4 editable mountain design expressed as nested closed XY contours."""

    height: float
    wall_thickness: float = 4.0
    roof_thickness: float = 5.0
    summit: list[float] = field(default_factory=lambda: [12.0, 5.0])
    levels: list[ContourLevel] = field(default_factory=list)
    entrance_width: float = 55.0
    entrance_height: float = 40.0
    entrance_offset: float = -30.0
    ring_clearance: float = 2.0
    max_local_slope_deg: float = 55.0

    @classmethod
    def default(cls, *, width: float = 180.0, depth: float = 120.0, height: float = 75.0) -> "ContourDesign":
        """Return the documented asymmetric 12-point hill footprint and levels."""
        if min(width, depth, height) <= 0:
            raise ValueError("width, depth, and height must be greater than zero")
        angles = np.linspace(0.0, 2.0 * math.pi, 12, endpoint=False)
        # Fixed modulation makes the organic footprint reproducible while retaining a
        # stable cyclic point order for editing.
        radii = np.array((1.00, 1.05, 0.96, 1.03, 0.98, 1.06, 1.00, 0.94, 1.02, 0.97, 1.04, 0.96))
        footprint = [[float(width * 0.5 * radius * math.cos(angle)),
                      float(depth * 0.5 * radius * math.sin(angle))]
                     for angle, radius in zip(angles, radii, strict=True)]
        design = cls(
            height=height,
            summit=[width / 15.0, depth / 24.0],
            entrance_width=55.0 * width / 180.0,
            entrance_height=40.0 * min(width / 180.0, height / 75.0),
            entrance_offset=-width / 6.0,
        )
        design.levels = generate_contours(footprint, height=height, summit=design.summit)
        design.validate()
        return design

    @property
    def footprint(self) -> ContourLevel:
        return self.levels[0]

    def generate_contours(self, *, replace_modified: bool = False) -> None:
        """Regenerate auto levels while preserving manual edits unless requested."""
        generated = generate_contours(self.footprint.points, height=self.height, summit=self.summit)
        if self.levels and not replace_modified:
            previous = {round(level.z / self.height, 8): level for level in self.levels}
            for index, level in enumerate(generated):
                saved = previous.get(round(level.z / self.height, 8))
                if saved is not None and saved.manually_modified:
                    generated[index] = saved.copy()
        self.levels = generated
        self.validate()

    def as_dict(self) -> dict[str, Any]:
        """Return the stable V2 JSON representation with editable control points."""
        return {
            "version": CONTOUR_VERSION,
            "height": self.height,
            "wall_thickness": self.wall_thickness,
            "roof_thickness": self.roof_thickness,
            "summit": self.summit.copy(),
            "levels": [
                {"z": level.z, "points": [point.copy() for point in level.points],
                 "surface_mode": level.surface_mode, "manually_modified": level.manually_modified}
                for level in self.levels
            ],
            "entrance": {"width": self.entrance_width, "height": self.entrance_height, "offset": self.entrance_offset},
            "ring_clearance": self.ring_clearance,
            "max_local_slope_deg": self.max_local_slope_deg,
        }

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> "ContourDesign":
        """Decode a V2 design without silently discarding unknown fields."""
        payload = dict(values)
        version = payload.pop("version", None)
        if version != CONTOUR_VERSION:
            raise ValueError(f"unsupported contour design version: {version!r}; expected {CONTOUR_VERSION}")
        entrance = payload.pop("entrance", None)
        if not isinstance(entrance, Mapping) or set(entrance) != {"width", "height", "offset"}:
            raise ValueError("contour entrance must contain width, height, and offset")
        expected = {"height", "wall_thickness", "roof_thickness", "summit", "levels", "ring_clearance", "max_local_slope_deg"}
        if set(payload) != expected:
            unknown = set(payload) - expected
            missing = expected - set(payload)
            details: list[str] = []
            if unknown:
                details.append(f"unknown contour keys: {', '.join(sorted(unknown))}")
            if missing:
                details.append(f"missing contour keys: {', '.join(sorted(missing))}")
            raise ValueError("; ".join(details))
        raw_levels = payload.pop("levels")
        if not isinstance(raw_levels, Sequence):
            raise ValueError("contour levels must be an array")
        levels: list[ContourLevel] = []
        for raw in raw_levels:
            if (not isinstance(raw, Mapping) or set(raw) - {"z", "points", "surface_mode", "manually_modified"}
                    or {"z", "points"} - set(raw)):
                raise ValueError("each contour level must contain z and points")
            levels.append(ContourLevel(
                float(raw["z"]),
                [[float(x), float(y)] for x, y in raw["points"]],
                str(raw.get("surface_mode", "smooth")),
                bool(raw.get("manually_modified", False)),
            ))
        design = cls(**payload, levels=levels, entrance_width=float(entrance["width"]),
                     entrance_height=float(entrance["height"]), entrance_offset=float(entrance["offset"]))
        design.validate()
        return design

    def validate(self) -> None:
        """Validate editable topography before CadQuery is invoked."""
        from .contour_validation import validate_contour_design

        validate_contour_design(self)


def generate_contours(footprint: Sequence[Sequence[float]], *, height: float, summit: Sequence[float],
                      ratios: Sequence[float] = DEFAULT_LEVEL_RATIOS) -> list[ContourLevel]:
    """Generate nested, shifted, non-linear contour levels from one closed footprint."""
    points = np.asarray(footprint, dtype=float)
    if points.ndim != 2 or points.shape[1] != 2:
        raise ValueError("footprint points must be XY pairs")
    centroid = points.mean(axis=0)
    peak = np.asarray(summit, dtype=float)
    levels: list[ContourLevel] = []
    for ratio in ratios:
        # Slow lower changes, progressively tighter upper rings, and a finite top loop.
        center = centroid + float(ratio) * (peak - centroid)
        scale = 0.25 + 0.75 * (1.0 - float(ratio) ** 1.1)
        ring = center + scale * (points - centroid)
        levels.append(ContourLevel(z=float(ratio) * height,
                                   points=[[float(x), float(y)] for x, y in ring]))
    return levels



def scale_design(design: ContourDesign, factor: float) -> ContourDesign:
    """Uniformly scale all authored V4 geometry and manufacturing dimensions."""
    if factor <= 0:
        raise ValueError("design scale must be greater than zero")
    scaled = replace(
        design,
        height=design.height * factor,
        wall_thickness=design.wall_thickness * factor,
        roof_thickness=design.roof_thickness * factor,
        summit=[value * factor for value in design.summit],
        levels=[ContourLevel(level.z * factor, [[value * factor for value in point] for point in level.points],
                             level.surface_mode, level.manually_modified) for level in design.levels],
        entrance_width=design.entrance_width * factor,
        entrance_height=design.entrance_height * factor,
        entrance_offset=design.entrance_offset * factor,
        ring_clearance=design.ring_clearance * factor,
    )
    scaled.validate()
    return scaled

def load_design(path: str | Path) -> ContourDesign:
    """Load and validate a V4 editable contour design."""
    source = Path(path)
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except OSError as error:
        raise ValueError(f"cannot read design {source}: {error}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid design JSON in {source}: {error.msg}") from error
    if not isinstance(data, Mapping):
        raise ValueError("design JSON root must be an object")
    return ContourDesign.from_mapping(data)


def save_design(design: ContourDesign, path: str | Path) -> Path:
    """Validate and write a deterministic editable V4 contour design."""
    design.validate()
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(design.as_dict(), indent=2) + "\n", encoding="utf-8")
    return destination
