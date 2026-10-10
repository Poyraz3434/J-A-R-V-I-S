import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import services.database as database
from services.browser import _open_allowed
from services.computer_control import (
    edit_text_file,
    open_allowed_app,
    preview_text_edit,
    undo_last_text_edit,
)
from services.database import (
    db_get_messages,
    db_get_reminders,
    db_init,
    db_new_session,
    db_save_msg,
)
from services.verification import CommandVerifier
from services.web_automation import _validate_url


class SecurityRegressionTests(unittest.TestCase):
    def test_confirmation_enters_safe_mode_after_failures(self):
        verifier = CommandVerifier()
        for _ in range(3):
            verifier.confirmation_failed()
        self.assertTrue(verifier.safe_mode)
        self.assertFalse(verifier.inspect("dosya sil").allowed)

    def test_application_allowlist_rejects_path_commands(self):
        self.assertIn("allowlist", open_allowed_app("powershell").lower())

    def test_browser_rejects_unapproved_host_and_port(self):
        self.assertIn("güvenlik", _open_allowed("https://evil.example").lower())
        self.assertIsNotNone(_validate_url("https://example.com:444"))
        self.assertIn("allowlist", _validate_url("https://example.com", require_allowlist=True).lower())

    def test_database_round_trip(self):
        original_path = database.DB_PATH
        with tempfile.TemporaryDirectory() as directory:
            database.DB_PATH = str(Path(directory) / "memory.db")
            try:
                db_init()
                session_id = db_new_session("test")
                db_save_msg(session_id, "user", "hello")
                self.assertEqual(db_get_messages(session_id)[0]["content"], "hello")
                database.db_add_reminder("test", "2026-09-20")
                self.assertEqual(len(db_get_reminders()), 1)
            finally:
                database.DB_PATH = original_path

    def test_file_edit_preview_and_undo(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "notes.txt"
            target.write_text("before value", encoding="utf-8")
            with patch("services.computer_control.Path.home", return_value=Path(directory)):
                preview = preview_text_edit(str(target), "before", "after")
                self.assertIn("after", preview)
                self.assertEqual(target.read_text(encoding="utf-8"), "before value")

                changed = edit_text_file(str(target), "before", "after")
                self.assertIn("Yedek oluşturuldu", changed)
                self.assertEqual(target.read_text(encoding="utf-8"), "after value")

                undone = undo_last_text_edit(str(target))
                self.assertIn("geri yüklendi", undone)
                self.assertEqual(target.read_text(encoding="utf-8"), "before value")
                undo_last_text_edit(str(target))
                self.assertEqual(target.read_text(encoding="utf-8"), "before value")


if __name__ == "__main__":
    unittest.main()
