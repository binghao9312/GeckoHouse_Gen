"""Bokeh V4 topographic-contour editor.

Run ``python contour_editor.py`` or ``bokeh serve --show contour_editor.py``.
"""

from __future__ import annotations

import base64
from copy import deepcopy
from pathlib import Path
import subprocess
import sys

import cadquery as cq
from bokeh.document import Document
from bokeh.io import curdoc
from bokeh.layouts import column, row
from bokeh.models import Button, ColumnDataSource, Div, PointDrawTool, Select, Spinner, TabPanel, Tabs, TextInput
from bokeh.plotting import figure

from gecko_hide.contour import ContourDesign, ContourLevel, load_design, save_design
from gecko_hide.contour_shell import sample_contour
from gecko_hide.export import export_model
from gecko_hide.generator import generate_contour_gecko_hide
from render_preview import render_contour_views, render_preview

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"
CURRENT_DESIGN = ROOT / "designs" / "current.json"


def build_document(doc: Document) -> None:
    """Install the closed-contour V4 editing workflow into a Bokeh document."""
    state = {"syncing": False, "design": ContourDesign.default(), "history": []}
    design_path = TextInput(title="Design file", value=str(CURRENT_DESIGN), width=500)
    status = Div(text="<b>Step 1 — Footprint.</b> Drag the closed-loop control points in XY.", width=760)
    controls = {
        "height": Spinner(title="Height (mm)", low=40, high=250, step=1, value=75.0),
        "wall": Spinner(title="Wall Thickness (mm)", low=3.5, high=12, step=0.1, value=4.0),
        "roof": Spinner(title="Roof Thickness (mm)", low=3, high=20, step=0.1, value=5.0),
        "level": Spinner(title="Contour Level", low=0, high=6, step=1, value=0),
        "entrance_width": Spinner(title="Entrance Width (mm)", low=10, high=120, step=1, value=55.0),
        "entrance_height": Spinner(title="Entrance Height (mm)", low=10, high=70, step=1, value=40.0),
        "entrance_offset": Spinner(title="Entrance Offset (mm)", low=-150, high=150, step=1, value=-30.0),
    }
    surface_mode = Select(title="Surface to This Level", value="smooth", options=["smooth", "step"], width=180)
    level_info = Div(width=360)
    contour_sources: list[ColumnDataSource] = []
    control_source = ColumnDataSource(data={"x": [], "y": []})
    summit_source = ColumnDataSource(data={"x": [], "y": []})

    canvas = figure(
        title="Top View — Closed XY Contours",
        x_axis_label="X (mm)", y_axis_label="Y (mm)", match_aspect=True,
        width=760, height=650, tools="pan,wheel_zoom,reset,save",
    )
    canvas.grid.grid_line_alpha = 0.35
    colors = ("#315d7f", "#3f7b91", "#509c94", "#76ad7c", "#aeab5b", "#c8824d", "#b7554b")
    for index in range(7):
        source = ColumnDataSource(data={"x": [], "y": []})
        contour_sources.append(source)
        canvas.line("x", "y", source=source, line_width=3 if index == 0 else 2,
                    line_color=colors[index], line_alpha=0.85)
    canvas.line("x", "y", source=control_source, line_width=3, line_color="#111111")
    controls_renderer = canvas.scatter("x", "y", source=control_source, size=10, color="#111111")
    summit_renderer = canvas.scatter("x", "y", source=summit_source, size=13, marker="star", color="#d35b33")
    point_tool = PointDrawTool(renderers=[controls_renderer], add=False)
    summit_tool = PointDrawTool(renderers=[summit_renderer], add=False)
    canvas.add_tools(point_tool, summit_tool)
    canvas.toolbar.active_drag = point_tool

    preview_panel = Div(
        text="<b>3D Preview</b><br>Choose <em>Preview 3D</em>; the generated image appears here.",
        width=760,
        height=650,
    )
    views = Tabs(tabs=[
        TabPanel(child=canvas, title="Top View / Edit"),
        TabPanel(child=preview_panel, title="3D Preview"),
    ])

    preview_button = Button(label="Preview 3D", button_type="primary")
    generate_button = Button(label="Generate STL + STEP", button_type="success")
    generate_contours_button = Button(label="Generate Contours")

    def design() -> ContourDesign:
        return state["design"]

    def selected_index() -> int:
        return int(controls["level"].value)


    def remember_state() -> None:
        """Keep bounded complete-design snapshots for the explicit Previous Step action."""
        history: list[ContourDesign] = state["history"]
        history.append(deepcopy(design()))
        del history[:-20]

    def fit_range(current: ContourDesign) -> None:
        points = [point for level in current.levels for point in level.points]
        x_values, y_values = zip(*points, strict=True)
        margin = 20.0
        canvas.x_range.start, canvas.x_range.end = min(x_values) - margin, max(x_values) + margin
        canvas.y_range.start, canvas.y_range.end = min(y_values) - margin, max(y_values) + margin

    def sync_controls(current: ContourDesign) -> None:
        state["syncing"] = True
        controls["height"].value = current.height
        controls["wall"].value = current.wall_thickness
        controls["roof"].value = current.roof_thickness
        controls["entrance_width"].value = current.entrance_width
        controls["entrance_height"].value = current.entrance_height
        controls["entrance_offset"].value = current.entrance_offset
        index = selected_index()
        surface_mode.value = current.levels[index].surface_mode
        surface_mode.disabled = index == 0
        controls["level"].high = len(current.levels) - 1
        controls["level"].value = min(selected_index(), len(current.levels) - 1)
        state["syncing"] = False

    def refresh_canvas() -> None:
        current = design()
        state["syncing"] = True
        try:
            for source, level in zip(contour_sources, current.levels, strict=False):
                ring = sample_contour(level.points, count=192)
                source.data = {"x": [*ring[:, 0], ring[0, 0]], "y": [*ring[:, 1], ring[0, 1]]}
            index = selected_index()
            active = current.levels[index]
            control_source.data = {"x": [point[0] for point in active.points], "y": [point[1] for point in active.points]}
            summit_source.data = {"x": [current.summit[0]], "y": [current.summit[1]]}
            surface_mode.value = active.surface_mode
            surface_mode.disabled = index == 0
            level_info.text = (
                f"<b>Level {index + 1} of {len(current.levels)}</b> — {active.z:g} mm — "
                f"transition: <b>{'Stepped' if active.surface_mode == 'step' else 'Smooth'}</b>"
            )
        finally:
            state["syncing"] = False

    def validation_message(error: ValueError) -> str:
        """Turn CAD constraints into one direct problem and recovery instruction."""
        message = str(error)
        if "self-intersects" in message:
            fix = "Move the crossed control point back inside the loop."
        elif "outside contour" in message:
            fix = "Move this level inward until it sits inside the previous ring."
        elif "slope" in message:
            fix = "Reduce the horizontal shift between these two levels."
        elif "orientation" in message:
            fix = "Keep every contour's control points in the same circular direction."
        else:
            fix = "Use Previous Step to restore the last valid design, then adjust the highlighted level."
        return f"<b style='color:#aa2222'>Design needs correction.</b> {message}<br><b>Fix:</b> {fix} Preview and export stay disabled."

    def validate_and_refresh() -> None:
        try:
            current = design()
            current.validate()
            refresh_canvas()
            status.text = "<b style='color:#237a3b'>Valid contours.</b> Select a level and drag its closed-loop points."
            preview_button.disabled = False
            generate_button.disabled = False
        except ValueError as error:
            status.text = validation_message(error)
            preview_button.disabled = True
            generate_button.disabled = True

    def update_selected_points(attr: str, old: object, new: object) -> None:
        if state["syncing"]:
            return
        remember_state()
        active = design().levels[selected_index()]
        active.points = [[float(x), float(y)] for x, y in zip(control_source.data["x"], control_source.data["y"], strict=True)]
        active.manually_modified = True
        validate_and_refresh()

    def update_summit(attr: str, old: object, new: object) -> None:
        if state["syncing"] or len(summit_source.data["x"]) != 1:
            return
        remember_state()
        design().summit = [float(summit_source.data["x"][0]), float(summit_source.data["y"][0])]
        validate_and_refresh()

    def update_parameters(attr: str, old: object, new: object) -> None:
        if state["syncing"]:
            return
        remember_state()
        current = design()
        old_height = current.height
        current.height = float(controls["height"].value)
        if old_height > 0 and current.height != old_height:
            ratio = current.height / old_height
            for level in current.levels:
                level.z *= ratio
        current.wall_thickness = float(controls["wall"].value)
        current.roof_thickness = float(controls["roof"].value)
        current.entrance_width = float(controls["entrance_width"].value)
        current.entrance_height = float(controls["entrance_height"].value)
        current.entrance_offset = float(controls["entrance_offset"].value)
        validate_and_refresh()

    def select_level(attr: str, old: object, new: object) -> None:
        if not state["syncing"]:
            refresh_canvas()

    def update_surface_mode(attr: str, old: str, new: str) -> None:
        if state["syncing"]:
            return
        remember_state()
        design().levels[selected_index()].surface_mode = new
        validate_and_refresh()


    control_source.on_change("data", update_selected_points)
    summit_source.on_change("data", update_summit)
    controls["level"].on_change("value", select_level)
    surface_mode.on_change("value", update_surface_mode)
    for name, widget in controls.items():
        if name != "level":
            widget.on_change("value", update_parameters)

    def save_current() -> ContourDesign:
        current = design()
        current.validate()
        save_design(current, CURRENT_DESIGN)
        return current

    def on_save() -> None:
        try:
            save_current()
            status.text = f"<b style='color:#237a3b'>Saved design.</b> {CURRENT_DESIGN}"
        except ValueError as error:
            status.text = f"<b style='color:#aa2222'>Cannot save:</b> {error}"

    def on_load() -> None:
        try:
            remember_state()
            state["design"] = load_design(design_path.value)
            sync_controls(design())
            fit_range(design())
            validate_and_refresh()
            status.text = f"<b style='color:#237a3b'>Loaded design.</b> {design_path.value}"
        except ValueError as error:
            status.text = f"<b style='color:#aa2222'>Cannot load:</b> {error}"

    def on_generate_contours() -> None:
        try:
            remember_state()
            design().generate_contours()
            sync_controls(design())
            validate_and_refresh()
            status.text = "<b style='color:#237a3b'>Step 2 — Contours generated.</b> Select any ring to refine it."
        except ValueError as error:
            status.text = f"<b style='color:#aa2222'>Cannot generate contours:</b> {error}"

    def on_preview() -> None:
        try:
            current = save_current()
            shape = generate_contour_gecko_hide(current, resolution="preview")
            OUTPUT.mkdir(parents=True, exist_ok=True)
            stl_path = OUTPUT / "gecko_hide_contour_preview.stl"
            cq.exporters.export(shape, str(stl_path), tolerance=0.2, angularTolerance=0.15)
            preview_path = OUTPUT / "gecko_hide_contour_preview.png"
            render_preview(stl_path, preview_path)
            encoded = base64.b64encode(preview_path.read_bytes()).decode("ascii")
            preview_panel.text = f"<img src='data:image/png;base64,{encoded}' width='760' alt='Contour 3D preview'>"
            views.active = 1
            status.text = "<b style='color:#237a3b'>3D preview ready.</b> Switch back with the Top View / Edit tab."
        except (RuntimeError, ValueError) as error:
            status.text = f"<b style='color:#aa2222'>Preview failed:</b> {error}"

    def on_generate() -> None:
        try:
            current = save_current()
            shape = generate_contour_gecko_hide(current)
            from build import _config_for_design
            stl_path, step_path = export_model(shape, _config_for_design(current), OUTPUT, stem="gecko_hide_contour")
            render_contour_views(stl_path, OUTPUT)
            status.text = f"<b style='color:#237a3b'>Step 4 — Exported.</b> {stl_path.name}, {step_path.name}"
        except (RuntimeError, ValueError) as error:
            status.text = f"<b style='color:#aa2222'>Generation failed:</b> {error}"

    def on_previous() -> None:
        history: list[ContourDesign] = state["history"]
        if not history:
            status.text = "<b>No earlier edit is available.</b> The current design is unchanged."
            return
        state["design"] = history.pop()
        sync_controls(design())
        fit_range(design())
        validate_and_refresh()
        status.text = "<b style='color:#237a3b'>Returned to the previous edit.</b>"

    save_button = Button(label="Save Design")
    load_button = Button(label="Load Design")
    reset_button = Button(label="Reset")
    previous_button = Button(label="Previous Step")
    save_button.on_click(on_save)
    load_button.on_click(on_load)
    reset_button.on_click(lambda: (remember_state(), state.__setitem__("design", ContourDesign.default()), sync_controls(design()), fit_range(design()), validate_and_refresh()))
    previous_button.on_click(on_previous)
    generate_contours_button.on_click(on_generate_contours)
    preview_button.on_click(on_preview)
    generate_button.on_click(on_generate)

    sync_controls(design())
    fit_range(design())
    validate_and_refresh()
    doc.add_root(column(
        views,
        row(generate_contours_button, controls["level"], surface_mode, level_info),
        row(controls["height"], controls["wall"], controls["roof"]),
        row(controls["entrance_width"], controls["entrance_height"], controls["entrance_offset"]),
        design_path,
        row(load_button, save_button, previous_button, reset_button, preview_button, generate_button),
        status,
    ))
    doc.title = "Gecko Hide Designer — V4 Topography"


if __name__ == "__main__":
    subprocess.run([sys.executable, "-m", "bokeh", "serve", "--show", str(Path(__file__).resolve())], check=False)
else:
    build_document(curdoc())
