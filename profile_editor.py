"""Bokeh server editor for V3 front and side profile control points.

Run ``python profile_editor.py`` or ``bokeh serve --show profile_editor.py``.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import cadquery as cq
import numpy as np
from bokeh.layouts import column, gridplot, row
from bokeh.models import Button, ColumnDataSource, Div, PointDrawTool, Spinner, TextInput
from bokeh.io import curdoc
from bokeh.plotting import figure
from bokeh.document import Document

from gecko_hide.config import GeckoHideConfig
from gecko_hide.export import export_model
from gecko_hide.generator import generate_profile_gecko_hide
from gecko_hide.profile import ProfileDesign, load_profile, save_profile
from gecko_hide.profile_curve import make_profile_curves
from gecko_hide.profile_preview import export_profile_plots
from render_preview import render_preview, render_profile_views

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"
CURRENT_PROFILE = ROOT / "profiles" / "current.json"


def _validation_config(profile: ProfileDesign) -> GeckoHideConfig:
    return GeckoHideConfig(
        width=max(profile.x_right) - min(profile.x_left),
        depth=max(profile.y_back) - min(profile.y_front),
        height=profile.height,
        wall_thickness=profile.wall_thickness,
        roof_thickness=profile.roof_thickness,
        entrance_width=profile.entrance_width,
        entrance_height=profile.entrance_height,
        entrance_offset_x=profile.entrance_offset_x,
    )


def build_document(doc: Document) -> None:
    """Install the interactive editor into a Bokeh document."""
    state = {"syncing": False}
    profile = ProfileDesign.default()
    load_path = TextInput(title="Profile file", value=str(CURRENT_PROFILE), width=500)
    status = Div(text="<b>Ready.</b> Drag a boundary control point horizontally.", width=500)
    controls = {
        "height": Spinner(title="Height (mm)", low=40, high=250, step=1, value=profile.height),
        "wall": Spinner(title="Wall Thickness (mm)", low=3.5, high=12, step=0.1, value=profile.wall_thickness),
        "roof": Spinner(title="Roof Thickness (mm)", low=3, high=20, step=0.1, value=profile.roof_thickness),
        "power": Spinner(title="Section Roundness", low=2, high=4.5, step=0.1, value=profile.section_power),
        "entrance_width": Spinner(title="Entrance Width (mm)", low=10, high=120, step=1, value=profile.entrance_width),
        "entrance_height": Spinner(title="Entrance Height (mm)", low=10, high=120, step=1, value=profile.entrance_height),
        "entrance_offset": Spinner(title="Entrance Offset X (mm)", low=-150, high=150, step=1, value=profile.entrance_offset_x),
    }
    sources = {
        "x_left": ColumnDataSource(data={"value": profile.x_left.copy(), "z": profile.z_levels.copy()}),
        "x_right": ColumnDataSource(data={"value": profile.x_right.copy(), "z": profile.z_levels.copy()}),
        "y_front": ColumnDataSource(data={"value": profile.y_front.copy(), "z": profile.z_levels.copy()}),
        "y_back": ColumnDataSource(data={"value": profile.y_back.copy(), "z": profile.z_levels.copy()}),
    }
    smooth = {
        key: ColumnDataSource(data={"value": [], "z": []})
        for key in sources
    }
    entrance = ColumnDataSource(data={"left": [0.0], "right": [0.0], "bottom": [0.0], "top": [0.0]})

    def current_profile() -> ProfileDesign:
        return ProfileDesign(
            height=float(controls["height"].value),
            z_levels=[float(value) for value in sources["x_left"].data["z"]],
            x_left=[float(value) for value in sources["x_left"].data["value"]],
            x_right=[float(value) for value in sources["x_right"].data["value"]],
            y_front=[float(value) for value in sources["y_front"].data["value"]],
            y_back=[float(value) for value in sources["y_back"].data["value"]],
            section_power=float(controls["power"].value),
            wall_thickness=float(controls["wall"].value),
            roof_thickness=float(controls["roof"].value),
            entrance_width=float(controls["entrance_width"].value),
            entrance_height=float(controls["entrance_height"].value),
            entrance_offset_x=float(controls["entrance_offset"].value),
        )

    preview_button = Button(label="Preview 3D", button_type="primary")
    generate_button = Button(label="Generate Final", button_type="success")

    def refresh(attr: str, old: object, new: object) -> None:
        if state["syncing"]:
            return
        try:
            current = current_profile()
            # Z levels are intentionally fixed: only boundary coordinates are editable.
            state["syncing"] = True
            for source in sources.values():
                source.data = {"value": list(source.data["value"]), "z": current.z_levels.copy()}
            state["syncing"] = False
            current = current_profile()
            curves = make_profile_curves(current)
            z = np.linspace(0.0, current.height, 256)
            for key, interpolator in (
                ("x_left", curves.x_left), ("x_right", curves.x_right),
                ("y_front", curves.y_front), ("y_back", curves.y_back),
            ):
                smooth[key].data = {"value": list(interpolator(z)), "z": list(z)}
            entrance.data = {
                "left": [current.entrance_offset_x - current.entrance_width / 2.0],
                "right": [current.entrance_offset_x + current.entrance_width / 2.0],
                "bottom": [0.0], "top": [current.entrance_height],
            }
            current.validate()
            status.text = "<b style='color:#237a3b'>Valid profile.</b> Smooth PCHIP curves updated."
            preview_button.disabled = False
            generate_button.disabled = False
        except ValueError as error:
            status.text = f"<b style='color:#aa2222'>Invalid profile:</b> {error}"
            preview_button.disabled = True
            generate_button.disabled = True
        finally:
            state["syncing"] = False

    def fit_ranges(current: ProfileDesign) -> None:
        x_limit = max(abs(value) for value in current.x_left + current.x_right) + 20.0
        y_limit = max(abs(value) for value in current.y_front + current.y_back) + 20.0
        front.x_range.start, front.x_range.end = -x_limit, x_limit
        side.x_range.start, side.x_range.end = -y_limit, y_limit
        front.y_range.start = side.y_range.start = 0.0
        front.y_range.end = side.y_range.end = current.height + 15.0

    def apply_profile(current: ProfileDesign) -> None:
        state["syncing"] = True
        controls["height"].value = current.height
        controls["wall"].value = current.wall_thickness
        controls["roof"].value = current.roof_thickness
        controls["power"].value = current.section_power
        controls["entrance_width"].value = current.entrance_width
        controls["entrance_height"].value = current.entrance_height
        controls["entrance_offset"].value = current.entrance_offset_x
        for key, values in (("x_left", current.x_left), ("x_right", current.x_right),
                            ("y_front", current.y_front), ("y_back", current.y_back)):
            sources[key].data = {"value": values.copy(), "z": current.z_levels.copy()}
        state["syncing"] = False
        fit_ranges(current)
        refresh("", None, None)

    front = figure(title="Front Profile (X-Z)", x_axis_label="X (mm)", y_axis_label="Z (mm)",
                   match_aspect=True, width=560, height=520, tools="pan,wheel_zoom,reset")
    front.line("value", "z", source=smooth["x_left"], line_width=3, color="#286a9f")
    front.line("value", "z", source=smooth["x_right"], line_width=3, color="#286a9f")
    front.quad(left="left", right="right", bottom="bottom", top="top", source=entrance,
               fill_alpha=0.08, line_dash="dashed", line_color="#b44428")
    left_renderer = front.scatter("value", "z", source=sources["x_left"], size=10, color="#123c5a")
    right_renderer = front.scatter("value", "z", source=sources["x_right"], size=10, color="#123c5a")
    front_draw = PointDrawTool(renderers=[left_renderer, right_renderer], add=False)
    front.add_tools(front_draw)
    front.toolbar.active_drag = front_draw

    side = figure(title="Side Profile (Y-Z)", x_axis_label="Y (mm)", y_axis_label="Z (mm)",
                  match_aspect=True, width=560, height=520, tools="pan,wheel_zoom,reset")
    side.line("value", "z", source=smooth["y_front"], line_width=3, color="#3b8654")
    side.line("value", "z", source=smooth["y_back"], line_width=3, color="#3b8654")
    front_renderer = side.scatter("value", "z", source=sources["y_front"], size=10, color="#1d5230")
    back_renderer = side.scatter("value", "z", source=sources["y_back"], size=10, color="#1d5230")
    side_draw = PointDrawTool(renderers=[front_renderer, back_renderer], add=False)
    side.add_tools(side_draw)
    side.toolbar.active_drag = side_draw

    def update_height(attr: str, old: float, new: float) -> None:
        if state["syncing"]:
            return
        if old > 0:
            state["syncing"] = True
            ratio = float(new) / float(old)
            for source in sources.values():
                source.data = {"value": list(source.data["value"]), "z": [float(z) * ratio for z in source.data["z"]]}
            state["syncing"] = False
        refresh("", None, None)

    controls["height"].on_change("value", update_height)
    for key, widget in controls.items():
        if key != "height":
            widget.on_change("value", refresh)
    for source in sources.values():
        source.on_change("data", refresh)

    def save_current() -> ProfileDesign:
        current = current_profile()
        current.validate()
        save_profile(current, CURRENT_PROFILE)
        export_profile_plots(current, OUTPUT)
        return current

    def on_save() -> None:
        try:
            save_current()
            status.text = f"<b style='color:#237a3b'>Saved.</b> {CURRENT_PROFILE}"
        except ValueError as error:
            status.text = f"<b style='color:#aa2222'>Cannot save:</b> {error}"

    def on_load() -> None:
        try:
            current = load_profile(load_path.value)
            apply_profile(current)
            status.text = f"<b style='color:#237a3b'>Loaded.</b> {load_path.value}"
        except ValueError as error:
            status.text = f"<b style='color:#aa2222'>Cannot load:</b> {error}"

    def on_preview() -> None:
        try:
            current = save_current()
            shape = generate_profile_gecko_hide(current, resolution="preview")
            OUTPUT.mkdir(parents=True, exist_ok=True)
            stl_path = OUTPUT / "profile_preview.stl"
            cq.exporters.export(shape, str(stl_path), tolerance=0.2, angularTolerance=0.15)
            render_preview(stl_path, OUTPUT / "profile_preview.png")
            status.text = "<b style='color:#237a3b'>Preview generated.</b> output/profile_preview.stl and .png"
        except (RuntimeError, ValueError) as error:
            status.text = f"<b style='color:#aa2222'>Preview failed:</b> {error}"

    def on_generate() -> None:
        try:
            current = save_current()
            config = _validation_config(current)
            shape = generate_profile_gecko_hide(current)
            stl_path, step_path = export_model(shape, config, OUTPUT, stem="gecko_hide_profile")
            render_profile_views(stl_path, OUTPUT)
            status.text = f"<b style='color:#237a3b'>Final model generated.</b> {stl_path.name}, {step_path.name}, profile_iso.png"
        except (RuntimeError, ValueError) as error:
            status.text = f"<b style='color:#aa2222'>Generation failed:</b> {error}"

    save_button = Button(label="Save Profile")
    load_button = Button(label="Load Profile")
    reset_button = Button(label="Reset Default")
    save_button.on_click(on_save)
    load_button.on_click(on_load)
    reset_button.on_click(lambda: apply_profile(ProfileDesign.default()))
    preview_button.on_click(on_preview)
    generate_button.on_click(on_generate)

    fit_ranges(profile)
    refresh("", None, None)
    doc.add_root(column(
        row(front, side),
        gridplot([[controls["height"], controls["wall"], controls["roof"], controls["power"]],
                  [controls["entrance_width"], controls["entrance_height"], controls["entrance_offset"], None]]),
        load_path,
        row(load_button, save_button, reset_button, preview_button, generate_button),
        status,
    ))
    doc.title = "Gecko Hide Profile Editor"


if __name__ == "__main__":
    subprocess.run([sys.executable, "-m", "bokeh", "serve", "--show", str(Path(__file__).resolve())], check=False)
else:
    build_document(curdoc())
