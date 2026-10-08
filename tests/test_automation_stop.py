import unittest
from unittest import mock

from automation_engine import AutomationEngine


class _ActiveThread:
    def is_alive(self):
        return True


class AutomationStopTests(unittest.TestCase):
    def setUp(self):
        self.watcher_patch = mock.patch("automation_engine.ScreenWatcher")
        self.watcher_patch.start()
        self.addCleanup(self.watcher_patch.stop)
        self.engine = AutomationEngine()
        self.driver = mock.Mock()
        self.engine._driver = self.driver

    def test_stop_does_not_close_driver_while_automation_thread_is_active(self):
        self.engine._thread = _ActiveThread()

        self.engine.stop()

        self.driver.quit.assert_not_called()

    def test_stop_closes_driver_when_no_automation_thread_is_active(self):
        self.engine._thread = None

        self.engine.stop()

        self.driver.quit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
