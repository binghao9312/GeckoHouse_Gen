import numpy as np
import trimesh

from gecko_hide.contour import ContourDesign
from gecko_hide.relief import export_textured_stl


def test_textured_stl_relief_is_seeded_outward_and_watertight(tmp_path):
    source = tmp_path / "structural.stl"
    trimesh.creation.icosphere(subdivisions=3, radius=40).export(source)
    design = ContourDesign.default()
    design.appearance.relief_enabled = True
    textured_path = export_textured_stl(source, tmp_path / "textured.stl", design)
    textured = trimesh.load_mesh(textured_path, force="mesh", process=True)
    structural = trimesh.load_mesh(source, force="mesh", process=True)
    assert textured.is_watertight
    assert np.isfinite(textured.vertices).all()
    assert textured.volume > structural.volume
