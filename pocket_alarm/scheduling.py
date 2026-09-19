"""Compute next fire times for alarms."""

from __future__ import annotations

from datetime import datetime, timedelta

from pocket_alarm.models import Alarm

WEEKDAYS = frozenset(range(0, 5))


def _allowed_weekdays(alarm: Alarm) -> frozenset[int] | None:
    """Return allowed weekday indices, or None if any day is allowed."""
    if alarm.repeat == "once":
        return None
    if alarm.repeat == "daily":
        return None
    if alarm.repeat == "weekdays":
        return WEEKDAYS
    if alarm.repeat == "custom":
        return frozenset(alarm.days)
    return None


def _slot_on_day(alarm: Alarm, day: datetime) -> datetime:
    return datetime(day.year, day.month, day.day, alarm.hour, alarm.minute)


def next_fire_at(alarm: Alarm, after: datetime | None = None) -> datetime | None:
    """
    Next local datetime when ``alarm`` should ring.

    Comparison uses **minute precision**: an alarm at 07:30 fires any time during
    the 07:30 minute (07:30:00–07:30:59). Once that minute has fully passed
    (from 07:31:00 onward), the next slot is the following calendar day (or the
    next allowed weekday).

    Pass ``after`` to search strictly after a moment (e.g. ``fire_time +
    timedelta(minutes=1)`` after a dismiss so the same minute does not re-ring).
    """
    if not alarm.enabled:
        return None

    now = after or datetime.now()
    if now.tzinfo is not None:
        now = now.replace(tzinfo=None)

    search_from = now.replace(second=0, microsecond=0)
    candidate = _slot_on_day(alarm, search_from)
    if candidate < search_from:
        candidate += timedelta(days=1)

    allowed = _allowed_weekdays(alarm)
    if allowed is None:
        return candidate

    for _ in range(8):
        if candidate.weekday() in allowed:
            return candidate
        candidate += timedelta(days=1)
        candidate = candidate.replace(hour=alarm.hour, minute=alarm.minute)

    return None


def next_fire_among(alarms: list[Alarm], after: datetime | None = None) -> tuple[datetime | None, Alarm | None]:
    """Earliest next fire among enabled alarms."""
    now = after or datetime.now()
    best_time: datetime | None = None
    best_alarm: Alarm | None = None
    for alarm in alarms:
        fire = next_fire_at(alarm, now)
        if fire is None:
            continue
        if best_time is None or fire < best_time:
            best_time = fire
            best_alarm = alarm
    return best_time, best_alarm


def format_datetime(dt: datetime) -> str:
    """Compact local display."""
    return dt.strftime("%a %Y-%m-%d %H:%M")
