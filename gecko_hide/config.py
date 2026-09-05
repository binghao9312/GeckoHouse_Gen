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
    shell_profile_jitter: float = 0.025
    shell_top_shrink_min: float = 0.84
    shell_top_shrink_max: float = 0.91
    shell_center_offset_max: float = 3.0

    stone_front_taper_min: float = 0.72
    stone_front_taper_max: float = 0.88
    stone_mid_bulge_min: float = 1.02
    stone_mid_bulge_max: float = 1.10
    stone_section_jitter: float = 0.06
    stone_rotation_max_deg: float = 12.0
    wall_vertical_jitter_ratio: float = 0.15

    texture_mode: str = "none"


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
        if not 0.0 <= self.shell_profile_jitter <= 0.08:
            raise ValueError("shell_profile_jitter must be between 0.0 and 0.08")
        if not 0.70 <= self.shell_top_shrink_min <= self.shell_top_shrink_max <= 0.98:
            raise ValueError("invalid shell top shrink range")
        if not 0.0 <= self.shell_center_offset_max <= 8.0:
            raise ValueError("shell_center_offset_max must be between 0.0 and 8.0 mm")
        if not 0.55 <= self.stone_front_taper_min <= self.stone_front_taper_max <= 0.95:
            raise ValueError("invalid stone front taper range")
        if not 1.0 <= self.stone_mid_bulge_min <= self.stone_mid_bulge_max <= 1.20:
            raise ValueError("invalid stone middle bulge range")
        if not 0.0 <= self.stone_section_jitter <= 0.12:
            raise ValueError("stone_section_jitter must be between 0.0 and 0.12")
        if not 0.0 <= self.stone_rotation_max_deg <= 20.0:
            raise ValueError("stone_rotation_max_deg must be between 0.0 and 20.0")
        if not 0.0 <= self.wall_vertical_jitter_ratio <= 0.30:
            raise ValueError("wall_vertical_jitter_ratio must be between 0.0 and 0.30")
        if self.texture_mode not in {"none", "legacy_stones"}:
            raise ValueError("texture_mode must be 'none' or 'legacy_stones'")

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> "GeckoHideConfig":
        permitted = {field.name for field in fields(cls)}
        unknown = set(values) - permitted
        if unknown:
            raise ValueError(f"unknown configuration keys: {', '.join(sorted(unknown))}")
        return cls(**dict(values))
