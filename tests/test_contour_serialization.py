from dataclasses import replace

from gecko_hide.contour import ContourDesign, load_design, save_design


def test_contour_save_load_is_deterministic_and_preserves_manual_edit(tmp_path):
    design = ContourDesign.default()
    first = design.levels[2]
    edited_points = [point.copy() for point in first.points]
    edited_points[3][0] += 4.0
    design.levels[2] = replace(first, points=edited_points, surface_mode="step", manually_modified=True)
    destination = save_design(design, tmp_path / "contour.json")
    loaded = load_design(destination)
    assert loaded.as_dict() == design.as_dict()
    assert loaded.levels[2].manually_modified
    assert loaded.levels[2].surface_mode == "step"
