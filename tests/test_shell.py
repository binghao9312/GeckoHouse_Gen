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
    assert bbox.xlen <= config.width * (1 + config.shell_profile_jitter) + 0.5
    assert bbox.ylen <= config.depth * (1 + config.shell_profile_jitter) + 0.5
    assert bbox.zmin == pytest.approx(0.0, abs=0.01)
    bottom_slice = shell.intersect(
        cq.Workplane("XY")
        .box(config.width + 10, config.depth + 10, 0.4, centered=(True, True, False))
        .translate((0, 0, 0.1))
        .val()
    )
    top_slice = shell.intersect(
        cq.Workplane("XY")
        .box(config.width + 10, config.depth + 10, 0.4, centered=(True, True, False))
        .translate((0, 0, config.height - 0.3))
        .val()
    )
    assert top_slice.BoundingBox().xlen < bottom_slice.BoundingBox().xlen
    assert top_slice.BoundingBox().ylen < bottom_slice.BoundingBox().ylen
    outer_volume = config.width * config.depth * config.height
    assert 0 < shell.Volume() < outer_volume * 0.35
    # This vertical probe occupies the inner void, so shell and probe do not overlap.
    probe = cq.Workplane("XY").box(
        config.width * config.shell_top_shrink_min - 2 * config.wall_thickness - 2,
        config.depth * config.shell_top_shrink_min - 2 * config.wall_thickness - 2,
        config.height - config.roof_thickness - 2,
        centered=(True, True, False),
    ).val()
    assert shell.intersect(probe).Volume() == pytest.approx(0.0, abs=1e-5)


def test_invalid_wall_thickness_is_rejected():
    with pytest.raises(ValueError, match="wall_thickness"):
        create_shell(GeckoHideConfig(wall_thickness=2.9))
