"""Regression test for ``src.export.post_parse.clear_messages_table``.

The web-panel pipes ``PARSER_CLEAR_DB_AFTER_EXPORT=1`` into the parser
subprocess after a successful Docs / NotebookLM export. The parser then
deletes every row from the ``messages`` table so the user's per-user
SQLite doesn't keep growing — but the entity / processed-link cache
(``cache.json`` next to ``parser.db``) MUST stay intact so the next run
doesn't burn ``get_entity`` calls.

This test bypasses the FastAPI client entirely and exercises the helper
against a temp DB.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

# The parser source tree lives at the repo root, two levels above the
# webpanel/backend package. Add it to sys.path so tests can ``import src.*``
# without installing the parser as a wheel.
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


@pytest.fixture
def parser_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Build a minimal ``parser.db`` with a ``messages`` table + 3 rows."""
    db_path = tmp_path / "parser.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY,
                channel TEXT,
                text TEXT
            )
            """
        )
        conn.executemany(
            "INSERT INTO messages (channel, text) VALUES (?, ?)",
            [("a", "hello"), ("b", "world"), ("c", "!")],
        )
        conn.commit()

    # Point ``src.config.DATABASE_CONFIG['DB_PATH']`` at our temp DB.
    monkeypatch.setenv("PARSER_DB_PATH", str(db_path))
    # Reload the parser config so the env-override picks up.
    import importlib

    import src.config as config_mod

    importlib.reload(config_mod)
    yield db_path
    # Reload again after the test so other tests get a clean module.
    importlib.reload(config_mod)


def test_clear_messages_preserves_cache(parser_db: Path, tmp_path: Path) -> None:
    cache_path = tmp_path / "cache.json"
    cache_path.write_text(json.dumps({"entities": {"@chan": 12345}}))

    from src.export import post_parse  # imported after env-override took effect

    removed = post_parse.clear_messages_table()
    assert removed == 3

    # messages gone, cache still readable.
    with sqlite3.connect(parser_db) as conn:
        rows = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    assert rows == 0
    assert cache_path.exists()
    assert json.loads(cache_path.read_text()) == {"entities": {"@chan": 12345}}


def test_panel_mode_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    """``is_panel_managed`` flips when either env flag is set."""
    from src.export import post_parse

    monkeypatch.delenv("PARSER_EXPORT_TO_DOCS", raising=False)
    monkeypatch.delenv("PARSER_EXPORT_TO_NOTEBOOKLM", raising=False)
    assert post_parse.is_panel_managed() is False
    assert post_parse.docs_enabled() is True  # CLI default — exports to Docs
    assert post_parse.notebooklm_enabled() is False

    monkeypatch.setenv("PARSER_EXPORT_TO_DOCS", "0")
    monkeypatch.setenv("PARSER_EXPORT_TO_NOTEBOOKLM", "1")
    assert post_parse.is_panel_managed() is True
    assert post_parse.docs_enabled() is False
    assert post_parse.notebooklm_enabled() is True
