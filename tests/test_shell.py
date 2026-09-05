import cadquery as cq
import pytest

from gecko_hide.config import GeckoHideConfig
from gecko_hide.shell import create_shell


def test_shell_is_valid_hollow_and_open_at_bottom():
    config = GeckoHideConfig()
    shell = create_shell(config)
    bbox = shell.BoundingBox()
    assert shell.isValid()
    assert len(shell.Solids()) == 1
    assert bbox.xlen == pytest.approx(config.width, abs=0.1)
    assert bbox.ylen == pytest.approx(config.depth, abs=0.1)
    assert bbox.zmin == pytest.approx(0.0, abs=0.01)
    outer_volume = config.width * config.depth * config.height
    assert 0 < shell.Volume() < outer_volume * 0.35
    # This vertical probe occupies the inner void, so shell and probe do not overlap.
    probe = cq.Workplane("XY").box(
        config.width - 2 * config.wall_thickness - 2,
        config.depth - 2 * config.wall_thickness - 2,
        config.height - config.roof_thickness - 2,
        centered=(True, True, False),
    ).val()
    assert shell.intersect(probe).Volume() == pytest.approx(0.0, abs=1e-5)


def test_invalid_wall_thickness_is_rejected():
    with pytest.raises(ValueError, match="wall_thickness"):
        create_shell(GeckoHideConfig(wall_thickness=2.9))
