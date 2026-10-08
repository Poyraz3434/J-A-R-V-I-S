import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from services import user_data


class LongMemoryControlsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.original_profile_file = user_data.PROFILE_FILE
        self.profile_file = Path(self.temporary.name) / "profile.json"
        user_data.PROFILE_FILE = str(self.profile_file)

    def tearDown(self):
        user_data.PROFILE_FILE = self.original_profile_file
        self.temporary.cleanup()

    def test_snapshot_is_independent_and_note_can_be_deleted(self):
        memory = user_data.LongMemory()
        memory.save_note("preference", "Turkish")
        snapshot = memory.snapshot()
        snapshot["custom_notes"]["preference"] = "changed"

        self.assertEqual(memory.get_note("preference"), "Turkish")
        self.assertTrue(memory.delete_note("preference"))
        self.assertFalse(memory.delete_note("preference"))
        persisted = json.loads(self.profile_file.read_text(encoding="utf-8"))
        self.assertNotIn("preference", persisted["custom_notes"])

    def test_profile_save_errors_are_not_reported_as_success(self):
        memory = user_data.LongMemory()
        with mock.patch.object(
            user_data, "safe_write_json", side_effect=OSError("disk full")
        ):
            with self.assertRaisesRegex(OSError, "disk full"):
                memory.set("name", "New name")
        self.assertEqual(memory.get("name"), "Efendim")


if __name__ == "__main__":
    unittest.main()
