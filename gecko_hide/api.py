"""FastAPI backend for the V5 multi-view contour editor."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import numpy as np
from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .contour import ContourDesign, load_design, save_design
from .contour_shell import align_contours, sample_contour
from .export import export_model
from .generator import generate_contour_gecko_hide
from .relief import export_textured_stl

ROOT = Path(__file__).resolve().parents[1]
CURRENT_DESIGN = ROOT / "designs" / "current.json"
OUTPUT = ROOT / "output"
FRONTEND_DIST = ROOT / "frontend" / "dist"


DESIGN_INVALID = "DESIGN_INVALID"
EXPORT_BUILD_FAILED = "EXPORT_BUILD_FAILED"
EXPORT_ARTIFACT_INVALID = "EXPORT_ARTIFACT_INVALID"
EXPORT_RENDER_FAILED = "EXPORT_RENDER_FAILED"
EXPORT_TEXTURE_FAILED = "EXPORT_TEXTURE_FAILED"


def _api_error(status_code: int, code: str, message: str) -> HTTPException:
    """Return a stable error contract for the local designer UI."""
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def _decode(payload: Mapping[str, Any]) -> ContourDesign:
    try:
        return ContourDesign.from_mapping(payload)
    except (TypeError, ValueError) as error:
        raise _api_error(422, DESIGN_INVALID, str(error)) from error


def _current_design() -> ContourDesign:
    if CURRENT_DESIGN.is_file():
        return load_design(CURRENT_DESIGN)
    design = ContourDesign.default()
    save_design(design, CURRENT_DESIGN)
    return design


def _preview_mesh(design: ContourDesign) -> dict[str, list[float] | list[int]]:
    """Create the lightweight triangle-strip preview directly from contour rings."""
    rings = align_contours([sample_contour(level.points, count=64) for level in design.levels])
    positions = np.concatenate([
        np.column_stack((ring, np.full(len(ring), level.z)))
        for ring, level in zip(rings, design.levels, strict=True)
    ])
    indices: list[int] = []
    ring_size = len(rings[0])
    for level_index in range(len(rings) - 1):
        lower = level_index * ring_size
        upper = (level_index + 1) * ring_size
        for point_index in range(ring_size):
            next_point = (point_index + 1) % ring_size
            indices.extend((lower + point_index, lower + next_point, upper + point_index))
            indices.extend((lower + next_point, upper + next_point, upper + point_index))
    top_center = len(positions)
    positions = np.vstack((positions, [rings[-1][:, 0].mean(), rings[-1][:, 1].mean(), design.height]))
    top = (len(rings) - 1) * ring_size
    for point_index in range(ring_size):
        indices.extend((top_center, top + point_index, top + (point_index + 1) % ring_size))
    normals = np.zeros_like(positions)
    triangles = np.asarray(indices, dtype=int).reshape(-1, 3)
    for a, b, c in triangles:
        normal = np.cross(positions[b] - positions[a], positions[c] - positions[a])
        length = np.linalg.norm(normal)
        if length:
            normals[[a, b, c]] += normal / length
    lengths = np.linalg.norm(normals, axis=1)
    normals[lengths > 0] /= lengths[lengths > 0, None]
    return {"positions": positions.ravel().round(6).tolist(), "normals": normals.ravel().round(6).tolist(), "indices": indices}


def create_app() -> FastAPI:
    """Build the local V5 editor API and serve a production Vite build when present."""
    app = FastAPI(title="Gecko Hide Designer V5", version="5")

    @app.get("/api/design")
    def get_design() -> dict[str, Any]:
        return _current_design().as_dict()

    @app.post("/api/design/validate")
    def validate_design(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        design = _decode(payload)
        return {"valid": True, "design": design.as_dict()}

    @app.post("/api/design/preview-mesh")
    def preview_mesh(payload: dict[str, Any] = Body(...)) -> dict[str, list[float] | list[int]]:
        return _preview_mesh(_decode(payload))

    @app.post("/api/design/save")
    def save_current(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        design = _decode(payload)
        destination = save_design(design, CURRENT_DESIGN)
        return {"path": str(destination), "design": design.as_dict()}

    @app.post("/api/design/load")
    def load_current() -> dict[str, Any]:
        return _current_design().as_dict()

    @app.post("/api/design/export")
    def export_design(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        design = _decode(payload)
        save_design(design, CURRENT_DESIGN)
        try:
            from build import _config_for_design

            shape = generate_contour_gecko_hide(design, resolution="final")
            stl_path, step_path = export_model(shape, _config_for_design(design), OUTPUT, stem="gecko_hide_v5")
        except (RuntimeError, ValueError) as error:
            code = EXPORT_ARTIFACT_INVALID if "round-trip validation" in str(error) else EXPORT_BUILD_FAILED
            raise _api_error(422, code, str(error)) from error
        try:
            from render_preview import render_v5_contour_views

            views = render_v5_contour_views(stl_path, OUTPUT)
        except (RuntimeError, ValueError) as error:
            raise _api_error(422, EXPORT_RENDER_FAILED, str(error)) from error
        result: dict[str, Any] = {"stl": stl_path.name, "step": step_path.name, "views": [path.name for path in views]}
        if design.appearance.relief_enabled:
            try:
                textured = export_textured_stl(stl_path, OUTPUT / "gecko_hide_v5_textured.stl", design)
            except (RuntimeError, ValueError) as error:
                raise _api_error(422, EXPORT_TEXTURE_FAILED, str(error)) from error
            result["textured_stl"] = textured.name
            result["structural_step"] = step_path.name
        return result

    if FRONTEND_DIST.is_dir():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

        @app.get("/{path:path}")
        def editor(path: str) -> FileResponse:
            return FileResponse(FRONTEND_DIST / "index.html")

    return app


app = create_app()
