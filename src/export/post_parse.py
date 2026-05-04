# -*- coding: utf-8 -*-
"""Post-parse экспорт-пайплайн для запусков из web-panel.

Когда панель запускает парсер, она пробрасывает env-флаги:

- ``PARSER_EXPORT_TO_DOCS`` / ``PARSER_EXPORT_TO_NOTEBOOKLM`` — что именно
  делать с уже распарсенными сообщениями;
- ``PARSER_CLEAR_DB_AFTER_EXPORT`` — после успешного экспорта удалить все
  строки из ``messages`` (entity-cache в ``cache.json`` остаётся, чтобы не
  жечь ``get_entity`` на TG-лимиты);
- ``GOOGLE_CREDS_PATH`` / ``GOOGLE_DOC_ID`` / ``NOTEBOOKLM_AUTH_JSON`` — пути к
  файлам конкретного юзера.

При запуске из CLI без панели ни один из ``PARSER_EXPORT_*`` env-флагов не
задан, и :func:`is_panel_managed` возвращает False — старое поведение
сохраняется без изменений.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

logger = logging.getLogger(__name__)


def is_panel_managed() -> bool:
    """True if the panel set explicit gating flags for this run.

    When the panel launches the parser it always sets both
    ``PARSER_EXPORT_TO_DOCS`` and ``PARSER_EXPORT_TO_NOTEBOOKLM`` (to ``"1"``
    or ``"0"``). When run from the CLI, neither is set, and we keep the
    pre-PR-#10 behaviour where the parser exports to Docs unconditionally.
    """
    return (
        "PARSER_EXPORT_TO_DOCS" in os.environ
        or "PARSER_EXPORT_TO_NOTEBOOKLM" in os.environ
    )


def docs_enabled() -> bool:
    """Whether to run the Google Docs export step in the current run."""
    if not is_panel_managed():
        return True  # CLI default
    return os.environ.get("PARSER_EXPORT_TO_DOCS", "0") == "1"


def notebooklm_enabled() -> bool:
    if not is_panel_managed():
        return False  # CLI default — no NotebookLM step unless panel asked for it
    return os.environ.get("PARSER_EXPORT_TO_NOTEBOOKLM", "0") == "1"


def clear_db_after_export() -> bool:
    return os.environ.get("PARSER_CLEAR_DB_AFTER_EXPORT", "0") == "1"


async def export_to_notebooklm_via_file(
    messages: Iterable[dict[str, Any]],
    *,
    notebook_title: str | None = None,
) -> bool:
    """Export ``messages`` to a freshly-created NotebookLM notebook.

    Writes the messages to a CSV under ``exports/`` (so the file survives
    the panel's job cleanup and can be re-used as a Drive source later) and
    feeds it into NotebookLM as a new source. Uses ``NotebookLMClient.from_storage``
    which respects the ``NOTEBOOKLM_AUTH_JSON`` env var the panel injects.
    """
    messages_list = list(messages)
    if not messages_list:
        logger.info("NotebookLM: нет новых сообщений — пропускаем")
        return True

    # The notebooklm-py extra is optional — if the user only wants Docs export
    # we still want the panel to work without forcing the install.
    try:
        from notebooklm import NotebookLMClient  # type: ignore[import-not-found]
    except ImportError as exc:
        logger.error(
            "NotebookLM экспорт запрошен, но пакет notebooklm-py не установлен: %s",
            exc,
        )
        return False

    csv_path = _write_messages_csv(messages_list)
    title = notebook_title or f"Telegram parse {datetime.now():%Y-%m-%d %H:%M}"

    try:
        async with await NotebookLMClient.from_storage() as client:
            notebook = await client.notebooks.create(title)
            logger.info("NotebookLM: создан notebook %s (%s)", notebook.id, title)
            await client.sources.add_file(notebook.id, str(csv_path), wait=True)
            logger.info("NotebookLM: источник %s добавлен в notebook %s", csv_path.name, notebook.id)
        return True
    except Exception as exc:  # noqa: BLE001 — we want to log and report failure
        logger.error("NotebookLM экспорт не удался: %s", exc, exc_info=True)
        return False


def _write_messages_csv(messages: list[dict[str, Any]]) -> Path:
    """Serialise ``messages`` to ``exports/parse_<ts>.csv`` and return the path."""
    import csv

    exports_dir = Path("exports")
    exports_dir.mkdir(parents=True, exist_ok=True)
    csv_path = exports_dir / f"parse_{datetime.now():%Y%m%d_%H%M%S}.csv"

    fieldnames = [
        "date",
        "channel",
        "source_type",
        "topic_id",
        "topic_title",
        "title",
        "link",
        "text",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for msg in messages:
            writer.writerow(msg)
    logger.info("NotebookLM: подготовлен CSV %s (%s сообщений)", csv_path, len(messages))
    return csv_path


async def run_export_pipeline(messages: Iterable[dict[str, Any]]) -> bool:
    """Run Docs / NotebookLM exports + DB cleanup driven by env flags.

    Returns the value the parser should use as its overall success
    flag (which `main.py` translates to the process exit code).

    Two distinct concerns are tracked:

    - ``success`` — the public boolean. CLI runs preserve historical
      "log Docs failure but exit 0" behaviour; panel-managed runs
      surface failures via ``success=False`` so the jobs UI marks
      them red.
    - ``export_ok`` — internal data-safety guard. ANY export failure
      flips this to ``False`` and skips ``clear_messages_table`` so
      ``PARSER_CLEAR_DB_AFTER_EXPORT=1`` never silently deletes
      messages that didn't actually make it to Docs / NotebookLM.
    """
    messages_list = list(messages)
    if not messages_list:
        return True

    success = True
    export_ok = True
    panel = is_panel_managed()

    if docs_enabled():
        try:
            from src.config import GOOGLE_CONFIG, get_google_config
            from src.export.google_docs import GoogleDocsExporter

            logger.info(
                "Экспорт %s новых сообщений в Google Docs (creds=%r)",
                len(messages_list),
                GOOGLE_CONFIG.get("CREDS_PATH"),
            )
            exporter = GoogleDocsExporter()
            batch_size = get_google_config().get("BATCH_SIZE", 100)
            exporter.append_new_content(messages_list, batch_size=batch_size)
            print(f"\n✓ Экспортировано {len(messages_list)} новых сообщений в Google Docs")
        except Exception as exc:  # noqa: BLE001 — ловим любую ошибку API
            logger.error("Ошибка экспорта в Google Docs: %s", exc, exc_info=True)
            export_ok = False
            if panel:
                success = False
    elif panel:
        logger.info("Google Docs экспорт отключён в панели — пропускаем")

    if notebooklm_enabled():
        logger.info("Экспорт %s сообщений в NotebookLM…", len(messages_list))
        nlm_ok = await export_to_notebooklm_via_file(messages_list)
        if nlm_ok:
            print(f"\n✓ Загружено {len(messages_list)} сообщений в NotebookLM")
        else:
            export_ok = False
            success = False

    if export_ok and clear_db_after_export():
        logger.info("Очистка messages в parser.db после успешного экспорта…")
        try:
            removed = clear_messages_table()
            print(f"\n✓ Удалено {removed} строк из parser.db (entity-cache сохранён)")
        except Exception as exc:  # noqa: BLE001
            logger.error("Ошибка очистки messages: %s", exc, exc_info=True)
            success = False
    elif not export_ok and clear_db_after_export():
        logger.warning(
            "Пропускаем очистку messages: один из экспортов завершился с ошибкой"
        )

    return success


def clear_messages_table() -> int:
    """Delete every row from the parser's ``messages`` table.

    Cache files (entity / processed-links) stay untouched — they live in
    ``cache.json``, not in ``parser.db``.

    Returns the number of rows deleted (best-effort).
    """
    import sqlite3

    from src.config import DATABASE_CONFIG

    db_path = Path(DATABASE_CONFIG["DB_PATH"])
    if not db_path.exists():
        logger.info("Cleanup: parser.db (%s) не существует — пропускаем", db_path)
        return 0

    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM messages")
        before = int(cur.fetchone()[0])
        cur.execute("DELETE FROM messages")
        conn.commit()
        # VACUUM reclaims disk space — the user explicitly asked us to free
        # space after exports. Run outside the transaction.
    with sqlite3.connect(db_path) as conn:
        conn.execute("VACUUM")

    logger.info("Cleanup: удалено %s строк из messages, БД сжата", before)
    return before
