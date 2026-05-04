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
    _seed_existing_users()


def _seed_existing_users() -> None:
    """Make sure every panel user has an isolated parser data directory.

    Re-run on every startup; no-op once the per-user dirs already exist. The
    smallest user id (typically the bootstrap admin) gets the legacy global
    files copied from the repo root if their own dir is still empty, so an
    upgrade from a pre-PR-#9 install doesn't lose ``config.json`` / ``channels.txt``.
    """
    # Imported here to avoid a circular import (services -> config -> db).
    from sqlmodel import Session, select

    from app.models.user import User
    from app.services import parser_files

    with Session(get_engine()) as session:
        users = list(session.exec(select(User).order_by(User.id)))
    if not users:
        return
    first_id = min((u.id for u in users if u.id is not None), default=None)
    for user in users:
        if user.id is None:
            continue
        parser_files.seed_user_dir(user.id, copy_legacy=(user.id == first_id))


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

        user_cols = {
            row[1]
            for row in conn.exec_driver_sql("PRAGMA table_info(users)")
        }
        if "google_doc_id" not in user_cols:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN google_doc_id VARCHAR(128)"
            )
        if "google_drive_folder_id" not in user_cols:
            conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN google_drive_folder_id VARCHAR(128)"
            )

        job_cols = {
            row[1]
            for row in conn.exec_driver_sql("PRAGMA table_info(jobs)")
        }
        if "export_to_docs" not in job_cols:
            conn.exec_driver_sql(
                "ALTER TABLE jobs ADD COLUMN export_to_docs INTEGER DEFAULT 0"
            )
        if "export_to_notebooklm" not in job_cols:
            conn.exec_driver_sql(
                "ALTER TABLE jobs ADD COLUMN export_to_notebooklm INTEGER DEFAULT 0"
            )
        if "allow_rotation" not in job_cols:
            conn.exec_driver_sql(
                "ALTER TABLE jobs ADD COLUMN allow_rotation INTEGER DEFAULT 1"
            )
        if "retry_count" not in job_cols:
            conn.exec_driver_sql(
                "ALTER TABLE jobs ADD COLUMN retry_count INTEGER DEFAULT 0"
            )


def get_session() -> Iterator[Session]:
    """FastAPI dependency that yields a SQLModel session."""
    with Session(get_engine()) as session:
        yield session
