"""Configuration and validation for the Gecko Hide Generator."""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Any, Mapping


@dataclass(frozen=True)
class GeckoHideConfig:
    width: float = 180.0
    depth: float = 120.0
    height: float = 75.0

    wall_thickness: float = 4.0
    roof_thickness: float = 5.0
    bottom_open: bool = True

    entrance_width: float = 55.0
    entrance_height: float = 40.0
    entrance_offset_x: float = -30.0

    stone_width_min: float = 22.0
    stone_width_max: float = 48.0
    stone_height_min: float = 15.0
    stone_height_max: float = 30.0
    stone_depth_min: float = 1.5
    stone_depth_max: float = 5.0
    stone_gap_min: float = 1.2
    stone_gap_max: float = 2.5
    stone_vertex_count_min: int = 7
    stone_vertex_count_max: int = 12
    stone_irregularity: float = 0.20
    stone_fillet_min: float = 1.5
    stone_fillet_max: float = 4.0
    roof_rock_count_min: int = 3
    roof_rock_count_max: int = 7
    seed: int = 12345

    def validate(self) -> None:
        positive = ("width", "depth", "height", "entrance_width", "entrance_height")
        for name in positive:
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be greater than zero")
        if self.wall_thickness < 3.0:
            raise ValueError("wall_thickness must be at least 3.0 mm")
        if self.roof_thickness < 3.0:
            raise ValueError("roof_thickness must be at least 3.0 mm")
        if self.entrance_width >= self.width - 2 * self.wall_thickness:
            raise ValueError("entrance_width does not fit between side walls")
        if self.entrance_height >= self.height - self.roof_thickness:
            raise ValueError("entrance_height does not fit below the roof")
        if abs(self.entrance_offset_x) + self.entrance_width / 2 >= self.width / 2 - self.wall_thickness:
            raise ValueError("entrance_offset_x places entrance outside front wall")
        if self.stone_width_min <= 0 or self.stone_width_max < self.stone_width_min:
            raise ValueError("invalid stone width range")
        if self.stone_height_min <= 0 or self.stone_height_max < self.stone_height_min:
            raise ValueError("invalid stone height range")
        if self.stone_depth_min < 1.2 or self.stone_depth_max < self.stone_depth_min:
            raise ValueError("invalid stone depth range")
        if self.stone_gap_min < 1.2 or self.stone_gap_max < self.stone_gap_min:
            raise ValueError("invalid stone gap range")
        if self.stone_vertex_count_min < 5 or self.stone_vertex_count_max < self.stone_vertex_count_min:
            raise ValueError("invalid stone vertex count range")
        if not 0.0 <= self.stone_irregularity <= 0.45:
            raise ValueError("stone_irregularity must be between 0.0 and 0.45")
        if self.stone_fillet_min < 0 or self.stone_fillet_max < self.stone_fillet_min:
            raise ValueError("invalid stone fillet range")
        if self.roof_rock_count_min < 3 or self.roof_rock_count_max < self.roof_rock_count_min:
            raise ValueError("invalid roof rock count range")

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> "GeckoHideConfig":
        permitted = {field.name for field in fields(cls)}
        unknown = set(values) - permitted
        if unknown:
            raise ValueError(f"unknown configuration keys: {', '.join(sorted(unknown))}")
        return cls(**dict(values))
