"""Top-level deterministic Boolean assembly."""

from __future__ import annotations

import cadquery as cq

from .config import GeckoHideConfig
from .entrance import create_entrance_cutout, entrance_keepout
from .random_utils import make_rng
from .roof_generator import generate_roof_stones
from .shell import create_shell, safe_cut, safe_union
from .validation import validate_shape
from .wall_generator import generate_wall_stones


def _emit(step: int, label: str, progress: bool) -> None:
    if progress:
        print(f"[{step}/10] {label}")


def generate_gecko_hide(config: GeckoHideConfig, *, progress: bool = False) -> cq.Shape:
    """Create one reproducible, single-solid, open-bottom printable hide."""
    _emit(1, "Validating config", progress)
    config.validate()
    rng = make_rng(config.seed)

    _emit(2, "Creating structural shell", progress)
    body = create_shell(config, rng)
    _emit(3, "Creating entrance", progress)
    body = safe_cut(body, create_entrance_cutout(config, rng))

    walls = (
        (4, "front", entrance_keepout(config)),
        (5, "back", None),
        (6, "left", None),
        (7, "right", None),
    )
    for step, side, keepout in walls:
        _emit(step, f"Generating {side} stones", progress)
        stones = generate_wall_stones(body, side, config, rng, keepout)
        body = safe_union(body, stones.Solids())

    _emit(8, "Generating roof stones", progress)
    body = safe_union(body, generate_roof_stones(body, config, rng).Solids())
    _emit(9, "Cleaning geometry", progress)
    body = body.clean()
    _emit(10, "Validating model", progress)
    validate_shape(body)
    return body
