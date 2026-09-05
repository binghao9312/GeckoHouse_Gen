"""Deterministic random helpers.  Geometry never uses global random state."""

from __future__ import annotations

import random


def make_rng(seed: int) -> random.Random:
    return random.Random(seed)
