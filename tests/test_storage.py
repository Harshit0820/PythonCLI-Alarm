"""Tests for JSON storage."""

import json
import tempfile
import unittest
from pathlib import Path

from pocket_alarm.models import Alarm
from pocket_alarm.storage import find_alarm, load_alarms, save_alarms


class TestStorageRoundTrip(unittest.TestCase):
    def test_save_and_load(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "alarms.json"
            alarms = [
                Alarm(hour=7, minute=30, label="Wake", repeat="weekdays"),
                Alarm(hour=22, minute=0, repeat="custom", days=[4, 5], enabled=False),
            ]
            save_alarms(path, alarms)
            loaded = load_alarms(path)
            self.assertEqual(len(loaded), 2)
            self.assertEqual(loaded[0].hour, 7)
            self.assertEqual(loaded[0].label, "Wake")
            self.assertEqual(loaded[1].days, [4, 5])
            self.assertFalse(loaded[1].enabled)

            raw = json.loads(path.read_text())
            self.assertIsInstance(raw, list)

    def test_find_alarm_prefix(self) -> None:
        a = Alarm(id="abcdef12", hour=1, minute=0)
        b = Alarm(id="fedcba98", hour=2, minute=0)
        self.assertIs(find_alarm([a, b], "abc"), a)
        self.assertIsNone(find_alarm([a, b], "ab"))


if __name__ == "__main__":
    unittest.main()
