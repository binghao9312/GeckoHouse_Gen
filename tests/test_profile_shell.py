from dataclasses import replace

import cadquery as cq
import pytest

from gecko_hide.generator import generate_profile_gecko_hide
from gecko_hide.profile import ProfileDesign
from gecko_hide.profile_shell import build_profile_shell


def test_profile_shell_is_single_grounded_hollow_solid_with_roof():
    profile = ProfileDesign.default()
    shell = build_profile_shell(profile, resolution="preview")
    box = shell.BoundingBox()
    assert shell.isValid()
    assert len(shell.Solids()) == 1
    assert box.zmin == pytest.approx(0.0, abs=0.01)
    probe = cq.Workplane("XY").box(80.0, 45.0, profile.height - profile.roof_thickness - 3.0,
                                    centered=(True, True, False)).val()
    assert shell.intersect(probe).Volume() == pytest.approx(0.0, abs=1e-5)
    roof_probe = cq.Workplane("XY").box(10.0, 10.0, 1.0, centered=(True, True, False)).translate(
        (0.0, 0.0, profile.height - 0.5)
    ).val()
    assert shell.intersect(roof_probe).Volume() > 0


def test_profile_asymmetry_changes_generated_geometry_without_seed():
    profile = ProfileDesign.default()
    altered = replace(profile, x_right=profile.x_right.copy())
    altered.x_right[0] += 8.0
    baseline = generate_profile_gecko_hide(profile, resolution="preview")
    changed = generate_profile_gecko_hide(altered, resolution="preview")
    assert baseline.Volume() != pytest.approx(changed.Volume(), abs=1e-3)
    assert baseline.BoundingBox().xmax != pytest.approx(changed.BoundingBox().xmax, abs=1e-3)
