"""Health-check endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from app import __version__

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """Return a static OK response used by uptime probes."""
    return {"status": "ok", "version": __version__}
