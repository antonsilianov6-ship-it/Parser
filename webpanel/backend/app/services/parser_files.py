"""File-IO service for parser-side config files (``config.json``,
``config/prompts.json``, ``channels.txt``).

The web panel exposes these as CRUD-able resources so the user can edit them
without SSHing into the VPS. Secret-looking JSON paths in ``config.json``
(API hashes, NotebookLM password) are masked as ``***`` on read; on write the
sentinel ``***`` means *preserve the previously-stored value*.
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any

SECRET_SENTINEL = "***"

# (section, key) tuples in the config.json schema whose values must never leave
# the server in plaintext. Keep the list minimal and explicit.
SECRET_PATHS: tuple[tuple[str, str], ...] = (
    ("TELEGRAM", "API_HASH"),
    ("NOTEBOOKLM", "password"),
)


def project_root() -> Path:
    """Path to the parser repo root (where ``config.json`` lives)."""
    return Path(__file__).resolve().parents[4]


def config_json_path() -> Path:
    return project_root() / "config.json"


def prompts_json_path() -> Path:
    return project_root() / "config" / "prompts.json"


def channels_txt_path() -> Path:
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


# ----- config.json --------------------------------------------------------


def read_config() -> dict[str, Any]:
    """Read ``config.json`` (or return defaults) and mask secret fields."""
    raw = _read_config_raw()
    return mask_secrets(raw)


def _read_config_raw() -> dict[str, Any]:
    path = config_json_path()
    if not path.exists():
        return _default_config()
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError("config.json must contain a JSON object at the top level")
    return data


def write_config(payload: dict[str, Any]) -> dict[str, Any]:
    """Persist a new ``config.json`` after merging masked secrets back in."""
    if not isinstance(payload, dict):
        raise ValueError("config payload must be a JSON object")
    existing = _read_config_raw()
    merged = merge_secrets(payload, existing)
    _validate_config_shape(merged)
    _write_json_atomically(config_json_path(), merged)
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


def read_prompts() -> dict[str, Any]:
    path = prompts_json_path()
    if not path.exists():
        return {"prompts": {}, "defaults": {}}
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError("prompts.json must contain a JSON object at the top level")
    return data


def write_prompts(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("prompts payload must be a JSON object")
    if "prompts" not in payload or not isinstance(payload["prompts"], dict):
        raise ValueError("prompts.json must contain a 'prompts' object")
    _write_json_atomically(prompts_json_path(), payload)
    return payload


# ----- channels.txt -------------------------------------------------------


def read_channels() -> list[str]:
    path = channels_txt_path()
    if not path.exists():
        return []
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def write_channels(channels: list[str]) -> list[str]:
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
    path = channels_txt_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(cleaned) + ("\n" if cleaned else ""), encoding="utf-8")
    return cleaned


def add_channel(value: str) -> list[str]:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("channel must be a non-empty string")
    current = read_channels()
    candidate = value.strip()
    if candidate in current:
        return current
    current.append(candidate)
    return write_channels(current)


def remove_channel(value: str) -> list[str]:
    current = read_channels()
    target = (value or "").strip()
    return write_channels([c for c in current if c != target])


# ----- helpers ------------------------------------------------------------


def _write_json_atomically(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=4)
    os.replace(tmp, path)
