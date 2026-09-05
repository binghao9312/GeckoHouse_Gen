import numpy as np
import trimesh
import pytest


from gecko_hide.config import GeckoHideConfig
from gecko_hide.export import export_model
from gecko_hide.generator import generate_gecko_hide
from gecko_hide.validation import validate_step, validate_stl


def test_exported_stl_is_watertight_connected_and_finite(tmp_path):
    config = GeckoHideConfig(width=130.0, depth=90.0, height=58.0, entrance_width=40.0, entrance_height=30.0)
    shape = generate_gecko_hide(config)
    stl_path, step_path = export_model(shape, config, tmp_path)
    result = validate_stl(stl_path, config)
    mesh = trimesh.load_mesh(stl_path, force="mesh")
    assert stl_path.is_file() and stl_path.stat().st_size > 0
    assert step_path.is_file() and step_path.stat().st_size > 0
    assert result.watertight is True
    assert result.components == 1
    assert result.volume > 0
    assert mesh.is_watertight is True
    assert np.isfinite(mesh.vertices).all()


def test_exported_step_round_trips_as_one_valid_solid(tmp_path):
    config = GeckoHideConfig(width=130.0, depth=90.0, height=58.0, entrance_width=40.0, entrance_height=30.0)
    shape = generate_gecko_hide(config)
    _, step_path = export_model(shape, config, tmp_path)
    validate_step(step_path, shape)


def test_malformed_step_is_rejected_by_round_trip_validation(tmp_path):
    shape = generate_gecko_hide(GeckoHideConfig())
    malformed = tmp_path / "broken.step"
    malformed.write_text("ISO-10303-21;\\nDATA;\\n", encoding="utf-8")
    with pytest.raises(ValueError, match="STEP cannot be imported"):
        validate_step(malformed, shape)

def test_organic_geometry_ranges_are_validated():
    with pytest.raises(ValueError, match="shell top shrink"):
        GeckoHideConfig(shell_top_shrink_min=0.94, shell_top_shrink_max=0.90).validate()
    with pytest.raises(ValueError, match="stone middle bulge"):
        GeckoHideConfig(stone_mid_bulge_min=0.99).validate()
    with pytest.raises(ValueError, match="wall_vertical_jitter_ratio"):
        GeckoHideConfig(wall_vertical_jitter_ratio=0.31).validate()
