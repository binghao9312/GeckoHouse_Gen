import numpy as np
import pytest

from gecko_hide.contour import ContourDesign
from gecko_hide.contour_shell import align_contours, sample_contour


def test_alignment_removes_cyclic_phase_and_preserves_sample_count():
    design = ContourDesign.default()
    outer = sample_contour(design.levels[0].points, count=96)
    inner = sample_contour(design.levels[1].points, count=96)
    shifted = np.roll(inner, 31, axis=0)
    aligned = align_contours([outer, shifted])
    expected = align_contours([outer, inner])
    assert len(aligned[0]) == len(aligned[1]) == 96
    assert aligned[1] == pytest.approx(expected[1], abs=1e-8)
