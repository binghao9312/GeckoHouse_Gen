"""Launch the V5 local multi-view Gecko Hide Designer."""

from __future__ import annotations

import uvicorn


if __name__ == "__main__":
    uvicorn.run("gecko_hide.api:app", host="127.0.0.1", port=8000, reload=False)
