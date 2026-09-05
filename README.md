# Gecko Hide Generator — V3 Profile Driven

V3 builds a deterministic, smooth, open-bottom structural shell from four user-edited PCHIP boundary curves. The base shell has no decorative seams or stone dependencies; `texture_mode="none"` is the default. The retained V2 stone implementation is available only through `--texture-mode legacy_stones`.

## Install

Python 3.11+, CadQuery, NumPy, SciPy, Bokeh, trimesh, Matplotlib, and pytest:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Profile editor

```powershell
python profile_editor.py
```

The wrapper opens Bokeh Server. Alternatively:

```powershell
bokeh serve --show profile_editor.py
```

Drag the front X-Z and side Y-Z control points horizontally. Z levels remain fixed so the profile ordering cannot invert. Smooth PCHIP curves and profile validation update immediately; invalid curves disable preview and final generation. The editor saves `profiles/current.json`, exports `output/front_profile.png` and `output/side_profile.png`, creates a lower-resolution `output/profile_preview.stl` / `profile_preview.png`, and creates final `gecko_hide_profile.stl`, `.step`, `profile_iso.png`, `profile_front.png`, and `profile_side.png`.

## CLI

Generate the supplied default profile:

```powershell
python build.py --profile profiles/default.json
```

Profile boundaries, thicknesses, and entrance fields always take precedence over old macro CLI arguments. `--width`, `--depth`, `--height`, `--wall`, `--roof`, and entrance arguments are reported and ignored when `--profile` is present; curves are never silently scaled. Use an explicit uniform scale when needed:

```powershell
python build.py --profile profiles/current.json --scale 1.1
```

The dimension CLI remains available and translates its values into the V3 default editable profile:

```powershell
python build.py --width 180 --depth 120 --height 75 --wall 4 --entrance-width 55 --entrance-height 40 --entrance-offset-x -30
```

`--seed` affects only `--texture-mode legacy_stones`; it cannot affect V3 macro geometry.

## Curve and shell model

`ProfileDesign` stores `x_left(z)`, `x_right(z)`, `y_front(z)`, and `y_back(z)` at fixed Z control levels. SciPy `PchipInterpolator` produces local, continuous curves without global polynomial overshoot. At 18 preview or 32 final heights, the generator evaluates those curves and lofts consistently ordered 64-point superellipses into the outer body. An inward-offset profile loft is cut from Z=-0.5 through `height - roof_thickness`, leaving a continuous roof and coplanar Z=0 opening. The profile-aware entrance cutter runs after the shell loft.

Profile validation rejects curve crossing, insufficient interior clearance, entrances outside local side walls, wall thickness below 3.5 mm, invalid roof clearance, and boundary slopes above 55° from vertical. Final CLI generation validates the CadQuery solid and exported STL for one connected watertight component, finite vertices, positive volume, and Z=0 grounding.

## Tests

```powershell
pytest
```

The suite covers PCHIP determinism/local control, crossing rejection, profile shell cavity/roof/bottom behavior, asymmetry, JSON save/load/version errors, export validation, and retained legacy helpers.

## Known limitation

V3 intentionally does not yet implement shallow rock-relief texture. `legacy_stones` is comparison-only and is not part of the V3 structural model.
