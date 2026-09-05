"""Canonical V5 contour-stack design and synchronized editing operations."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import json
import math
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence

import numpy as np

CONTOUR_VERSION = 3
DEFAULT_LEVEL_HEIGHTS = (0.0, 12.0, 24.0, 38.0, 50.0, 58.0, 68.0, 75.0)
LevelRole = Literal["wall", "roof_shoulder", "roof_top"]


@dataclass
class ContourLevel:
    """One closed XY control loop at a fixed height in the canonical stack."""

    z: float
    points: list[list[float]]
    # Mode describes the transition from the preceding level into this one.
    surface_mode: str = "smooth"
    manually_modified: bool = False
    role: LevelRole = "wall"
    z_locked: bool = False
    shape_locked: bool = False

    def copy(self) -> "ContourLevel":
        return replace(self, points=[point.copy() for point in self.points])


@dataclass
class AppearanceSettings:
    """Optional surface-relief settings; macro geometry never depends on its seed."""

    relief_enabled: bool = False
    relief_seed: int = 12_345
    relief_depth: float = 1.5
    relief_gap: float = 1.5
    relief_scale: float = 1.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "relief_enabled": self.relief_enabled,
            "relief_seed": self.relief_seed,
            "relief_depth": self.relief_depth,
            "relief_gap": self.relief_gap,
            "relief_scale": self.relief_scale,
        }


@dataclass
class ContourDesign:
    """V5 editable rock shelter represented by one stack of closed XY contours."""

    height: float
    wall_thickness: float = 4.0
    roof_thickness: float = 5.0
    summit: list[float] = field(default_factory=lambda: [4.0, 2.0])
    levels: list[ContourLevel] = field(default_factory=list)
    entrance_width: float = 55.0
    entrance_height: float = 40.0
    entrance_offset: float = -30.0
    entrance_profile: list[list[float]] = field(default_factory=list)
    ring_clearance: float = 2.0
    max_local_slope_deg: float = 55.0
    max_overhang_xy: float = 8.0
    max_overhang_ratio: float = 0.08
    min_level_spacing: float = 4.0
    appearance: AppearanceSettings = field(default_factory=AppearanceSettings)

    @classmethod
    def default(cls, *, width: float = 180.0, depth: float = 120.0, height: float = 75.0) -> "ContourDesign":
        """Return an asymmetric, full-walled rock shelter with a broad roof cap."""
        if min(width, depth, height) <= 0:
            raise ValueError("width, depth, and height must be greater than zero")
        angles = np.linspace(0.0, 2.0 * math.pi, 12, endpoint=False)
        radii = np.array((1.00, 1.05, 0.96, 1.03, 0.98, 1.06, 1.00, 0.94, 1.02, 0.97, 1.04, 0.96))
        footprint = np.column_stack((
            width * 0.5 * radii * np.cos(angles),
            depth * 0.5 * radii * np.sin(angles),
        ))
        scale_height = height / 75.0
        scales = ((1.00, 1.00), (1.01, 1.00), (1.00, 0.99), (0.99, 0.98),
                  (0.97, 0.96), (1.025, 1.025), (1.00, 0.98), (0.92, 0.90))
        shifts = ((0.0, 0.0), (-0.8, 0.3), (-1.2, 0.0), (-0.5, 0.5), (0.4, 0.7),
                  (2.0, 1.5), (3.0, 2.1), (3.2, 2.4))
        roles: tuple[LevelRole, ...] = ("wall", "wall", "wall", "wall", "wall", "roof_shoulder", "roof_top", "roof_top")
        levels = []
        for index, (z, (x_scale, y_scale), (shift_x, shift_y), role) in enumerate(
            zip(DEFAULT_LEVEL_HEIGHTS, scales, shifts, roles, strict=True)
        ):
            ring = footprint * np.array((x_scale, y_scale)) + np.array((shift_x * width / 180.0, shift_y * depth / 120.0))
            levels.append(ContourLevel(
                z=z * scale_height,
                points=[[float(x), float(y)] for x, y in ring],
                role=role,
                z_locked=index in {0, len(DEFAULT_LEVEL_HEIGHTS) - 1},
            ))
        entrance_width = 55.0 * width / 180.0
        entrance_height = 40.0 * min(width / 180.0, scale_height)
        design = cls(
            height=height,
            summit=[4.0 * width / 180.0, 2.8 * depth / 120.0],
            levels=levels,
            entrance_width=entrance_width,
            entrance_height=entrance_height,
            entrance_offset=-width / 6.0,
            entrance_profile=_default_entrance_profile(entrance_width, entrance_height),
        )
        design.validate()
        return design

    @property
    def footprint(self) -> ContourLevel:
        return self.levels[0]

    def generate_contours(self, *, replace_modified: bool = False) -> None:
        """Restore V5's authored shelter stack while retaining manual levels by height."""
        generated = self.default(width=self.width, depth=self.depth, height=self.height).levels
        if self.levels and not replace_modified:
            previous = {round(level.z / self.height, 8): level for level in self.levels}
            for index, level in enumerate(generated):
                saved = previous.get(round(level.z / self.height, 8))
                if saved is not None and saved.manually_modified:
                    generated[index] = saved.copy()
        self.levels = generated
        self.validate()

    @property
    def width(self) -> float:
        return _bounds(self.footprint.points)[1] - _bounds(self.footprint.points)[0]

    @property
    def depth(self) -> float:
        return _bounds(self.footprint.points, axis=1)[1] - _bounds(self.footprint.points, axis=1)[0]

    def level_bounds(self, index: int, *, axis: int) -> tuple[float, float]:
        """Return sampled X or Y extrema used by the Front and Side editors."""
        from .contour_shell import sample_contour

        ring = sample_contour(self.levels[index].points, count=192)
        return float(ring[:, axis].min()), float(ring[:, axis].max())

    def set_level_bounds(self, index: int, *, axis: int, lower: float, upper: float) -> None:
        """Affinely remap canonical control points to requested Front or Side extrema."""
        if not lower < upper:
            raise ValueError("contour bounds must have positive extent")
        level = self.levels[index]
        if level.shape_locked:
            raise ValueError("selected contour shape is locked")
        old_lower, old_upper = self.level_bounds(index, axis=axis)
        extent = old_upper - old_lower
        if extent <= 1e-9:
            raise ValueError("contour extent is too small to edit")
        requested = upper - lower
        for point in level.points:
            point[axis] = lower + (point[axis] - old_lower) / extent * requested
        level.manually_modified = True
        self.validate()

    def translate_level(self, index: int, *, axis: int, center: float) -> None:
        """Translate a contour in X or Y without altering its Front/Side extent."""
        level = self.levels[index]
        if level.shape_locked:
            raise ValueError("selected contour shape is locked")
        lower, upper = self.level_bounds(index, axis=axis)
        delta = center - (lower + upper) / 2.0
        for point in level.points:
            point[axis] += delta
        level.manually_modified = True
        self.validate()

    def set_level_z(self, index: int, z: float) -> None:
        """Move an intermediate contour only within its ordered minimum-spacing window."""
        level = self.levels[index]
        if level.z_locked:
            raise ValueError("selected contour Z is locked")
        if index == 0 or index == len(self.levels) - 1:
            raise ValueError("base and roof top Z are fixed")
        lower = self.levels[index - 1].z + self.min_level_spacing
        upper = self.levels[index + 1].z - self.min_level_spacing
        if not lower <= z <= upper:
            raise ValueError(f"level Z must remain between {lower:g} and {upper:g} mm")
        level.z = float(z)
        level.manually_modified = True
        self.validate()

    def as_dict(self) -> dict[str, Any]:
        """Return deterministic V5 JSON preserving the canonical editable stack."""
        return {
            "version": CONTOUR_VERSION,
            "height": self.height,
            "wall_thickness": self.wall_thickness,
            "roof_thickness": self.roof_thickness,
            "summit": self.summit.copy(),
            "levels": [
                {
                    "z": level.z,
                    "points": [point.copy() for point in level.points],
                    "surface_mode": level.surface_mode,
                    "manually_modified": level.manually_modified,
                    "role": level.role,
                    "z_locked": level.z_locked,
                    "shape_locked": level.shape_locked,
                }
                for level in self.levels
            ],
            "entrance": {
                "width": self.entrance_width,
                "height": self.entrance_height,
                "offset": self.entrance_offset,
                "profile": [point.copy() for point in self.entrance_profile],
            },
            "ring_clearance": self.ring_clearance,
            "max_local_slope_deg": self.max_local_slope_deg,
            "max_overhang_xy": self.max_overhang_xy,
            "max_overhang_ratio": self.max_overhang_ratio,
            "min_level_spacing": self.min_level_spacing,
            "appearance": self.appearance.as_dict(),
        }

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> "ContourDesign":
        """Decode V5 JSON and explicitly migrate retained V2 contour designs."""
        payload = dict(values)
        version = payload.pop("version", None)
        if version == 2:
            return cls._from_v2(payload)
        if version != CONTOUR_VERSION:
            raise ValueError(f"unsupported contour design version: {version!r}; expected 2 or {CONTOUR_VERSION}")
        entrance = payload.pop("entrance", None)
        appearance = payload.pop("appearance", None)
        if not isinstance(entrance, Mapping) or set(entrance) != {"width", "height", "offset", "profile"}:
            raise ValueError("V5 contour entrance must contain width, height, offset, and profile")
        if not isinstance(appearance, Mapping) or set(appearance) != set(AppearanceSettings().as_dict()):
            raise ValueError("V5 appearance must contain all relief settings")
        expected = {
            "height", "wall_thickness", "roof_thickness", "summit", "levels", "ring_clearance", "max_local_slope_deg",
            "max_overhang_xy", "max_overhang_ratio", "min_level_spacing",
        }
        if set(payload) != expected:
            raise ValueError(_key_error(payload, expected, "contour"))
        levels = _decode_levels(payload.pop("levels"), version=3)
        design = cls(
            **payload,
            levels=levels,
            entrance_width=float(entrance["width"]),
            entrance_height=float(entrance["height"]),
            entrance_offset=float(entrance["offset"]),
            entrance_profile=[[float(x), float(z)] for x, z in entrance["profile"]],
            appearance=AppearanceSettings(**appearance),
        )
        design.validate()
        return design

    @classmethod
    def _from_v2(cls, payload: dict[str, Any]) -> "ContourDesign":
        """Migrate V2 mountain files into V5 without discarding authored contours."""
        entrance = payload.pop("entrance", None)
        expected = {"height", "wall_thickness", "roof_thickness", "summit", "levels", "ring_clearance", "max_local_slope_deg"}
        if not isinstance(entrance, Mapping) or set(entrance) != {"width", "height", "offset"}:
            raise ValueError("V2 contour entrance must contain width, height, and offset")
        if set(payload) != expected:
            raise ValueError(_key_error(payload, expected, "V2 contour"))
        levels = _decode_levels(payload.pop("levels"), version=2)
        expanded = [index for index in range(1, len(levels) - 1) if _control_area(levels[index].points) > _control_area(levels[index - 1].points)]
        shoulder_index = max(expanded, key=lambda index: _control_area(levels[index].points)) if expanded else len(levels) - 2
        for index, level in enumerate(levels):
            level.role = "roof_top" if index == len(levels) - 1 else "roof_shoulder" if index == shoulder_index else "wall"
            level.z_locked = index in {0, len(levels) - 1}
        width = _bounds(levels[0].points)[1] - _bounds(levels[0].points)[0]
        height = float(payload.pop("height"))
        entrance_width = float(entrance["width"])
        entrance_height = float(entrance["height"])
        design = cls(
            **payload,
            height=height,
            levels=levels,
            entrance_width=entrance_width,
            entrance_height=entrance_height,
            entrance_offset=float(entrance["offset"]),
            entrance_profile=_default_entrance_profile(entrance_width, entrance_height),
            max_overhang_xy=min(8.0, width * 0.08),
        )
        design.validate()
        return design

    def validate(self) -> None:
        """Validate the editable stack before any CadQuery operation."""
        from .contour_validation import validate_contour_design

        validate_contour_design(self)


def _default_entrance_profile(width: float, height: float) -> list[list[float]]:
    shoulder = height * 0.48
    return [
        [-width / 2.0, 0.0], [-width / 2.0, shoulder], [-width * 0.36, height * 0.82],
        [0.0, height], [width * 0.34, height * 0.89], [width / 2.0, height * 0.54], [width / 2.0, 0.0],
    ]


def _decode_levels(raw_levels: Any, *, version: int) -> list[ContourLevel]:
    if not isinstance(raw_levels, Sequence):
        raise ValueError("contour levels must be an array")
    levels: list[ContourLevel] = []
    permitted = {"z", "points", "surface_mode", "manually_modified"}
    if version == 3:
        permitted |= {"role", "z_locked", "shape_locked"}
    for raw in raw_levels:
        if not isinstance(raw, Mapping) or set(raw) - permitted or {"z", "points"} - set(raw):
            raise ValueError("each contour level must contain valid V5 fields")
        mode = str(raw.get("surface_mode", "smooth"))
        levels.append(ContourLevel(
            z=float(raw["z"]),
            points=[[float(x), float(y)] for x, y in raw["points"]],
            surface_mode="ledge" if mode == "step" else mode,
            manually_modified=bool(raw.get("manually_modified", False)),
            role=str(raw.get("role", "wall")),
            z_locked=bool(raw.get("z_locked", False)),
            shape_locked=bool(raw.get("shape_locked", False)),
        ))
    return levels


def _key_error(payload: Mapping[str, Any], expected: set[str], label: str) -> str:
    unknown = set(payload) - expected
    missing = expected - set(payload)
    details = []
    if unknown:
        details.append(f"unknown {label} keys: {', '.join(sorted(unknown))}")
    if missing:
        details.append(f"missing {label} keys: {', '.join(sorted(missing))}")
    return "; ".join(details)


def _control_area(points: Sequence[Sequence[float]]) -> float:
    """Measure a control loop sufficiently to identify a migrated broad roof shoulder."""
    ring = np.asarray(points, dtype=float)
    return abs(float(np.dot(ring[:, 0], np.roll(ring[:, 1], -1)) - np.dot(ring[:, 1], np.roll(ring[:, 0], -1))))


def _bounds(points: Sequence[Sequence[float]], *, axis: int = 0) -> tuple[float, float]:
    values = [float(point[axis]) for point in points]
    return min(values), max(values)


def scale_design(design: ContourDesign, factor: float) -> ContourDesign:
    """Uniformly scale all authored V5 geometry and manufacturing dimensions."""
    if factor <= 0:
        raise ValueError("design scale must be greater than zero")
    scaled = replace(
        design,
        height=design.height * factor,
        wall_thickness=design.wall_thickness * factor,
        roof_thickness=design.roof_thickness * factor,
        summit=[value * factor for value in design.summit],
        levels=[replace(level, z=level.z * factor, points=[[value * factor for value in point] for point in level.points]) for level in design.levels],
        entrance_width=design.entrance_width * factor,
        entrance_height=design.entrance_height * factor,
        entrance_offset=design.entrance_offset * factor,
        entrance_profile=[[x * factor, z * factor] for x, z in design.entrance_profile],
        ring_clearance=design.ring_clearance * factor,
        max_overhang_xy=design.max_overhang_xy * factor,
        min_level_spacing=design.min_level_spacing * factor,
        appearance=replace(design.appearance, relief_depth=design.appearance.relief_depth * factor,
                           relief_gap=design.appearance.relief_gap * factor, relief_scale=design.appearance.relief_scale * factor),
    )
    scaled.validate()
    return scaled


def load_design(path: str | Path) -> ContourDesign:
    """Load, migrate when needed, and validate a versioned editable contour design."""
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
    """Validate and write a deterministic editable V5 contour design."""
    design.validate()
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(design.as_dict(), indent=2) + "\n", encoding="utf-8")
    return destination
