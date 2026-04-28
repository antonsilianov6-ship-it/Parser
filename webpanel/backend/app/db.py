"""Database engine and session helpers."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from app.config import get_settings

_engine: Engine | None = None


def get_engine() -> Engine:
    """Lazily create the SQLAlchemy engine bound to the configured database URL."""
    global _engine
    if _engine is None:
        settings = get_settings()
        settings.db_path.parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(
            settings.database_url,
            echo=False,
            connect_args={"check_same_thread": False},
        )
    return _engine


def reset_engine() -> None:
    """Dispose of the cached engine (used in tests)."""
    global _engine
    if _engine is not None:
        _engine.dispose()
        _engine = None


def init_db() -> None:
    """Create all tables defined on :data:`SQLModel.metadata`."""
    from app import models  # noqa: F401  ensure models register with metadata

    SQLModel.metadata.create_all(get_engine())
    _apply_additive_migrations()


def _apply_additive_migrations() -> None:
    """Apply idempotent ``ALTER TABLE ... ADD COLUMN`` steps for existing DBs.

    SQLModel's ``create_all`` only handles missing *tables*; adding columns to an
    existing table is a no-op. Until we introduce Alembic this helper bridges the
    gap so upgrading a running panel doesn't require wiping ``panel.db``.
    """
    engine = get_engine()
    if engine.url.get_backend_name() != "sqlite":  # pragma: no cover — sqlite only
        return
    with engine.begin() as conn:
        existing = {
            row[1]
            for row in conn.exec_driver_sql("PRAGMA table_info(telegram_accounts)")
        }
        if "api_id" not in existing:
            conn.exec_driver_sql(
                "ALTER TABLE telegram_accounts ADD COLUMN api_id INTEGER"
            )
        if "api_hash" not in existing:
            conn.exec_driver_sql(
                "ALTER TABLE telegram_accounts ADD COLUMN api_hash VARCHAR(64)"
            )


def get_session() -> Iterator[Session]:
    """FastAPI dependency that yields a SQLModel session."""
    with Session(get_engine()) as session:
        yield session
