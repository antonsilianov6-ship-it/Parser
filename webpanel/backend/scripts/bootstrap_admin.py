"""Create the first panel user from the command line.

Usage::

    PANEL_JWT_SECRET=... python -m scripts.bootstrap_admin \
        --username admin --password 'hunter2'

The script is idempotent: if the username already exists, its password is updated and
``is_active`` is forced to True.
"""

from __future__ import annotations

import argparse
import getpass
import sys
from datetime import UTC, datetime

from sqlmodel import Session, select

from app.db import get_engine, init_db
from app.models.user import User
from app.security import hash_password


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap or reset a panel admin user")
    parser.add_argument("--username", required=True, help="Username to create or update")
    parser.add_argument(
        "--password",
        default=None,
        help="Password (if omitted, read interactively from stdin)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    password = args.password or getpass.getpass("Password: ")
    if len(password) < 8:
        print("error: password must be at least 8 characters", file=sys.stderr)
        return 2

    init_db()
    with Session(get_engine()) as session:
        existing = session.exec(select(User).where(User.username == args.username)).first()
        if existing is None:
            user = User(
                username=args.username,
                password_hash=hash_password(password),
                is_active=True,
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            print(f"created user id={user.id} username={user.username!r}")
        else:
            existing.password_hash = hash_password(password)
            existing.is_active = True
            existing.updated_at = datetime.now(tz=UTC)
            session.add(existing)
            session.commit()
            print(f"updated user id={existing.id} username={existing.username!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
