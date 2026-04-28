"""Application settings loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the web panel backend."""

    model_config = SettingsConfigDict(
        env_prefix="PANEL_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    jwt_secret: str = Field(default="", description="HS256 signing secret for JWT tokens")
    jwt_algorithm: str = Field(default="HS256")
    jwt_access_ttl_minutes: int = Field(default=60, ge=1)

    db_path: Path = Field(default=Path("panel.db"))

    allow_registration: bool = Field(
        default=False,
        description="When true, POST /api/users is open to anonymous callers",
    )

    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173"],
        description="CSV list of allowed CORS origins for the SvelteKit dev server",
    )

    frontend_dir: Path | None = Field(
        default=None,
        description="If set, FastAPI serves the built SvelteKit SPA from this directory "
        "under '/' (with SPA fallback). Leave unset in API-only deployments.",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            parts = [item.strip() for item in value.split(",") if item.strip()]
            return parts or ["http://localhost:5173"]
        return value

    @property
    def database_url(self) -> str:
        """Return a SQLAlchemy-compatible URL for the configured SQLite file."""
        return f"sqlite:///{self.db_path}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance."""
    return Settings()
