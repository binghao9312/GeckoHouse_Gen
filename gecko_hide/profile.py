"""Serializable user-authored orthographic profiles for a gecko hide."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import json
from pathlib import Path
from typing import Any, Mapping

PROFILE_VERSION = 1
_DEFAULT_LEVEL_RATIOS = (0.00, 0.12, 0.25, 0.42, 0.60, 0.76, 0.90, 1.00)


@dataclass
class ProfileDesign:
    """Four editable boundary curves sampled at fixed, ascending Z levels."""

    height: float
    z_levels: list[float]
    x_left: list[float]
    x_right: list[float]
    y_front: list[float]
    y_back: list[float]
    section_power: float = 2.8
    wall_thickness: float = 4.0
    roof_thickness: float = 5.0
    entrance_width: float = 55.0
    entrance_height: float = 40.0
    entrance_offset_x: float = -30.0

    @classmethod
    def default(cls, *, width: float = 180.0, depth: float = 120.0, height: float = 75.0) -> "ProfileDesign":
        """Return the gentle, editable V3 profile scaled from the documented default."""
        x_scale = width / 180.0
        y_scale = depth / 120.0
        z_levels = [ratio * height for ratio in _DEFAULT_LEVEL_RATIOS]
        return cls(
            height=height,
            z_levels=z_levels,
            x_left=[value * x_scale for value in (-90, -91, -90, -87, -82, -75, -67, -60)],
            x_right=[value * x_scale for value in (90, 91, 90, 88, 83, 77, 70, 63)],
            y_front=[value * y_scale for value in (-60, -61, -60, -58, -54, -49, -43, -38)],
            y_back=[value * y_scale for value in (60, 61, 60, 59, 55, 51, 45, 40)],
            entrance_width=55.0 * x_scale,
            entrance_height=40.0 * min(x_scale, height / 75.0),
            entrance_offset_x=-30.0 * x_scale,
        )

    def as_dict(self) -> dict[str, Any]:
        """Return the documented versioned on-disk JSON representation."""
        data = asdict(self)
        entrance = {
            "width": data.pop("entrance_width"),
            "height": data.pop("entrance_height"),
            "offset_x": data.pop("entrance_offset_x"),
        }
        return {"version": PROFILE_VERSION, **data, "entrance": entrance}

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> "ProfileDesign":
        """Decode one supported profile JSON mapping without silently ignoring keys."""
        payload = dict(values)
        version = payload.pop("version", None)
        if version != PROFILE_VERSION:
            raise ValueError(f"unsupported profile version: {version!r}; expected {PROFILE_VERSION}")
        entrance = payload.pop("entrance", None)
        if not isinstance(entrance, Mapping):
            raise ValueError("profile entrance must be an object")
        expected = {
            "height", "z_levels", "x_left", "x_right", "y_front", "y_back",
            "section_power", "wall_thickness", "roof_thickness",
        }
        unknown = set(payload) - expected
        missing = expected - set(payload)
        if unknown:
            raise ValueError(f"unknown profile keys: {', '.join(sorted(unknown))}")
        if missing:
            raise ValueError(f"missing profile keys: {', '.join(sorted(missing))}")
        entrance_keys = {"width", "height", "offset_x"}
        if set(entrance) != entrance_keys:
            raise ValueError("profile entrance must contain width, height, and offset_x")
        profile = cls(
            **payload,
            entrance_width=entrance["width"],
            entrance_height=entrance["height"],
            entrance_offset_x=entrance["offset_x"],
        )
        profile.validate()
        return profile

    def validate(self) -> None:
        """Validate raw control data and sampled smooth-curve safety constraints."""
        from .profile_validation import validate_profile

        validate_profile(self)


def scale_profile(profile: ProfileDesign, factor: float) -> ProfileDesign:
    """Uniformly scale an authored profile, including print-safety dimensions."""
    if factor <= 0:
        raise ValueError("profile scale must be greater than zero")
    scaled = replace(
        profile,
        height=profile.height * factor,
        z_levels=[value * factor for value in profile.z_levels],
        x_left=[value * factor for value in profile.x_left],
        x_right=[value * factor for value in profile.x_right],
        y_front=[value * factor for value in profile.y_front],
        y_back=[value * factor for value in profile.y_back],
        wall_thickness=profile.wall_thickness * factor,
        roof_thickness=profile.roof_thickness * factor,
        entrance_width=profile.entrance_width * factor,
        entrance_height=profile.entrance_height * factor,
        entrance_offset_x=profile.entrance_offset_x * factor,
    )
    scaled.validate()
    return scaled


def load_profile(path: str | Path) -> ProfileDesign:
    """Load and validate a versioned profile JSON file."""
    source = Path(path)
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except OSError as error:
        raise ValueError(f"cannot read profile {source}: {error}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid profile JSON in {source}: {error.msg}") from error
    if not isinstance(data, Mapping):
        raise ValueError("profile JSON root must be an object")
    return ProfileDesign.from_mapping(data)


def save_profile(profile: ProfileDesign, path: str | Path) -> Path:
    """Validate and atomically write a profile JSON document."""
    profile.validate()
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(profile.as_dict(), indent=2) + "\n", encoding="utf-8")
    return destination
