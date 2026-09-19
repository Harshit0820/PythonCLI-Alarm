"""Parse user-facing time and repeat strings."""

from __future__ import annotations

import re

from pocket_alarm.models import WEEKDAY_ALIASES, WEEKDAY_NAMES

_TIME_24 = re.compile(r"^(\d{1,2}):(\d{2})$")
_TIME_12 = re.compile(
    r"^(\d{1,2}):(\d{2})\s*(am|pm|a\.m\.|p\.m\.)$",
    re.IGNORECASE,
)


class ParseError(ValueError):
    """Invalid user input."""


def parse_time(text: str) -> tuple[int, int]:
    """Parse 24h ``07:30`` or 12h ``7:30am`` into (hour, minute)."""
    raw = text.strip()
    if not raw:
        raise ParseError("Time is required.")

    m = _TIME_24.match(raw)
    if m:
        hour, minute = int(m.group(1)), int(m.group(2))
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ParseError(f"Invalid 24-hour time: {text!r}")
        return hour, minute

    m = _TIME_12.match(raw.replace(" ", ""))
    if not m:
        # retry with space before am/pm: "7:30 am"
        m = _TIME_12.match(raw)
    if m:
        hour, minute = int(m.group(1)), int(m.group(2))
        if not (1 <= hour <= 12 and 0 <= minute <= 59):
            raise ParseError(f"Invalid 12-hour time: {text!r}")
        meridiem = m.group(3).lower().replace(".", "")
        if meridiem == "am":
            if hour == 12:
                hour = 0
        else:
            if hour != 12:
                hour += 12
        return hour, minute

    raise ParseError(
        f"Could not parse time {text!r}. Use 24h (07:30) or 12h (7:30am)."
    )


def parse_repeat(text: str | None) -> tuple[str, list[int]]:
    """
    Parse repeat schedule.

    Returns (repeat_kind, days) where repeat_kind is once|daily|weekdays|custom.
    """
    if text is None or not text.strip():
        return "once", []

    raw = text.strip().lower().replace(" ", "")
    if raw in ("once", "one-shot", "onetime"):
        return "once", []
    if raw in ("daily", "everyday"):
        return "daily", []
    if raw in ("weekdays", "weekday", "mon-fri", "monfri"):
        return "weekdays", [0, 1, 2, 3, 4]

    parts = [p for p in re.split(r"[,/]", raw) if p]
    days: list[int] = []
    for part in parts:
        if part not in WEEKDAY_ALIASES:
            raise ParseError(
                f"Unknown day {part!r}. Use {', '.join(WEEKDAY_NAMES)}."
            )
        days.append(WEEKDAY_ALIASES[part])
    if not days:
        raise ParseError("Repeat schedule must list at least one day.")
    return "custom", sorted(set(days))


def parse_duration(text: str) -> int:
    """Parse duration like ``5m``, ``90s``, ``1h30m`` into total seconds."""
    raw = text.strip().lower()
    if not raw:
        raise ParseError("Duration is required.")

    total = 0
    pos = 0
    duration_re = re.compile(r"(\d+)\s*(h|hr|hrs|hour|hours|m|min|mins|minute|minutes|s|sec|secs|second|seconds)")
    for m in duration_re.finditer(raw):
        if m.start() != pos and pos == 0 and m.start() > 0:
            break
        pos = m.end()
        value = int(m.group(1))
        unit = m.group(2)[0]
        if unit == "h":
            total += value * 3600
        elif unit == "m":
            total += value * 60
        else:
            total += value

    if pos != len(raw) or total <= 0:
        raise ParseError(
            f"Could not parse duration {text!r}. Examples: 30s, 5m, 1h30m."
        )
    return total
