import datetime as dt
import tempfile
import unittest
from pathlib import Path

from services import routines


class RoutineStoreTests(unittest.TestCase):
    def setUp(self):
        self._old_path = routines.DB_PATH
        self._tmp = tempfile.TemporaryDirectory()
        routines.DB_PATH = str(Path(self._tmp.name) / "routines.db")

    def tearDown(self):
        routines.DB_PATH = self._old_path
        self._tmp.cleanup()

    def test_daily_briefing_is_persistent_and_listed(self):
        routine_id = routines.add_daily_briefing("08:30")
        found = routines.list_routines()
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].id, routine_id)
        self.assertEqual(found[0].run_at, "08:30")
        self.assertEqual(found[0].action, "daily_briefing")

    def test_due_routine_is_claimed_only_once_per_day(self):
        routines.add_daily_briefing("08:30")
        now = dt.datetime(2026, 10, 3, 9, 0)
        self.assertEqual(len(routines.claim_due_routines(now)), 1)
        self.assertEqual(routines.claim_due_routines(now), [])
        next_day = now + dt.timedelta(days=1)
        self.assertEqual(len(routines.claim_due_routines(next_day)), 1)

    def test_invalid_time_and_removal(self):
        with self.assertRaises(ValueError):
            routines.add_daily_briefing("25:99")
        routine_id = routines.add_daily_briefing("8:30")
        self.assertTrue(routines.remove_routine(routine_id))
        self.assertFalse(routines.remove_routine(routine_id))


if __name__ == "__main__":
    unittest.main()
