from dataclasses import replace

import numpy as np
import pytest

from gecko_hide.profile import ProfileDesign
from gecko_hide.profile_curve import make_profile_curves


def test_pchip_curves_are_deterministic_and_respect_control_bounds():
    profile = ProfileDesign.default()
    first = make_profile_curves(profile)
    second = make_profile_curves(profile)
    heights = np.linspace(0.0, profile.height, 257)
    for name in ("x_left", "x_right", "y_front", "y_back"):
        first_values = getattr(first, name)(heights)
        second_values = getattr(second, name)(heights)
        controls = np.asarray(getattr(profile, name))
        assert first_values == pytest.approx(second_values)
        assert np.min(first_values) >= np.min(controls) - 1e-8
        assert np.max(first_values) <= np.max(controls) + 1e-8


def test_crossing_boundaries_are_rejected_before_geometry_generation():
    profile = ProfileDesign.default()
    profile.x_right[3] = profile.x_left[3] + 8.0
    with pytest.raises(ValueError, match="insufficient interior width"):
        profile.validate()


def test_adjusting_one_control_changes_only_its_local_profile_region():
    profile = ProfileDesign.default()
    changed = replace(profile, x_right=profile.x_right.copy())
    changed.x_right[4] += 12.0
    baseline = make_profile_curves(profile).x_right
    edited = make_profile_curves(changed).x_right
    near = abs(float(edited(profile.z_levels[4])) - float(baseline(profile.z_levels[4])))
    far = abs(float(edited(profile.z_levels[0])) - float(baseline(profile.z_levels[0])))
    assert near == pytest.approx(12.0)
    assert far == pytest.approx(0.0)
