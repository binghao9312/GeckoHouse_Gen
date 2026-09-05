"""CLI entry point for generating, exporting, and validating a gecko hide."""

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
from gecko_hide.generator import generate_gecko_hide
from gecko_hide.validation import validate_stl

ROOT = Path(__file__).resolve().parent


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a printable irregular-rock gecko hide.")
    parser.add_argument("--preset", choices=("small", "medium", "large"))
    parser.add_argument("--width", type=float)
    parser.add_argument("--depth", type=float)
    parser.add_argument("--height", type=float)
    parser.add_argument("--wall", dest="wall_thickness", type=float)
    parser.add_argument("--roof", dest="roof_thickness", type=float)
    parser.add_argument("--entrance-width", type=float)
    parser.add_argument("--entrance-height", type=float)
    parser.add_argument("--entrance-offset-x", type=float)
    parser.add_argument("--seed", default=None, help="integer seed or 'random'")
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


def main(argv: list[str] | None = None) -> int:
    try:
        config = _config_from_args(_parser().parse_args(argv))
        print("Gecko Hide Generator\n")
        print(f"Seed: {config.seed}\n")
        print("Dimensions:")
        print(f"{config.width:g} x {config.depth:g} x {config.height:g} mm\n")
        print("Structural wall:")
        print(f"{config.wall_thickness:g} mm\n")
        shape = generate_gecko_hide(config, progress=True)
        stl_path, step_path = export_model(shape, config, ROOT / "output")
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
        return 0
    except Exception as error:
        print(f"FAIL  {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    # CadQuery 2.6.1/OCP on this Windows Python build can alter the interpreter
    # exit status during module teardown.  Flush then exit directly with the
    # generator's verified result, preserving CLI's documented contract.
    exit_code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(exit_code)
