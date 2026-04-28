"""Optional SPA static-file mount.

When ``PANEL_FRONTEND_DIR`` points at a built SvelteKit ``build/`` directory we
serve it under ``/`` and fall back to ``index.html`` for any non-API path that
does not match a file on disk — the classic single-page-app routing trick.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

_RESERVED_PREFIXES = ("api", "docs", "redoc", "openapi.json")


def mount_frontend(app: FastAPI, frontend_dir: Path) -> None:
    """Serve *frontend_dir* as the root SPA with an ``index.html`` fallback."""
    root = frontend_dir.resolve()
    if not root.is_dir():
        raise RuntimeError(f"PANEL_FRONTEND_DIR does not exist or is not a directory: {root}")
    index = root / "index.html"
    if not index.is_file():
        raise RuntimeError(f"PANEL_FRONTEND_DIR is missing index.html: {index}")

    @app.get("/{spa_path:path}", include_in_schema=False)
    async def spa_catchall(spa_path: str) -> FileResponse:
        first = spa_path.split("/", 1)[0]
        if first in _RESERVED_PREFIXES:
            raise HTTPException(status_code=404)

        if spa_path:
            candidate = (root / spa_path).resolve()
            # Prevent directory traversal: the resolved path must stay inside root.
            if root in candidate.parents or candidate == root:
                if candidate.is_file():
                    return FileResponse(candidate)
        return FileResponse(index)
