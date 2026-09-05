import numpy as np

from gecko_hide.config import GeckoHideConfig
from gecko_hide.contour import ContourDesign
from gecko_hide.contour_shell import sample_contour
from gecko_hide.export import export_model
from gecko_hide.generator import generate_contour_gecko_hide
from gecko_hide.validation import validate_step, validate_stl


def test_v5_stl_and_step_round_trip_as_valid_single_solid(tmp_path):
    design = ContourDesign.default()
    footprint = sample_contour(design.footprint.points, count=192)
    config = GeckoHideConfig(
        width=float(np.ptp(footprint[:, 0])),
        depth=float(np.ptp(footprint[:, 1])),
        height=design.height,
        wall_thickness=design.wall_thickness,
        roof_thickness=design.roof_thickness,
        entrance_width=design.entrance_width,
        entrance_height=design.entrance_height,
        entrance_offset_x=design.entrance_offset,
    )
    shape = generate_contour_gecko_hide(design, resolution="preview")
    stl_path, step_path = export_model(shape, config, tmp_path, stem="v5_round_trip")
    stl = validate_stl(stl_path, config)
    validate_step(step_path, shape)
    assert stl.watertight
    assert stl.components == 1
    assert stl.volume > 0
