"""Compatibility launcher for the V4 topographic contour editor.

Run ``python profile_editor.py``; legacy V3 profiles remain at
``legacy/profile_editor_v3.py`` and are not the primary workflow.
"""

from contour_editor import build_document


if __name__ == "__main__":
    from pathlib import Path
    import subprocess
    import sys

    subprocess.run([sys.executable, "-m", "bokeh", "serve", "--show", str(Path(__file__).with_name("contour_editor.py"))], check=False)
else:
    from bokeh.io import curdoc

    build_document(curdoc())
