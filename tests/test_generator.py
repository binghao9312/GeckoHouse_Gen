import pytest
import random


from gecko_hide.config import GeckoHideConfig
from gecko_hide.generator import generate_gecko_hide
from gecko_hide.entrance import create_entrance_cutout



def _bbox(shape):
    box = shape.BoundingBox()
    return (box.xmin, box.xmax, box.ymin, box.ymax, box.zmin, box.zmax)


def test_default_generator_returns_single_valid_grounded_solid():
    shape = generate_gecko_hide(GeckoHideConfig())
    assert shape.isValid()
    assert len(shape.Solids()) == 1
    assert shape.Volume() > 0
    assert shape.BoundingBox().zmin == pytest.approx(0.0, abs=0.05)


def test_seed_is_reproducible_and_changes_layout():
    config = GeckoHideConfig(width=130.0, depth=90.0, height=58.0, entrance_width=40.0, entrance_height=30.0)
    first = generate_gecko_hide(config)
    repeat = generate_gecko_hide(config)
    changed = generate_gecko_hide(GeckoHideConfig(**{**config.as_dict(), "seed": 9}))
    assert first.Volume() == pytest.approx(repeat.Volume(), abs=1e-6)
    assert _bbox(first) == pytest.approx(_bbox(repeat), abs=1e-6)
    assert first.Volume() != pytest.approx(changed.Volume(), abs=1e-3)

def test_entrance_cutter_preserves_configured_opening_size():
    config = GeckoHideConfig()
    cutter = create_entrance_cutout(config, random.Random(config.seed))
    bounds = cutter.BoundingBox()
    assert bounds.xlen == pytest.approx(config.entrance_width, rel=0.05)
    assert bounds.zlen == pytest.approx(config.entrance_height, rel=0.05)
