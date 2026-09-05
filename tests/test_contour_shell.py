import cadquery as cq
import pytest

from gecko_hide.contour import ContourDesign
from gecko_hide.contour_shell import build_contour_shell


def test_contour_shell_is_one_grounded_hollow_solid_with_roof():
    design = ContourDesign.default()
    shell = build_contour_shell(design, resolution="preview")
    assert shell.isValid()
    assert len(shell.Solids()) == 1
    assert shell.Volume() > 0
    assert shell.BoundingBox().zmin == pytest.approx(0.0, abs=0.01)
    cavity_probe = cq.Workplane("XY").box(25, 25, 40, centered=(True, True, False)).val()
    assert shell.intersect(cavity_probe).Volume() == pytest.approx(0.0, abs=1e-5)
    roof_probe = cq.Workplane("XY").box(5, 5, 1, centered=(True, True, False)).translate((0, 0, design.height - 0.5)).val()
    assert shell.intersect(roof_probe).Volume() > 0


def test_step_transition_produces_a_single_printable_shell():
    design = ContourDesign.default()
    design.levels[3].surface_mode = "step"
    shell = build_contour_shell(design, resolution="preview")
    assert shell.isValid()
    assert len(shell.Solids()) == 1
    assert shell.Volume() > 0
