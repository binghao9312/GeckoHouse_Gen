"""Top-level V3 profile-driven and optional V2 legacy assemblies."""

from __future__ import annotations

from dataclasses import replace

import cadquery as cq

from .config import GeckoHideConfig
from .entrance import create_entrance_cutout, create_profile_entrance_cutout, entrance_keepout
from .profile import ProfileDesign
from .profile_shell import build_profile_shell
from .random_utils import make_rng
from .roof_generator import generate_roof_stones
from .shell import create_shell, safe_cut, safe_union
from .validation import validate_shape
from .wall_generator import generate_wall_stones


def _emit(step: int, label: str, progress: bool) -> None:
    if progress:
        print(f"[{step}/10] {label}")


def profile_from_config(config: GeckoHideConfig) -> ProfileDesign:
    """Translate the retained dimension CLI into the default editable V3 profile."""
    return replace(
        ProfileDesign.default(width=config.width, depth=config.depth, height=config.height),
        wall_thickness=config.wall_thickness,
        roof_thickness=config.roof_thickness,
        entrance_width=config.entrance_width,
        entrance_height=config.entrance_height,
        entrance_offset_x=config.entrance_offset_x,
    )


def generate_profile_gecko_hide(profile: ProfileDesign, *, resolution: str = "final", progress: bool = False) -> cq.Shape:
    """Create a deterministic, entrance-cut, texture-free V3 structural hide."""
    _emit(1, "Validating editable profiles", progress)
    profile.validate()
    _emit(2, "Lofting continuous structural shell", progress)
    body = build_profile_shell(profile, resolution)
    _emit(3, "Cutting profile-aware entrance", progress)
    body = safe_cut(body, create_profile_entrance_cutout(profile))
    _emit(4, "Validating continuous model", progress)
    validate_shape(body)
    return body


def _generate_legacy_stone_hide(config: GeckoHideConfig, *, progress: bool) -> cq.Shape:
    """Retain V2's seeded stone assembly for explicit comparison only."""
    rng = make_rng(config.seed)
    _emit(2, "Creating legacy structural shell", progress)
    body = create_shell(config, rng)
    _emit(3, "Creating legacy entrance", progress)
    body = safe_cut(body, create_entrance_cutout(config, rng))
    walls = (
        (4, "front", entrance_keepout(config)),
        (5, "back", None),
        (6, "left", None),
        (7, "right", None),
    )
    for step, side, keepout in walls:
        _emit(step, f"Generating legacy {side} stones", progress)
        body = safe_union(body, generate_wall_stones(body, side, config, rng, keepout).Solids())
    _emit(8, "Generating legacy roof stones", progress)
    body = safe_union(body, generate_roof_stones(body, config, rng).Solids())
    _emit(9, "Cleaning legacy geometry", progress)
    body = body.clean()
    _emit(10, "Validating model", progress)
    validate_shape(body)
    return body


def generate_gecko_hide(config: GeckoHideConfig, *, progress: bool = False) -> cq.Shape:
    """Generate V3 by default; V2 stones require ``texture_mode='legacy_stones'``."""
    config.validate()
    if config.texture_mode == "legacy_stones":
        return _generate_legacy_stone_hide(config, progress=progress)
    return generate_profile_gecko_hide(profile_from_config(config), progress=progress)
