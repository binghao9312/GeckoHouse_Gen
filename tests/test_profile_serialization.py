import json

import pytest

from gecko_hide.profile import PROFILE_VERSION, ProfileDesign, load_profile, save_profile


def test_saved_profile_loads_exactly_and_has_stable_json_data(tmp_path):
    profile = ProfileDesign.default()
    path = save_profile(profile, tmp_path / "profile.json")
    loaded = load_profile(path)
    assert loaded == profile
    assert json.loads(path.read_text(encoding="utf-8"))["version"] == PROFILE_VERSION


def test_invalid_profile_json_and_version_report_clear_errors(tmp_path):
    malformed = tmp_path / "malformed.json"
    malformed.write_text("{broken", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid profile JSON"):
        load_profile(malformed)
    incompatible = tmp_path / "incompatible.json"
    incompatible.write_text(json.dumps({"version": 99}), encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported profile version"):
        load_profile(incompatible)
