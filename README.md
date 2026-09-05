# Gecko Hide Generator — V5 Rock Shelter Designer

V5 is a local CAD-style editor for one canonical `ContourDesign` stack. Top, Front, Side, and interactive 3D views edit the same closed XY contour control points; Front transforms X bounds, Side transforms Y bounds, and either orthographic view can move an intermediate level Z. There is no independent front/side profile model.

The default is a full-sided, asymmetric rock shelter: five near-full wall levels, a controlled broad roof shoulder, and a broad roof top. It avoids V4's shrinking mountain and terrace-style default.

## Install

Python 3.11+, Node 20+, CadQuery, NumPy, SciPy, Shapely, FastAPI, trimesh, Matplotlib, and pytest:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
cd frontend
npm install
npm run build
cd ..
```

`frontend/dist` is served by the Python launcher after the production Vite build. During UI development, use `npm run dev`; Vite proxies `/api` to the editor API.

## V5 four-view editor

```powershell
python profile_editor.py
```

Open `http://127.0.0.1:8000`. The desktop workspace shows all four synchronized views at once:

- **Top** — direct XY control-point editing, grid, entrance direction, selected-ring highlight.
- **Front** — X/Z left, right, center, and Z handles plus the draggable 7-handle entrance arch.
- **Side** — Y/Z front, back, center, and Z handles.
- **3D** — Three.js orbit, pan, zoom, and Top/Front/Side/Iso controls generated directly from the contour rings; it never invokes CadQuery while dragging.

The shared level timeline selects one contour in all views. Base and roof-top Z are locked. Snap supports Off, 1 mm, 2 mm, and 5 mm. Undo/redo applies complete design snapshots to point, envelope, level, entrance, and property edits. The inspector exposes exact dimensions, roles, roof limits, and relief settings.

The local API supplies `GET /api/design`, `POST /api/design/validate`, `POST /api/design/preview-mesh`, `POST /api/design/save`, `POST /api/design/load`, and `POST /api/design/export`. 2D interaction remains client-side and validation is debounced.

## Canonical contour model

`ContourDesign` JSON is version 3. Each `ContourLevel` has a `role` (`wall`, `roof_shoulder`, or `roof_top`), `smooth`/advanced `ledge` transition, and Z/shape locks. Version-2 files migrate explicitly: their `step` mode becomes `ledge`, entrance arch handles are created from retained width/height fields, and roles are derived without changing existing control points.

Wall transitions remain nested except for a small clearance-sized organic swell. A `roof_shoulder` may extend outward only when its maximum local expansion is below both `max_overhang_xy` (default 8 mm) and `max_overhang_ratio` (default 8%), with the existing local-slope and solid checks retained. The continuous structural shell remains open at the bottom, retains its roof, and has the authored front entrance cut only.

Appearance settings (`relief_enabled`, seed, depth, gap, scale) are persisted separately from macro geometry. The relief seed never changes contour geometry. When enabled in the editor, the fallback creates `gecko_hide_v5_textured.stl`: a deterministic, outward-only, shallow rounded cell relief over the structural shell. `gecko_hide_v5.step` remains the exact untextured structural BREP and is never claimed to contain texture.

## CLI and exports

```powershell
python build.py
python build.py --design designs/current.json
```

The default CLI creates a new V5 design and writes:

```text
output/gecko_hide_v5.stl
output/gecko_hide_v5.step
output/gecko_hide_v5_iso.png
output/gecko_hide_v5_top.png
output/gecko_hide_v5_front.png
output/gecko_hide_v5_side.png
```

Authored designs take precedence over dimension flags. `--legacy-profile` keeps the retained V3 mode separate from the V5 workflow.

## Tests

```powershell
pytest
```

The suite covers periodic closure, transition validation, controlled roof overhang, Front/Side affine edits of canonical control points, center translation, Z spacing, V2 migration, deterministic save/load, one-solid CadQuery shell construction, and export geometry checks.
