"""Paths and environment configuration."""

from __future__ import annotations

import os
from pathlib import Path

ENV_DATA_FILE = "POCKET_ALARM_DATA_FILE"
DEFAULT_DATA_DIR = Path.home() / ".config" / "pocket-alarm"
DEFAULT_DATA_FILE = DEFAULT_DATA_DIR / "alarms.json"


def resolve_data_file(override: str | None = None) -> Path:
    """Return the alarms JSON path (override, env, or default)."""
    if override:
        return Path(override).expanduser()
    env = os.environ.get(ENV_DATA_FILE)
    if env:
        return Path(env).expanduser()
    return DEFAULT_DATA_FILE
