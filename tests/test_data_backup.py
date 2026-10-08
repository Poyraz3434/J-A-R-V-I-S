import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from services import data_backup, database


class DataBackupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.originals = {
            "APP_DATA_DIR": data_backup.APP_DATA_DIR,
            "DB_PATH": data_backup.DB_PATH,
            "PDF_STORE": data_backup.PDF_STORE,
            "_JSON_FILES": data_backup._JSON_FILES,
            "database_path": database.DB_PATH,
        }
        self.data_dir = self.root / "data"
        self.pdf_dir = self.data_dir / "jarvis_pdfs"
        self.db_path = self.data_dir / "jarvis_memory.db"
        self.json_files = {
            "jarvis_settings.json": self.data_dir / "jarvis_settings.json",
            "jarvis_profile.json": self.data_dir / "jarvis_profile.json",
            "user_style.json": self.data_dir / "user_style.json",
            "jarvis_contacts.json": self.data_dir / "jarvis_contacts.json",
        }
        self.data_dir.mkdir(parents=True, exist_ok=True)
        data_backup.APP_DATA_DIR = self.data_dir
        data_backup.DB_PATH = self.db_path
        data_backup.PDF_STORE = self.pdf_dir
        data_backup._JSON_FILES = self.json_files
        database.DB_PATH = str(self.db_path)
        database.db_init()

    def tearDown(self):
        data_backup.APP_DATA_DIR = self.originals["APP_DATA_DIR"]
        data_backup.DB_PATH = self.originals["DB_PATH"]
        data_backup.PDF_STORE = self.originals["PDF_STORE"]
        data_backup._JSON_FILES = self.originals["_JSON_FILES"]
        database.DB_PATH = self.originals["database_path"]
        self.temporary.cleanup()

    def test_backup_and_restore_round_trip_preserves_user_data(self):
        session_id = database.db_new_session("backup-test")
        database.db_save_msg(session_id, "user", "saved conversation")
        self.pdf_dir.mkdir(parents=True)
        (self.pdf_dir / "notes.pdf").write_bytes(b"%PDF-test")
        for name, path in self.json_files.items():
            path.write_text(json.dumps({"name": name}), encoding="utf-8")
        destination = self.root / "external" / "jarvis.zip"

        data_backup.create_backup(destination)
        with zipfile.ZipFile(destination) as archive:
            self.assertIn("jarvis_memory.db", archive.namelist())
            self.assertIn("pdfs/notes.pdf", archive.namelist())
            self.assertNotIn(".env", archive.namelist())

        database.db_save_msg(session_id, "assistant", "message after backup")
        self.json_files["jarvis_settings.json"].write_text(
            '{"changed": true}', encoding="utf-8"
        )
        safety_backup = data_backup.restore_backup(destination)

        self.assertTrue(safety_backup.is_file())
        self.assertEqual(database.db_get_messages(session_id), [
            {"role": "user", "content": "saved conversation"},
        ])
        self.assertEqual(
            json.loads(self.json_files["jarvis_settings.json"].read_text(encoding="utf-8")),
            {"name": "jarvis_settings.json"},
        )
        self.assertEqual((self.pdf_dir / "notes.pdf").read_bytes(), b"%PDF-test")

    def test_unsafe_archive_path_is_rejected_before_live_data_changes(self):
        settings = self.json_files["jarvis_settings.json"]
        settings.parent.mkdir(parents=True, exist_ok=True)
        settings.write_text('{"safe": true}', encoding="utf-8")
        archive_path = self.root / "unsafe.zip"
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.writestr("../outside.txt", "not allowed")
            archive.writestr("jarvis_memory.db", "invalid sqlite")

        with self.assertRaisesRegex(ValueError, "güvenli olmayan"):
            data_backup.restore_backup(archive_path)

        self.assertEqual(settings.read_text(encoding="utf-8"), '{"safe": true}')

    def test_invalid_json_is_rejected_before_live_data_changes(self):
        settings = self.json_files["jarvis_settings.json"]
        settings.parent.mkdir(parents=True, exist_ok=True)
        settings.write_text('{"before": true}', encoding="utf-8")
        backup_path = self.root / "invalid-json.zip"
        with tempfile.TemporaryDirectory() as temporary:
            staged_db = Path(temporary) / "jarvis_memory.db"
            data_backup._sqlite_backup(self.db_path, staged_db)
            with zipfile.ZipFile(backup_path, "w") as archive:
                archive.write(staged_db, "jarvis_memory.db")
                archive.writestr("jarvis_settings.json", "[not an object]")

        with self.assertRaises((ValueError, json.JSONDecodeError)):
            data_backup.restore_backup(backup_path)
        self.assertEqual(settings.read_text(encoding="utf-8"), '{"before": true}')

    def test_archive_rejects_non_pdf_payload_in_pdf_directory(self):
        backup_path = self.root / "non-pdf.zip"
        with tempfile.TemporaryDirectory() as temporary:
            staged_db = Path(temporary) / "jarvis_memory.db"
            data_backup._sqlite_backup(self.db_path, staged_db)
            with zipfile.ZipFile(backup_path, "w") as archive:
                archive.write(staged_db, "jarvis_memory.db")
                archive.writestr("pdfs/notes.txt", "not a PDF")

        with self.assertRaisesRegex(ValueError, "PDF olmayan"):
            data_backup.restore_backup(backup_path)

    def test_partial_restore_failure_rolls_database_and_json_back(self):
        session_id = database.db_new_session("restore-rollback-test")
        database.db_save_msg(session_id, "user", "before restore")
        settings = self.json_files["jarvis_settings.json"]
        settings.write_text('{"state": "archived"}', encoding="utf-8")
        self.pdf_dir.mkdir(parents=True)
        pdf = self.pdf_dir / "notes.pdf"
        pdf.write_bytes(b"archived PDF")
        archive_path = self.root / "restore-source.zip"
        data_backup.create_backup(archive_path)

        database.db_save_msg(session_id, "assistant", "live data")
        settings.write_text('{"state": "live"}', encoding="utf-8")
        pdf.write_bytes(b"live PDF")
        atomic_copy = data_backup._atomic_copy_replace
        failed = False

        def fail_pdf_once(source, destination):
            nonlocal failed
            if destination == pdf and not failed:
                failed = True
                raise OSError("simulated disk full")
            atomic_copy(source, destination)

        with mock.patch.object(
            data_backup, "_atomic_copy_replace", side_effect=fail_pdf_once
        ):
            with self.assertRaisesRegex(
                RuntimeError, "Mevcut veriler işlem öncesi durumuna döndürüldü"
            ):
                data_backup.restore_backup(archive_path)

        self.assertEqual(
            database.db_get_messages(session_id),
            [
                {"role": "user", "content": "before restore"},
                {"role": "assistant", "content": "live data"},
            ],
        )
        self.assertEqual(settings.read_text(encoding="utf-8"), '{"state": "live"}')
        self.assertEqual(pdf.read_bytes(), b"live PDF")

    def test_failed_rollback_is_reported_with_safety_backup_location(self):
        settings = self.json_files["jarvis_settings.json"]
        settings.write_text('{"state": "archived"}', encoding="utf-8")
        self.pdf_dir.mkdir(parents=True)
        pdf = self.pdf_dir / "notes.pdf"
        pdf.write_bytes(b"archived PDF")
        archive_path = self.root / "restore-source.zip"
        data_backup.create_backup(archive_path)
        settings.write_text('{"state": "live"}', encoding="utf-8")
        pdf.write_bytes(b"live PDF")

        atomic_copy = data_backup._atomic_copy_replace
        state = {"pdf_failed": False, "settings_calls": 0}

        def fail_restore_steps(source, destination):
            if destination == pdf:
                state["pdf_failed"] = True
                raise OSError("simulated disk failure")
            if destination == settings:
                state["settings_calls"] += 1
                if state["settings_calls"] > 1:
                    raise OSError("simulated rollback failure")
            if destination == self.db_path and state["pdf_failed"]:
                raise OSError("simulated database rollback failure")
            atomic_copy(source, destination)

        with mock.patch.object(
            data_backup, "_atomic_copy_replace", side_effect=fail_restore_steps
        ):
            with self.assertRaisesRegex(RuntimeError, "Geri alma hataları") as raised:
                data_backup.restore_backup(archive_path)

        self.assertIn("İşlem öncesi güvenlik yedeği:", str(raised.exception))
        self.assertTrue(list((self.data_dir / "backups").glob("pre-restore-*.zip")))


if __name__ == "__main__":
    unittest.main()
