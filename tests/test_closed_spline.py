import numpy as np
import pytest
from scipy.interpolate import splev, splprep

from gecko_hide.contour import ContourDesign
from gecko_hide.contour_shell import sample_contour


def test_periodic_spline_is_closed_and_tangent_continuous():
    points = ContourDesign.default().footprint.points
    controls = np.asarray(points, dtype=float)
    knots, _ = splprep(np.vstack((controls, controls[0])).T, s=0.0, per=True, k=3)
    start = np.asarray(splev(0.0, knots))
    end = np.asarray(splev(1.0, knots))
    start_tangent = np.asarray(splev(0.0, knots, der=1))
    end_tangent = np.asarray(splev(1.0, knots, der=1))
    assert start == pytest.approx(end, abs=1e-9)
    assert start_tangent == pytest.approx(end_tangent, abs=1e-8)
    assert len(sample_contour(points, count=96)) == 96
