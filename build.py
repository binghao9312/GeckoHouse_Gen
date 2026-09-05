"""CLI entry point for V3 profile generation, export, previews, and validation."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
from dataclasses import fields, replace
from pathlib import Path
from typing import Any

from gecko_hide.config import GeckoHideConfig
from gecko_hide.export import export_model
from gecko_hide.generator import generate_gecko_hide, generate_profile_gecko_hide
from gecko_hide.profile import ProfileDesign, load_profile, scale_profile
from gecko_hide.validation import validate_stl
from render_preview import render_profile_views

ROOT = Path(__file__).resolve().parent


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a printable profile-driven gecko hide.")
    parser.add_argument("--profile", type=Path, help="versioned V3 profile JSON")
    parser.add_argument("--scale", type=float, default=1.0, help="uniform V3 profile scale")
    parser.add_argument("--preset", choices=("small", "medium", "large"))
    parser.add_argument("--width", type=float)
    parser.add_argument("--depth", type=float)
    parser.add_argument("--height", type=float)
    parser.add_argument("--wall", dest="wall_thickness", type=float)
    parser.add_argument("--roof", dest="roof_thickness", type=float)
    parser.add_argument("--entrance-width", type=float)
    parser.add_argument("--entrance-height", type=float)
    parser.add_argument("--entrance-offset-x", type=float)
    parser.add_argument("--seed", default=None, help="integer seed or 'random'; legacy texture only")
    parser.add_argument("--texture-mode", choices=("none", "legacy_stones"), default=None)
    return parser


def _config_from_args(args: argparse.Namespace) -> GeckoHideConfig:
    values: dict[str, Any] = {}
    if args.preset:
        values = json.loads((ROOT / "presets" / f"{args.preset}.json").read_text(encoding="utf-8"))
    allowed = {field.name for field in fields(GeckoHideConfig)}
    for name in allowed - {"seed"}:
        value = getattr(args, name, None)
        if value is not None:
            values[name] = value
    if args.seed is not None:
        values["seed"] = secrets.randbelow(2_147_483_647) if args.seed == "random" else int(args.seed)
    return replace(GeckoHideConfig(), **values)


def _config_for_profile(profile: ProfileDesign) -> GeckoHideConfig:
    """Supply STL validation dimensions without changing authored profile boundaries."""
    return GeckoHideConfig(
        width=max(profile.x_right) - min(profile.x_left),
        depth=max(profile.y_back) - min(profile.y_front),
        height=profile.height,
        wall_thickness=profile.wall_thickness,
        roof_thickness=profile.roof_thickness,
        entrance_width=profile.entrance_width,
        entrance_height=profile.entrance_height,
        entrance_offset_x=profile.entrance_offset_x,
    )


def _profile_from_args(args: argparse.Namespace) -> ProfileDesign:
    profile = scale_profile(load_profile(args.profile), args.scale)
    ignored = [
        option for option, value in (
            ("--preset", args.preset), ("--width", args.width), ("--depth", args.depth),
            ("--height", args.height), ("--wall", args.wall_thickness), ("--roof", args.roof_thickness),
            ("--entrance-width", args.entrance_width), ("--entrance-height", args.entrance_height),
            ("--entrance-offset-x", args.entrance_offset_x),
        ) if value is not None
    ]
    if ignored:
        print(f"Profile boundaries and dimensions take precedence; ignoring {', '.join(ignored)}.")
    return profile


def _report(stl_path: Path, step_path: Path, config: GeckoHideConfig) -> None:
    result = validate_stl(stl_path, config)
    print("\nValidation:")
    print("PASS  CadQuery shape valid")
    print("PASS  Single connected model")
    print("PASS  STL watertight")
    print("PASS  Finite vertices")
    print("PASS  Non-zero volume")
    print("PASS  Bottom Z = 0")
    print("\nExport:")
    print(f"PASS  {stl_path.relative_to(ROOT)}")
    print(f"PASS  {step_path.relative_to(ROOT)}")
    print(f"\nMesh: {result.triangle_count} triangles; volume {result.volume:.2f} mm^3")


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        print("Gecko Hide Generator V3\n")
        if args.profile:
            if args.texture_mode not in (None, "none"):
                raise ValueError("profile mode supports texture_mode='none' only")
            profile = _profile_from_args(args)
            config = _config_for_profile(profile)
            print(f"Profile: {args.profile}")
            print(f"Dimensions: {config.width:g} x {config.depth:g} x {config.height:g} mm\n")
            shape = generate_profile_gecko_hide(profile, progress=True)
            stl_path, step_path = export_model(shape, config, ROOT / "output", stem="gecko_hide_profile")
            iso_path, front_path, side_path = render_profile_views(stl_path, ROOT / "output")
            _report(stl_path, step_path, config)
            print(f"PASS  {iso_path.relative_to(ROOT)}")
            print(f"PASS  {front_path.relative_to(ROOT)}")
            print(f"PASS  {side_path.relative_to(ROOT)}")
        else:
            config = _config_from_args(args)
            print(f"Seed: {config.seed}\n")
            print(f"Dimensions: {config.width:g} x {config.depth:g} x {config.height:g} mm\n")
            print(f"Structural wall: {config.wall_thickness:g} mm\n")
            shape = generate_gecko_hide(config, progress=True)
            stl_path, step_path = export_model(shape, config, ROOT / "output")
            _report(stl_path, step_path, config)
        return 0
    except Exception as error:
        print(f"FAIL  {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    # CadQuery 2.6.1/OCP on this Windows Python build can alter interpreter
    # teardown status. Flush and exit directly with the documented CLI result.
    exit_code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(exit_code)
