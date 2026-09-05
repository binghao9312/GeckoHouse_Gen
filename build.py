"""CLI entry point for V5 rock-shelter contour generation and export."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
from dataclasses import fields, replace
from pathlib import Path
from typing import Any

import numpy as np

from gecko_hide.config import GeckoHideConfig
from gecko_hide.contour import ContourDesign, load_design, save_design, scale_design
from gecko_hide.contour_shell import sample_contour
from gecko_hide.export import export_model
from gecko_hide.generator import contour_from_config, generate_contour_gecko_hide, generate_profile_gecko_hide
from gecko_hide.profile import ProfileDesign, load_profile, scale_profile
from gecko_hide.validation import validate_stl
from render_preview import render_profile_views, render_v5_contour_views

ROOT = Path(__file__).resolve().parent
CURRENT_DESIGN = ROOT / "designs" / "current.json"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a printable V5 rock-shelter gecko hide.")
    parser.add_argument("--design", type=Path, help="versioned V5 contour design JSON (V2 migrates on load)")
    parser.add_argument("--legacy-profile", type=Path, help="deprecated versioned V3 profile JSON")
    parser.add_argument("--scale", type=float, default=1.0, help="uniform authored-design scale")
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


def _config_for_design(design: ContourDesign) -> GeckoHideConfig:
    """Supply STL acceptance dimensions without altering authored contour loops."""
    base = sample_contour(design.footprint.points, count=192)
    return GeckoHideConfig(
        width=float(np.ptp(base[:, 0])),
        depth=float(np.ptp(base[:, 1])),
        height=design.height,
        wall_thickness=design.wall_thickness,
        roof_thickness=design.roof_thickness,
        entrance_width=design.entrance_width,
        entrance_height=design.entrance_height,
        entrance_offset_x=design.entrance_offset,
    )


def _config_for_profile(profile: ProfileDesign) -> GeckoHideConfig:
    """Supply retained V3 STL validation dimensions."""
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


def _authored_dimension_options(args: argparse.Namespace) -> list[str]:
    return [option for option, value in (
        ("--preset", args.preset), ("--width", args.width), ("--depth", args.depth),
        ("--height", args.height), ("--wall", args.wall_thickness), ("--roof", args.roof_thickness),
        ("--entrance-width", args.entrance_width), ("--entrance-height", args.entrance_height),
        ("--entrance-offset-x", args.entrance_offset_x),
    ) if value is not None]


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


def _run_legacy_profile(args: argparse.Namespace) -> None:
    profile = scale_profile(load_profile(args.legacy_profile), args.scale)
    ignored = _authored_dimension_options(args)
    if ignored:
        print(f"Legacy profile boundaries take precedence; ignoring {', '.join(ignored)}.")
    config = _config_for_profile(profile)
    shape = generate_profile_gecko_hide(profile, progress=True)
    stl_path, step_path = export_model(shape, config, ROOT / "output", stem="gecko_hide_profile")
    views = render_profile_views(stl_path, ROOT / "output")
    _report(stl_path, step_path, config)
    for path in views:
        print(f"PASS  {path.relative_to(ROOT)}")


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        if args.design and args.legacy_profile:
            raise ValueError("choose either --design or --legacy-profile")
        print("Gecko Hide Generator V5\n")
        if args.legacy_profile:
            print("Deprecated V3 profile mode.\n")
            _run_legacy_profile(args)
            return 0

        if args.design:
            design = scale_design(load_design(args.design), args.scale)
            ignored = _authored_dimension_options(args)
            if ignored:
                print(f"Authored contours take precedence; ignoring {', '.join(ignored)}.")
            print(f"Design: {args.design}")
        else:
            config = _config_from_args(args)
            if config.texture_mode == "legacy_stones":
                raise ValueError("legacy stones are not part of the V4 contour workflow")
            design = contour_from_config(config)
            save_design(design, CURRENT_DESIGN)
            print(f"Saved default design: {CURRENT_DESIGN.relative_to(ROOT)}")
        config = _config_for_design(design)
        print(f"Dimensions: {config.width:g} x {config.depth:g} x {config.height:g} mm\n")
        shape = generate_contour_gecko_hide(design, progress=True)
        stl_path, step_path = export_model(shape, config, ROOT / "output", stem="gecko_hide_v5")
        views = render_v5_contour_views(stl_path, ROOT / "output")
        _report(stl_path, step_path, config)
        for path in views:
            print(f"PASS  {path.relative_to(ROOT)}")
        return 0
    except Exception as error:
        print(f"FAIL  {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(exit_code)
