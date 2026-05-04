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


@pytest.mark.asyncio
async def test_failed_docs_export_skips_db_clear_in_cli_mode(
    parser_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CLI mode: Docs export crashes -> messages table MUST stay intact.

    Regression for the post-PR-#11 finding (Devin Review): the
    earlier patch made ``success`` mode-dependent for exit-code
    backwards compatibility, but ``clear_db_after_export`` still has
    to gate on whether exports actually succeeded. Otherwise
    ``PARSER_CLEAR_DB_AFTER_EXPORT=1`` + a failed Docs export would
    silently delete messages that never reached Google.
    """
    import sys
    import types

    # The test environment doesn't ship the Google API client (it lives
    # in requirements.runtime.txt for the parser image only). Stub the
    # GoogleDocsExporter import done inside run_export_pipeline so we
    # can exercise the failure branch without pulling googleapiclient
    # into webpanel/backend deps.
    fake_export = types.ModuleType("src.export.google_docs")

    class _BoomExporter:
        def __init__(self) -> None:
            raise RuntimeError("creds missing")

    fake_export.GoogleDocsExporter = _BoomExporter  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "src.export.google_docs", fake_export)

    monkeypatch.setenv("PARSER_CLEAR_DB_AFTER_EXPORT", "1")
    monkeypatch.delenv("PARSER_EXPORT_TO_DOCS", raising=False)  # CLI mode
    monkeypatch.delenv("PARSER_EXPORT_TO_NOTEBOOKLM", raising=False)

    import importlib

    import src.export.post_parse as pp

    importlib.reload(pp)

    result = await pp.run_export_pipeline([{"id": 1, "text": "x"}])
    # CLI: returns True (historical exit-code preservation).
    assert result is True
    # …but the messages table MUST still be intact.
    with sqlite3.connect(parser_db) as conn:
        rows = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    assert rows == 3


@pytest.mark.asyncio
async def test_failed_docs_export_skips_db_clear_in_panel_mode(
    parser_db: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Panel mode: same data-safety guard, plus success=False return."""
    import sys
    import types

    fake_export = types.ModuleType("src.export.google_docs")

    class _BoomExporter:
        def __init__(self) -> None:
            raise RuntimeError("creds missing")

    fake_export.GoogleDocsExporter = _BoomExporter  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "src.export.google_docs", fake_export)

    monkeypatch.setenv("PARSER_CLEAR_DB_AFTER_EXPORT", "1")
    monkeypatch.setenv("PARSER_EXPORT_TO_DOCS", "1")
    monkeypatch.setenv("PARSER_EXPORT_TO_NOTEBOOKLM", "0")

    import importlib

    import src.export.post_parse as pp

    importlib.reload(pp)

    result = await pp.run_export_pipeline([{"id": 1, "text": "x"}])
    # Panel: surfaces failure to jobs UI.
    assert result is False
    # And still doesn't touch the DB.
    with sqlite3.connect(parser_db) as conn:
        rows = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    assert rows == 3
