import random

import pytest

from gecko_hide.stone import create_stone


def _bounds(shape):
    box = shape.BoundingBox()
    return (box.xmin, box.xmax, box.ymin, box.ymax, box.zmin, box.zmax)


def test_stone_is_single_solid_with_volume_and_reasonable_dimensions():
    stone = create_stone(32.0, 21.0, 4.0, random.Random(12345))
    box = stone.BoundingBox()
    assert stone.isValid()
    assert len(stone.Solids()) == 1
    assert stone.Volume() > 0
    assert 20 < box.xlen < 45
    assert 12 < box.ylen < 32
    assert box.zlen == pytest.approx(4.0, abs=0.1)


def test_stones_are_seed_deterministic_but_rng_state_changes_geometry():
    first = create_stone(32.0, 21.0, 4.0, random.Random(42))
    repeat = create_stone(32.0, 21.0, 4.0, random.Random(42))
    different = create_stone(32.0, 21.0, 4.0, random.Random(43))
    assert first.Volume() == pytest.approx(repeat.Volume(), abs=1e-7)
    assert _bounds(first) == pytest.approx(_bounds(repeat), abs=1e-7)
    assert first.Volume() != pytest.approx(different.Volume(), abs=1e-4)
