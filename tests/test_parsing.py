"""Tests for time and repeat parsing."""

import unittest

from pocket_alarm.parsing import ParseError, parse_duration, parse_repeat, parse_time


class TestParseTime(unittest.TestCase):
    def test_24h(self) -> None:
        self.assertEqual(parse_time("07:30"), (7, 30))
        self.assertEqual(parse_time("23:59"), (23, 59))
        self.assertEqual(parse_time("0:00"), (0, 0))

    def test_12h(self) -> None:
        self.assertEqual(parse_time("7:30am"), (7, 30))
        self.assertEqual(parse_time("7:30 am"), (7, 30))
        self.assertEqual(parse_time("7:30PM"), (19, 30))
        self.assertEqual(parse_time("12:00am"), (0, 0))
        self.assertEqual(parse_time("12:00pm"), (12, 0))

    def test_invalid(self) -> None:
        with self.assertRaises(ParseError):
            parse_time("25:00")
        with self.assertRaises(ParseError):
            parse_time("noon")


class TestParseRepeat(unittest.TestCase):
    def test_once_daily_weekdays(self) -> None:
        self.assertEqual(parse_repeat(None), ("once", []))
        self.assertEqual(parse_repeat("daily"), ("daily", []))
        self.assertEqual(parse_repeat("weekdays"), ("weekdays", [0, 1, 2, 3, 4]))

    def test_custom_days(self) -> None:
        kind, days = parse_repeat("mon,wed,fri")
        self.assertEqual(kind, "custom")
        self.assertEqual(days, [0, 2, 4])


class TestParseDuration(unittest.TestCase):
    def test_seconds_minutes(self) -> None:
        self.assertEqual(parse_duration("30s"), 30)
        self.assertEqual(parse_duration("5m"), 300)
        self.assertEqual(parse_duration("1h30m"), 5400)


if __name__ == "__main__":
    unittest.main()
