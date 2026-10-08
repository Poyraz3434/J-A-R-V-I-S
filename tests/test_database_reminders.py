import tempfile
import unittest
from pathlib import Path

from services import database


class DueReminderTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = database.DB_PATH
        database.DB_PATH = str(Path(self.temp_dir.name) / "reminders.db")
        database.db_init()

    def tearDown(self):
        database.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def test_claim_returns_due_reminders_once_and_leaves_future_reminders(self):
        database.db_add_reminder("due", "2026-10-02")
        database.db_add_reminder("today", "2026-10-03")
        database.db_add_reminder("future", "2026-10-04")

        claimed = database.db_claim_due_reminders("2026-10-03")

        self.assertEqual([row[1] for row in claimed], ["due", "today"])
        self.assertEqual(database.db_claim_due_reminders("2026-10-03"), [])
        self.assertEqual(
            [row[1] for row in database.db_get_reminders()],
            ["future"],
        )


class ChatHistoryDeletionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = database.DB_PATH
        database.DB_PATH = str(Path(self.temp_dir.name) / "history.db")
        database.db_init()

    def tearDown(self):
        database.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def test_clear_session_removes_messages_without_removing_session(self):
        session_id = database.db_new_session("Saklanacak başlık")
        database.db_save_msg(session_id, "user", "Özel mesaj")

        deleted_count = database.db_clear_session(session_id)

        self.assertEqual(deleted_count, 1)
        self.assertEqual(database.db_get_messages(session_id), [])
        self.assertIn(
            session_id,
            [row[0] for row in database.db_get_sessions()],
        )

    def test_clear_all_history_keeps_only_current_empty_session(self):
        current_session = database.db_new_session("Geçerli sohbet")
        old_session = database.db_new_session("Eski sohbet")
        database.db_save_msg(current_session, "user", "Güncel mesaj")
        database.db_save_msg(old_session, "assistant", "Eski mesaj")

        deleted_sessions = database.db_clear_all_history(current_session)

        self.assertEqual(deleted_sessions, 1)
        self.assertEqual(database.db_get_messages(current_session), [])
        self.assertEqual(database.db_get_sessions()[0][0], current_session)
        self.assertEqual(database.db_get_messages(old_session), [])

    def test_clear_history_rejects_invalid_session_id(self):
        with self.assertRaises(ValueError):
            database.db_clear_session(0)
        with self.assertRaises(ValueError):
            database.db_clear_all_history(-1)


class ChatHistorySearchTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = database.DB_PATH
        database.DB_PATH = str(Path(self.temp_dir.name) / "history-search.db")
        database.db_init()

    def tearDown(self):
        database.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def test_search_is_case_insensitive_and_returns_recent_matches(self):
        session_id = database.db_new_session("Yerel arama")
        database.db_save_msg(session_id, "user", "İstanbul gezisi planı")
        database.db_save_msg(session_id, "assistant", "İSTANBUL için öneriler")
        database.db_save_msg(
            session_id, "user", "sohbet geçmişinde ara istanbul"
        )

        matches = database.db_search_messages(
            "istanbul",
            limit=5,
            exclude_content="sohbet geçmişinde ara istanbul",
        )

        self.assertEqual(len(matches), 2)
        self.assertEqual(matches[0]["role"], "assistant")
        self.assertEqual(matches[0]["title"], "Yerel arama")

    def test_search_rejects_empty_query_and_invalid_limit(self):
        with self.assertRaises(ValueError):
            database.db_search_messages(" ")
        with self.assertRaises(ValueError):
            database.db_search_messages("jarvis", limit=0)

    def test_search_ranks_messages_matching_more_query_terms_first(self):
        session_id = database.db_new_session("Sıralı eşleşmeler")
        database.db_save_msg(session_id, "user", "Rover hakkında genel bilgi")
        database.db_save_msg(
            session_id, "assistant", "Mars yüzeyindeki rover görevi"
        )

        matches = database.db_search_messages("mars rover", limit=2)

        self.assertIn("Mars yüzeyindeki", matches[0]["content"])

    def test_get_messages_limit_returns_newest_messages_in_original_order(self):
        session_id = database.db_new_session("Uzun sohbet")
        for index in range(5):
            database.db_save_msg(session_id, "user", f"mesaj {index}")

        messages = database.db_get_messages(session_id, limit=2)

        self.assertEqual(
            [message["content"] for message in messages],
            ["mesaj 3", "mesaj 4"],
        )

    def test_get_messages_rejects_invalid_limit(self):
        session_id = database.db_new_session("Sınır kontrolü")
        for limit in (0, -1, 10_001, 1.5):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                database.db_get_messages(session_id, limit=limit)


if __name__ == "__main__":
    unittest.main()
