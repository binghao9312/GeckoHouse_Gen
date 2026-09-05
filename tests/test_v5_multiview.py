from dataclasses import replace

import pytest

from gecko_hide.contour import CONTOUR_VERSION, ContourDesign


def test_front_bounds_transform_updates_canonical_x_only():
    design = ContourDesign.default()
    index = 3
    old_min, old_max = design.level_bounds(index, axis=0)
    before_y = [point[1] for point in design.levels[index].points]
    design.set_level_bounds(index, axis=0, lower=old_min + 2, upper=old_max - 2)
    new_min, new_max = design.level_bounds(index, axis=0)
    assert (new_min, new_max) == pytest.approx((old_min + 2, old_max - 2), abs=0.05)
    assert [point[1] for point in design.levels[index].points] == before_y


def test_side_bounds_transform_updates_canonical_y_only():
    design = ContourDesign.default()
    index = 3
    old_min, old_max = design.level_bounds(index, axis=1)
    before_x = [point[0] for point in design.levels[index].points]
    design.set_level_bounds(index, axis=1, lower=old_min + 1, upper=old_max - 1)
    new_min, new_max = design.level_bounds(index, axis=1)
    assert (new_min, new_max) == pytest.approx((old_min + 1, old_max - 1), abs=0.05)
    assert [point[0] for point in design.levels[index].points] == before_x


def test_center_translation_and_z_edit_preserve_stack_constraints():
    design = ContourDesign.default()
    index = 3
    center = sum(design.level_bounds(index, axis=0)) / 2
    design.translate_level(index, axis=0, center=center + 0.5)
    assert sum(design.level_bounds(index, axis=0)) / 2 == pytest.approx(center + 0.5, abs=0.05)
    design.set_level_z(index, 39.0)
    assert design.levels[index].z == pytest.approx(39.0)


def test_default_roof_shoulder_has_safe_controlled_overhang():
    design = ContourDesign.default()
    shoulder = next(index for index, level in enumerate(design.levels) if level.role == "roof_shoulder")
    assert design.levels[shoulder].z == pytest.approx(58.0)
    design.validate()


def test_extreme_roof_shoulder_overhang_is_rejected():
    design = ContourDesign.default()
    index = next(index for index, level in enumerate(design.levels) if level.role == "roof_shoulder")
    level = design.levels[index]
    design.levels[index] = replace(level, points=[[x * 1.25, y * 1.25] for x, y in level.points])
    with pytest.raises(ValueError, match="roof shoulder overhang"):
        design.validate()


def test_v2_design_migrates_to_v5_and_preserves_edited_points():
    design = ContourDesign.default()
    payload = design.as_dict()
    payload["version"] = 2
    payload.pop("appearance")
    payload.pop("max_overhang_xy")
    payload.pop("max_overhang_ratio")
    payload.pop("min_level_spacing")
    payload.pop("base_thickness")
    payload["entrance"].pop("profile")
    for level in payload["levels"]:
        level.pop("role")
        level.pop("z_locked")
        level.pop("shape_locked")
    migrated = ContourDesign.from_mapping(payload)
    assert migrated.as_dict()["version"] == CONTOUR_VERSION
    assert migrated.levels[3].points == design.levels[3].points
    assert migrated.levels[5].role == "roof_shoulder"


def test_base_thickness_round_trips_and_rejects_a_filled_cavity():
    design = ContourDesign.default()
    design.base_thickness = 2.0
    assert ContourDesign.from_mapping(design.as_dict()).base_thickness == pytest.approx(2.0)
    design.base_thickness = design.height - design.roof_thickness
    with pytest.raises(ValueError, match="base thickness"):
        design.validate()
