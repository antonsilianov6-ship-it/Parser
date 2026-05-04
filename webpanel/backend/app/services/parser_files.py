"""File-IO service for parser-side config files (``config.json``,
``prompts.json``, ``channels.txt``).

Files are **per-user**: each panel user has an isolated directory under
``settings.resolved_user_data_dir / <user_id> /`` and the web panel only ever
reads or writes within that directory for the calling user. The parser
subprocess receives ``PARSER_CONFIG_PATH`` / ``PARSER_PROMPTS_PATH`` /
``PARSER_CHANNELS_PATH`` / ``PARSER_DB_PATH`` env vars resolved against the
job owner's directory, so two users running parses in parallel never share
state.

Secret-looking JSON paths in ``config.json`` (API hashes, NotebookLM password)
are masked as ``***`` on read; on write the sentinel ``***`` means *preserve
the previously-stored value*.
"""

from __future__ import annotations

import copy
import json
import os
import shutil
from pathlib import Path
from typing import Any

from app.config import get_settings

SECRET_SENTINEL = "***"

# (section, key) tuples in the config.json schema whose values must never leave
# the server in plaintext. Keep the list minimal and explicit.
SECRET_PATHS: tuple[tuple[str, str], ...] = (
    ("TELEGRAM", "API_HASH"),
    ("NOTEBOOKLM", "password"),
)


def project_root() -> Path:
    """Path to the parser repo root (where the legacy config.json lives)."""
    return Path(__file__).resolve().parents[4]


def user_dir(user_id: int) -> Path:
    """Per-user directory holding {config.json, prompts.json, channels.txt, parser.db}.

    Created on first access. Lives next to the panel's own SQLite by default
    (``<panel_db>.parent/users/<uid>/``) but can be overridden via the
    ``PANEL_USER_DATA_DIR`` env var.
    """
    base = get_settings().resolved_user_data_dir
    path = base / str(user_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_json_path(user_id: int) -> Path:
    return user_dir(user_id) / "config.json"


def prompts_json_path(user_id: int) -> Path:
    return user_dir(user_id) / "prompts.json"


def channels_txt_path(user_id: int) -> Path:
    return user_dir(user_id) / "channels.txt"


def parser_db_path(user_id: int) -> Path:
    return user_dir(user_id) / "parser.db"


def google_credentials_path(user_id: int) -> Path:
    """Per-user Google service-account JSON for Drive / Docs API."""
    return user_dir(user_id) / "google-credentials.json"


def notebooklm_storage_path(user_id: int) -> Path:
    """Per-user NotebookLM ``storage_state.json`` (cookies + localStorage).

    Format matches what ``notebooklm-py`` produces via ``notebooklm login``.
    """
    return user_dir(user_id) / "notebooklm_storage.json"


def parser_cache_path(user_id: int) -> Path:
    """Per-user entity / processed-link cache (corresponds to ``cache/cache.json``)."""
    cache_dir = user_dir(user_id) / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / "cache.json"


def has_google_credentials(user_id: int) -> bool:
    return google_credentials_path(user_id).exists()


def has_notebooklm_storage(user_id: int) -> bool:
    return notebooklm_storage_path(user_id).exists()


def write_google_credentials(user_id: int, payload: dict[str, Any] | str) -> None:
    """Write a Google service-account JSON to the user's directory.

    Accepts either a parsed dict or the raw JSON string straight from the
    uploaded file. Validates that the file looks like a service account
    (``type == "service_account"``) before writing so we fail early with a
    helpful error instead of producing 500s downstream.
    """
    if isinstance(payload, str):
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValueError("Файл не является валидным JSON") from exc
    else:
        data = payload

    if not isinstance(data, dict) or data.get("type") != "service_account":
        raise ValueError(
            "Это не похоже на Google Service Account: ожидался JSON с "
            "полем 'type': 'service_account'"
        )
    for required in ("client_email", "private_key", "project_id"):
        if not data.get(required):
            raise ValueError(f"В JSON отсутствует обязательное поле '{required}'")

    _write_json_atomically(google_credentials_path(user_id), data)


def delete_google_credentials(user_id: int) -> None:
    path = google_credentials_path(user_id)
    if path.exists():
        path.unlink()


def google_credentials_email(user_id: int) -> str | None:
    """Return the service-account email so the UI can display it.

    The email is the only piece of the JSON that's safe to expose — it's also
    the one piece the user needs to know in order to share their Drive doc /
    folder with the service account.
    """
    path = google_credentials_path(user_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    email = data.get("client_email")
    return email if isinstance(email, str) else None


def write_notebooklm_storage(user_id: int, payload: dict[str, Any] | str) -> None:
    """Persist a Playwright ``storage_state.json`` for NotebookLM.

    notebooklm-py expects a Playwright storage-state object — a dict containing
    at minimum ``cookies`` (list) and ``origins`` (list). We sanity-check the
    shape but don't touch the contents.
    """
    if isinstance(payload, str):
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValueError("Файл не является валидным JSON") from exc
    else:
        data = payload

    if not isinstance(data, dict):
        raise ValueError("storage_state.json должен быть JSON-объектом")
    if "cookies" not in data and "origins" not in data:
        raise ValueError(
            "Это не похоже на storage_state.json от notebooklm-py: "
            "ожидались ключи 'cookies' и/или 'origins'"
        )

    _write_json_atomically(notebooklm_storage_path(user_id), data)


def delete_notebooklm_storage(user_id: int) -> None:
    path = notebooklm_storage_path(user_id)
    if path.exists():
        path.unlink()


# Legacy paths in the repo root. Used as one-time templates when seeding a new
# user's directory; the parser itself no longer reads them when run from the
# web panel because jobs_runner overrides them via environment variables.
def _legacy_config_path() -> Path:
    return project_root() / "config.json"


def _legacy_prompts_path() -> Path:
    return project_root() / "config" / "prompts.json"


def _legacy_channels_path() -> Path:
    return project_root() / "channels.txt"


def _default_config() -> dict[str, Any]:
    """Return a baseline ``config.json`` used when the file is missing."""
    return {
        "TELEGRAM": {"API_ID": None, "API_HASH": ""},
        "GOOGLE": {"CREDS_PATH": "google-credentials.json", "DOC_ID": None},
        "PARSER": {
            "CHECK_INTERVAL": 3600,
            "DATE_RANGE_ENABLED": False,
            "DAYS_FOR_EXPORT": 3,
            "FETCH_COMMENTS": True,
            "MAX_COMMENTS_PER_POST": 50,
        },
        "DATABASE": {
            "DB_PATH": "data/parser.db",
            "BACKUP_ENABLED": True,
            "BACKUP_INTERVAL": 24,
        },
        "NOTEBOOKLM": {
            "email": "",
            "password": "",
            "prompts_config": "config/prompts.json",
            "timeout": 120,
            "max_retries": 3,
        },
        "AUTOMATION": {
            "enabled": False,
            "target_chat_id": "",
            "schedule_enabled": True,
            "schedule_time": "09:00",
            "export_format": "csv",
            "export_dir": "exports",
        },
    }


def seed_user_dir(user_id: int, *, copy_legacy: bool = False) -> Path:
    """Ensure the per-user directory exists and contains baseline files.

    Missing files are written; existing files are never touched. When
    ``copy_legacy`` is true and a legacy file in the repo root is present,
    it is copied as-is into the user's directory (used during the one-time
    migration from the old global setup).
    """
    udir = user_dir(user_id)

    cfg_path = config_json_path(user_id)
    if not cfg_path.exists():
        legacy = _legacy_config_path()
        if copy_legacy and legacy.exists():
            shutil.copy2(legacy, cfg_path)
        else:
            _write_json_atomically(cfg_path, _default_config())

    prompts_path = prompts_json_path(user_id)
    if not prompts_path.exists():
        legacy_prompts = _legacy_prompts_path()
        if copy_legacy and legacy_prompts.exists():
            shutil.copy2(legacy_prompts, prompts_path)
        else:
            _write_json_atomically(prompts_path, {"prompts": {}, "defaults": {}})

    ch_path = channels_txt_path(user_id)
    if not ch_path.exists():
        legacy_channels = _legacy_channels_path()
        if copy_legacy and legacy_channels.exists():
            shutil.copy2(legacy_channels, ch_path)
        else:
            ch_path.write_text("", encoding="utf-8")

    return udir


# ----- config.json --------------------------------------------------------


def read_config(user_id: int) -> dict[str, Any]:
    """Read the user's ``config.json`` (or return defaults) and mask secrets."""
    raw = _read_config_raw(user_id)
    return mask_secrets(raw)


def _read_config_raw(user_id: int) -> dict[str, Any]:
    path = config_json_path(user_id)
    if not path.exists():
        return _default_config()
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError("config.json must contain a JSON object at the top level")
    return data


def write_config(user_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    """Persist a new ``config.json`` after merging masked secrets back in."""
    if not isinstance(payload, dict):
        raise ValueError("config payload must be a JSON object")
    existing = _read_config_raw(user_id)
    merged = merge_secrets(payload, existing)
    _validate_config_shape(merged)
    _write_json_atomically(config_json_path(user_id), merged)
    return mask_secrets(merged)


def mask_secrets(cfg: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(cfg)
    for section, key in SECRET_PATHS:
        section_obj = out.get(section)
        if not isinstance(section_obj, dict):
            continue
        value = section_obj.get(key)
        if isinstance(value, str) and value:
            section_obj[key] = SECRET_SENTINEL
    return out


def merge_secrets(incoming: dict[str, Any], existing: dict[str, Any]) -> dict[str, Any]:
    """Replace ``SECRET_SENTINEL`` placeholders with values from ``existing``."""
    out = copy.deepcopy(incoming)
    for section, key in SECRET_PATHS:
        new_section = out.get(section)
        if not isinstance(new_section, dict):
            continue
        if new_section.get(key) == SECRET_SENTINEL:
            old_section = existing.get(section)
            if isinstance(old_section, dict):
                new_section[key] = old_section.get(key, "")
            else:
                new_section[key] = ""
    return out


def _validate_config_shape(cfg: dict[str, Any]) -> None:
    if not isinstance(cfg, dict):
        raise ValueError("config must be a JSON object")
    for section_name, section_value in cfg.items():
        if not isinstance(section_value, dict):
            raise ValueError(
                f"config section '{section_name}' must be a JSON object, "
                f"got {type(section_value).__name__}"
            )


# ----- prompts.json -------------------------------------------------------


def read_prompts(user_id: int) -> dict[str, Any]:
    path = prompts_json_path(user_id)
    if not path.exists():
        return {"prompts": {}, "defaults": {}}
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError("prompts.json must contain a JSON object at the top level")
    return data


def write_prompts(user_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("prompts payload must be a JSON object")
    if "prompts" not in payload or not isinstance(payload["prompts"], dict):
        raise ValueError("prompts.json must contain a 'prompts' object")
    _write_json_atomically(prompts_json_path(user_id), payload)
    return payload


# ----- channels.txt -------------------------------------------------------


def read_channels(user_id: int) -> list[str]:
    path = channels_txt_path(user_id)
    if not path.exists():
        return []
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def write_channels(user_id: int, channels: list[str]) -> list[str]:
    """Replace the whole channel list (deduplicated, order preserved)."""
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in channels:
        if not isinstance(raw, str):
            raise ValueError("each channel must be a string")
        value = raw.strip()
        if not value:
            continue
        if value in seen:
            continue
        seen.add(value)
        cleaned.append(value)
    path = channels_txt_path(user_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(cleaned) + ("\n" if cleaned else ""), encoding="utf-8")
    return cleaned


def add_channel(user_id: int, value: str) -> list[str]:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("channel must be a non-empty string")
    current = read_channels(user_id)
    candidate = value.strip()
    if candidate in current:
        return current
    current.append(candidate)
    return write_channels(user_id, current)


def remove_channel(user_id: int, value: str) -> list[str]:
    current = read_channels(user_id)
    target = (value or "").strip()
    return write_channels(user_id, [c for c in current if c != target])


# ----- helpers ------------------------------------------------------------


def _write_json_atomically(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=4)
    os.replace(tmp, path)
