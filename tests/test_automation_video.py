import unittest
from unittest import mock

from automation_engine import AutomationEngine


class _PlayingDriver:
    current_url = "https://www.youtube.com/watch?v=example"

    def __init__(self, playback_states):
        self.playback_states = iter(playback_states)
        self.find_elements = mock.Mock(return_value=[])

    def execute_script(self, script):
        return next(self.playback_states)


class YouTubePlaybackTests(unittest.TestCase):
    def setUp(self):
        self.watcher_patch = mock.patch("automation_engine.ScreenWatcher")
        self.watcher_patch.start()
        self.addCleanup(self.watcher_patch.stop)
        self.engine = AutomationEngine()

    def test_playback_is_confirmed_only_from_active_video_state(self):
        driver = _PlayingDriver([True])

        self.assertTrue(self.engine._wait_for_video_playback(driver, timeout=0))
        driver.find_elements.assert_not_called()

    def test_video_title_alone_cannot_confirm_playback(self):
        driver = _PlayingDriver([False])

        self.assertFalse(self.engine._wait_for_video_playback(driver, timeout=0))
        driver.find_elements.assert_called_once()

    def test_paused_video_gets_one_play_click_attempt(self):
        button = mock.Mock()
        button.is_displayed.return_value = True
        button.is_enabled.return_value = True
        driver = _PlayingDriver([False, True])
        driver.find_elements.return_value = [button]

        with mock.patch("automation_engine.time.sleep"):
            playing = self.engine._wait_for_video_playback(driver, timeout=1)

        self.assertTrue(playing)
        button.click.assert_called_once()


if __name__ == "__main__":
    unittest.main()
