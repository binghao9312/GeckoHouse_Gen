import numpy as np
import trimesh

from gecko_hide.config import GeckoHideConfig
from gecko_hide.export import export_model
from gecko_hide.generator import generate_gecko_hide
from gecko_hide.validation import validate_stl


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
