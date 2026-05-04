"""FastAPI application entry point."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.config import get_settings
from app.db import init_db
from app.routers import (
    auth,
    google,
    health,
    jobs,
    parser_config,
    parser_db,
    telegram_accounts,
    users,
)
from app.static import mount_frontend


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


def create_app() -> FastAPI:
    """Application factory. Used by tests to build isolated instances."""
    settings = get_settings()
    app = FastAPI(
        title="Parser Web Panel API",
        version=__version__,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(telegram_accounts.router)
    app.include_router(jobs.router)
    app.include_router(parser_config.router)
    app.include_router(parser_db.router)
    app.include_router(google.router)

    if settings.frontend_dir is not None:
        mount_frontend(app, settings.frontend_dir)

    return app


app = create_app()
