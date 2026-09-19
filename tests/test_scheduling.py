"""Tests for next-fire scheduling."""

import unittest
from datetime import datetime

from pocket_alarm.models import Alarm
from pocket_alarm.scheduling import next_fire_among, next_fire_at


class TestNextFireAt(unittest.TestCase):
    def test_today_later(self) -> None:
        alarm = Alarm(hour=15, minute=0, repeat="daily")
        now = datetime(2026, 3, 10, 10, 0)
        fire = next_fire_at(alarm, now)
        assert fire is not None
        self.assertEqual(fire, datetime(2026, 3, 10, 15, 0))

    def test_rolls_to_next_day(self) -> None:
        alarm = Alarm(hour=7, minute=30, repeat="daily")
        now = datetime(2026, 3, 10, 8, 0)
        fire = next_fire_at(alarm, now)
        assert fire is not None
        self.assertEqual(fire, datetime(2026, 3, 11, 7, 30))

    def test_once_tomorrow(self) -> None:
        alarm = Alarm(hour=7, minute=0, repeat="once")
        now = datetime(2026, 3, 10, 12, 0)
        fire = next_fire_at(alarm, now)
        assert fire is not None
        self.assertEqual(fire, datetime(2026, 3, 11, 7, 0))

    def test_same_minute_fires_today_not_tomorrow(self) -> None:
        """Regression: candidate <= now skipped the entire current minute."""
        alarm = Alarm(hour=7, minute=30, repeat="daily")
        fire = next_fire_at(alarm, datetime(2026, 3, 10, 7, 30, 0))
        assert fire is not None
        self.assertEqual(fire, datetime(2026, 3, 10, 7, 30))
        fire = next_fire_at(alarm, datetime(2026, 3, 10, 7, 30, 45))
        assert fire is not None
        self.assertEqual(fire, datetime(2026, 3, 10, 7, 30))

    def test_after_dismiss_searches_from_next_minute(self) -> None:
        alarm = Alarm(hour=7, minute=30, repeat="daily")
        after = datetime(2026, 3, 10, 7, 31, 0)
        fire = next_fire_at(alarm, after)
        assert fire is not None
        self.assertEqual(fire, datetime(2026, 3, 11, 7, 30))

    def test_weekdays_skips_weekend(self) -> None:
        alarm = Alarm(hour=9, minute=0, repeat="weekdays")
        # 2026-03-14 is Saturday
        now = datetime(2026, 3, 14, 10, 0)
        fire = next_fire_at(alarm, now)
        assert fire is not None
        self.assertEqual(fire.weekday(), 0)  # Monday
        self.assertEqual(fire, datetime(2026, 3, 16, 9, 0))

    def test_custom_days(self) -> None:
        alarm = Alarm(hour=8, minute=0, repeat="custom", days=[0, 2])  # Mon, Wed
        now = datetime(2026, 3, 10, 9, 0)  # Tuesday
        fire = next_fire_at(alarm, now)
        assert fire is not None
        self.assertEqual(fire, datetime(2026, 3, 11, 8, 0))  # Wednesday

    def test_disabled(self) -> None:
        alarm = Alarm(hour=8, minute=0, enabled=False)
        self.assertIsNone(next_fire_at(alarm, datetime(2026, 3, 10, 7, 0)))


class TestNextFireAmong(unittest.TestCase):
    def test_picks_earliest(self) -> None:
        a = Alarm(id="a", hour=10, minute=0, repeat="daily")
        b = Alarm(id="b", hour=9, minute=0, repeat="daily")
        now = datetime(2026, 3, 10, 8, 0)
        t, winner = next_fire_among([a, b], now)
        assert t is not None and winner is not None
        self.assertEqual(winner.id, "b")
        self.assertEqual(t, datetime(2026, 3, 10, 9, 0))


if __name__ == "__main__":
    unittest.main()
