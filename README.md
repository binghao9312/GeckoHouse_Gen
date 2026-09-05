# Gecko Hide Generator — V4 Topographic Contours

V4 designs a hide as editable, closed XY contour rings. The default shape is an asymmetric low hill with a shifted summit, not a reconstruction from four orthographic boundary curves. It lofts the actual rings into a continuous outer solid, offsets those rings inward for the cavity, then cuts only the front entrance.

The retained V3 profile editor is deprecated at `legacy/profile_editor_v3.py`. It is not the default workflow.

## Install

Python 3.11+, CadQuery, NumPy, SciPy, Shapely, Bokeh, trimesh, Matplotlib, and pytest:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## V4 contour editor

```powershell
python profile_editor.py
```

The default editor is a top-down contour canvas:

1. Drag the 12 closed-loop footprint control points in X/Y.
2. Choose **Generate Contours** to produce seven nested levels that drift toward the Summit marker.
3. Choose a contour level, then choose **Smooth** or **Step** for its transition from the prior level.
4. Use the **Top View / Edit** and **3D Preview** tabs to switch views. `Preview 3D` renders the selected 3D tab.
5. Use **Previous Step** to restore the last edit; it stores the latest 20 complete design states.
6. Use **Generate STL + STEP** for final export.

The status line states the invalid constraint, a specific recovery action, and that preview/export are disabled. Shapely rejects self-intersection, collapsed loops, reversed orientation, insufficient nesting clearance, and excessive local slope before CadQuery runs.

`Save Design` writes `designs/current.json`; load/save preserves control-point order, each transition mode, and manual-level flags.

## CLI

Generate the default V4 design:

```powershell
python build.py
```

This writes `designs/current.json` and:

```text
output/gecko_hide_contour.stl
output/gecko_hide_contour.step
output/gecko_hide_contour_iso.png
output/gecko_hide_contour_top.png
output/gecko_hide_contour_front.png
output/gecko_hide_contour_side.png
```

Generate an authored V4 design:

```powershell
python build.py --design designs/current.json
```

Dimension arguments create a fresh V4 default footprint when no `--design` is supplied. Authored contours take precedence over dimension flags. V3 remains available only as `python build.py --legacy-profile profiles/current.json`.

## Contour and shell model

`ContourDesign` stores editable control loops at fixed Z heights in version-2 JSON. Each loop has 8–20 points and a transition mode: `smooth` lofts from the preceding ring; `step` holds the preceding footprint vertically, producing a horizontal exterior ledge at that level. Rings are arc-length resampled to 48 preview or 96 final samples, given a consistent winding direction, and cyclically aligned to minimize adjacent point travel.

The inner cavity derives from Shapely inward offsets of those outer rings; it remains smooth across external steps so an interior shelf cannot disconnect the printable open volume. It begins at Z=-0.5 mm, leaves an open bottom, and ends at `height - roof_thickness`, leaving a continuous roof. The only structural openings are this bottom and the post-process front entrance cut.

## Tests

```powershell
pytest
```

The suite covers periodic closure and tangent continuity, contour validity and containment, cyclic ring alignment, shell cavity/roof behavior, deterministic serialization, exports, and retained legacy helpers.
