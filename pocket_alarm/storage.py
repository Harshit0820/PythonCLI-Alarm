"""JSON file persistence."""

from __future__ import annotations

import json
from pathlib import Path

from pocket_alarm.models import Alarm


class StorageError(OSError):
    """Failed to read or write alarm data."""


def load_alarms(path: Path) -> list[Alarm]:
    """Load alarms from JSON; return empty list if file is missing."""
    if not path.exists():
        return []
    try:
        raw = path.read_text(encoding="utf-8")
        if not raw.strip():
            return []
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise StorageError(f"Invalid JSON in {path}: {exc}") from exc
    except OSError as exc:
        raise StorageError(f"Cannot read {path}: {exc}") from exc

    if not isinstance(data, list):
        raise StorageError(f"Expected a JSON array in {path}")

    return [Alarm.from_dict(item) for item in data]


def save_alarms(path: Path, alarms: list[Alarm]) -> None:
    """Write alarms atomically (best effort via temp file rename)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps([a.to_dict() for a in alarms], indent=2)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(payload + "\n", encoding="utf-8")
        tmp.replace(path)
    except OSError as exc:
        raise StorageError(f"Cannot write {path}: {exc}") from exc


def find_alarm(alarms: list[Alarm], alarm_id: str) -> Alarm | None:
    """Find by exact or prefix id match."""
    if not alarm_id:
        return None
    for alarm in alarms:
        if alarm.id == alarm_id:
            return alarm
    if len(alarm_id) < 3:
        return None
    matches = [a for a in alarms if a.id.startswith(alarm_id)]
    if len(matches) == 1:
        return matches[0]
    return None
