"""Alarm data model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

# Python weekday(): Monday=0 … Sunday=6
WEEKDAY_NAMES = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
WEEKDAY_ALIASES = {name: i for i, name in enumerate(WEEKDAY_NAMES)}


@dataclass
class Alarm:
    """A single alarm definition."""

    hour: int
    minute: int
    id: str = field(default_factory=lambda: uuid4().hex[:8])
    label: str = ""
    repeat: str = "once"  # once | daily | weekdays | custom (comma-separated days)
    days: list[int] = field(default_factory=list)  # used when repeat == "custom"
    enabled: bool = True

    def repeat_display(self) -> str:
        """Human-readable repeat schedule."""
        if self.repeat == "once":
            return "once"
        if self.repeat == "daily":
            return "daily"
        if self.repeat == "weekdays":
            return "weekdays"
        if self.repeat == "custom" and self.days:
            return ",".join(WEEKDAY_NAMES[d] for d in sorted(self.days))
        return self.repeat

    def time_display(self) -> str:
        """12-hour style display for tables."""
        h, m = self.hour, self.minute
        suffix = "am" if h < 12 else "pm"
        h12 = h % 12
        if h12 == 0:
            h12 = 12
        return f"{h12}:{m:02d}{suffix}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "hour": self.hour,
            "minute": self.minute,
            "label": self.label,
            "repeat": self.repeat,
            "days": self.days,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Alarm:
        return cls(
            id=str(data["id"]),
            hour=int(data["hour"]),
            minute=int(data["minute"]),
            label=str(data.get("label", "")),
            repeat=str(data.get("repeat", "once")),
            days=[int(d) for d in data.get("days", [])],
            enabled=bool(data.get("enabled", True)),
        )
