"""Validate an exported default-parameter Gecko Hide STL."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from gecko_hide.config import GeckoHideConfig
from gecko_hide.validation import validate_stl


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a gecko hide STL with trimesh.")
    parser.add_argument("stl", nargs="?", default="output/gecko_hide_seed_12345.stl")
    parser.add_argument("--seed", type=int, default=12345)
    args = parser.parse_args(argv)
    try:
        result = validate_stl(Path(args.stl), GeckoHideConfig(seed=args.seed))
        print(f"watertight: {result.watertight}")
        print(f"components: {result.components}")
        print(f"volume: {result.volume:.2f} mm^3")
        print(f"bounds: {result.bounds}")
        print(f"triangles: {result.triangle_count}")
        return 0
    except Exception as error:
        print(f"FAIL  {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)
