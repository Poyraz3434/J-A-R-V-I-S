"""Validated backup and restore for JARVIS-local user data."""
from __future__ import annotations

import json
import os
from contextlib import closing
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import tempfile
import time
import zipfile

from config import (
    APP_DATA_DIR,
    CONTACTS_FILE,
    DB_PATH,
    PDF_STORE,
    PROFILE_FILE,
    SETTINGS_FILE,
    STYLE_PATH,
)
from logger_setup import logger

_JSON_FILES = {
    "jarvis_settings.json": Path(SETTINGS_FILE),
    "jarvis_profile.json": Path(PROFILE_FILE),
    "user_style.json": Path(STYLE_PATH),
    "jarvis_contacts.json": Path(CONTACTS_FILE),
}
_MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
_MAX_JSON_BYTES = 16 * 1024 * 1024
_REQUIRED_TABLES = {
    "sessions", "messages", "reminders", "watchlist", "finance_history",
}


def _sqlite_backup(source: Path, destination: Path) -> None:
    source_db = sqlite3.connect(source, timeout=10)
    destination_db = sqlite3.connect(destination, timeout=10)
    try:
        source_db.backup(destination_db)
    finally:
        destination_db.close()
        source_db.close()
    with closing(sqlite3.connect(destination, timeout=10)) as check_db:
        try:
            result = check_db.execute("PRAGMA integrity_check").fetchone()
            if not result or result[0] != "ok":
                raise ValueError("SQLite yedeğinin bütünlük kontrolü başarısız.")
        finally:
            check_db.close()


def _atomic_copy_replace(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        shutil.copy2(source, temporary)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def create_backup(destination: str | os.PathLike) -> Path:
    """Create a consistent ZIP backup; API credentials and logs are excluded."""
    archive_path = Path(destination).expanduser().resolve()
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    protected_files = {Path(DB_PATH).resolve(), *(path.resolve() for path in _JSON_FILES.values())}
    if archive_path in protected_files:
        raise ValueError("Yedek hedefi JARVIS'in mevcut veri dosyası olamaz.")

    with tempfile.TemporaryDirectory(
        prefix=".jarvis-backup-", dir=archive_path.parent
    ) as temporary:
        staged_db = Path(temporary) / "jarvis_memory.db"
        staged_archive = Path(temporary) / archive_path.name
        source_db = Path(DB_PATH)
        if not source_db.is_file():
            raise FileNotFoundError("JARVIS veritabanı henüz oluşturulmamış.")
        _sqlite_backup(source_db, staged_db)

        with zipfile.ZipFile(
            staged_archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6
        ) as archive:
            archive.write(staged_db, "jarvis_memory.db")
            for archive_name, source in _JSON_FILES.items():
                if source.is_file():
                    archive.write(source, archive_name)
            pdf_root = Path(PDF_STORE).resolve()
            if pdf_root.is_dir():
                for pdf in pdf_root.rglob("*.pdf"):
                    if pdf.is_file() and not pdf.is_symlink():
                        resolved_pdf = pdf.resolve()
                        if pdf_root in resolved_pdf.parents:
                            archive.write(
                                resolved_pdf,
                                "pdfs/" + resolved_pdf.relative_to(pdf_root).as_posix(),
                            )
        os.replace(staged_archive, archive_path)
    try:
        os.chmod(archive_path, 0o600)
    except OSError:
        logger.warning("Yedek dosyasının izinleri sınırlandırılamadı.")
    logger.info("JARVIS verileri yedeklendi: %s", archive_path.name)
    return archive_path


def _validate_archive(archive: zipfile.ZipFile) -> tuple[set[str], list[str]]:
    names = set()
    pdf_entries = []
    total_size = 0
    for info in archive.infolist():
        path = PurePosixPath(info.filename)
        if (
            path.is_absolute()
            or ".." in path.parts
            or any(":" in part for part in path.parts)
            or "\\" in info.filename
            or info.filename in names
            or info.flag_bits & 0x1
        ):
            raise ValueError("Yedek arşivinde güvenli olmayan dosya yolu var.")
        names.add(info.filename)
        total_size += info.file_size
        if total_size > _MAX_ARCHIVE_BYTES:
            raise ValueError("Yedek arşivi izin verilen boyut sınırını aşıyor.")
        if info.filename.startswith("pdfs/"):
            relative = path.relative_to("pdfs")
            if any(part in {"", ".", ".."} for part in relative.parts):
                raise ValueError("Yedekte geçersiz PDF yolu var.")
            if not info.is_dir():
                if relative.suffix.lower() != ".pdf":
                    raise ValueError("Yedek arşivindeki PDF klasöründe PDF olmayan dosya var.")
                pdf_entries.append(info.filename)
        elif info.filename not in {"jarvis_memory.db", *_JSON_FILES}:
            raise ValueError(f"Yedekte desteklenmeyen içerik var: {info.filename}")
        if info.filename in _JSON_FILES and info.file_size > _MAX_JSON_BYTES:
            raise ValueError("Yedekteki ayar dosyası beklenenden büyük.")
    if "jarvis_memory.db" not in names:
        raise ValueError("Yedekte JARVIS veritabanı bulunamadı.")
    return names, pdf_entries


def restore_backup(source: str | os.PathLike) -> Path:
    """Validate the complete archive, take a pre-restore backup, then restore."""
    archive_path = Path(source).expanduser().resolve()
    if archive_path.stat().st_size > _MAX_ARCHIVE_BYTES:
        raise ValueError("Yedek arşivi izin verilen boyut sınırını aşıyor.")
    with zipfile.ZipFile(archive_path, "r") as archive:
        _, pdf_entries = _validate_archive(archive)
        corrupt_entry = archive.testzip()
        if corrupt_entry is not None:
            raise ValueError(f"Yedekte bozuk veri bulundu: {corrupt_entry}")
        with tempfile.TemporaryDirectory(prefix="jarvis-restore-") as temporary:
            staging = Path(temporary)
            staged_db = staging / "jarvis_memory.db"
            with archive.open("jarvis_memory.db") as source_db, staged_db.open("wb") as target_db:
                shutil.copyfileobj(source_db, target_db)
            with closing(sqlite3.connect(staged_db)) as database:
                integrity = database.execute("PRAGMA integrity_check").fetchone()
                tables = {
                    row[0]
                    for row in database.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
                database.close()
            if not integrity or integrity[0] != "ok":
                raise ValueError("Yedek veritabanı bozuk; mevcut veriler değiştirilmedi.")
            if not _REQUIRED_TABLES.issubset(tables):
                raise ValueError("Yedek, gerekli JARVIS veritabanı tablolarını içermiyor.")

            staged_json = {}
            for name, destination in _JSON_FILES.items():
                if name not in archive.namelist():
                    continue
                payload = json.loads(archive.read(name).decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError(f"{name} içeriği JSON nesnesi olmalı.")
                staged_file = staging / name
                staged_file.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                staged_json[destination] = staged_file

            staged_pdfs = []
            for entry in pdf_entries:
                relative = PurePosixPath(entry).relative_to("pdfs")
                staged_pdf = staging / "pdfs" / Path(*relative.parts)
                staged_pdf.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(entry) as source_pdf, staged_pdf.open("wb") as target_pdf:
                    shutil.copyfileobj(source_pdf, target_pdf)
                staged_pdfs.append((relative, staged_pdf))

            live_db = Path(DB_PATH)
            pdf_root = Path(PDF_STORE).resolve()
            pdf_destinations = []
            for relative, staged_pdf in staged_pdfs:
                destination = pdf_root.joinpath(*relative.parts).resolve()
                if pdf_root not in destination.parents:
                    raise ValueError("Yedekte PDF yolu uygulama klasörünün dışına çıkıyor.")
                pdf_destinations.append((destination, staged_pdf))

            backup_dir = Path(APP_DATA_DIR) / "backups"
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            backup_path = backup_dir / f"pre-restore-{timestamp}.zip"
            counter = 1
            while backup_path.exists():
                backup_path = backup_dir / f"pre-restore-{timestamp}-{counter}.zip"
                counter += 1
            safety_backup = create_backup(backup_path)
            originals_dir = staging / "pre-restore"
            originals_dir.mkdir()
            rollback_db = originals_dir / "jarvis_memory.db"
            if live_db.is_file():
                _sqlite_backup(live_db, rollback_db)

            original_json = {}
            for index, destination in enumerate(staged_json):
                if destination.is_file():
                    snapshot = originals_dir / f"json-{index}.bak"
                    shutil.copy2(destination, snapshot)
                    original_json[destination] = snapshot
                else:
                    original_json[destination] = None

            original_pdfs = {}
            for index, (destination, _) in enumerate(pdf_destinations):
                if destination.is_file():
                    snapshot = originals_dir / f"pdf-{index}.bak"
                    shutil.copy2(destination, snapshot)
                    original_pdfs[destination] = snapshot
                else:
                    original_pdfs[destination] = None

            db_replaced = False
            changed_json = []
            changed_pdfs = []
            try:
                if live_db.exists():
                    with closing(sqlite3.connect(live_db, timeout=10)) as current_db:
                        current_db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                    for suffix in ("-wal", "-shm"):
                        sidecar = Path(str(live_db) + suffix)
                        if sidecar.exists():
                            sidecar.unlink()
                live_db.parent.mkdir(parents=True, exist_ok=True)
                _atomic_copy_replace(staged_db, live_db)
                db_replaced = True
                for destination, staged_file in staged_json.items():
                    _atomic_copy_replace(staged_file, destination)
                    changed_json.append(destination)

                for destination, staged_pdf in pdf_destinations:
                    _atomic_copy_replace(staged_pdf, destination)
                    changed_pdfs.append(destination)
            except Exception as exc:
                rollback_errors = []
                for destination in reversed(changed_pdfs):
                    try:
                        previous = original_pdfs[destination]
                        if previous is None:
                            destination.unlink(missing_ok=True)
                        else:
                            _atomic_copy_replace(previous, destination)
                    except OSError as rollback_exc:
                        rollback_errors.append(f"{destination}: {rollback_exc}")
                for destination in reversed(changed_json):
                    try:
                        previous = original_json[destination]
                        if previous is None:
                            destination.unlink(missing_ok=True)
                        else:
                            _atomic_copy_replace(previous, destination)
                    except OSError as rollback_exc:
                        rollback_errors.append(f"{destination}: {rollback_exc}")
                if db_replaced:
                    try:
                        for suffix in ("-wal", "-shm"):
                            Path(str(live_db) + suffix).unlink(missing_ok=True)
                        if rollback_db.is_file():
                            _atomic_copy_replace(rollback_db, live_db)
                        else:
                            live_db.unlink(missing_ok=True)
                    except OSError as rollback_exc:
                        rollback_errors.append(f"{live_db}: {rollback_exc}")
                rollback_report = (
                    " Geri alma hataları: " + "; ".join(rollback_errors)
                    if rollback_errors
                    else " Mevcut veriler işlem öncesi durumuna döndürüldü."
                )
                raise RuntimeError(
                    f"Geri yükleme tamamlanamadı ({exc})."
                    f"{rollback_report} İşlem öncesi güvenlik yedeği: {safety_backup}"
                ) from exc

    logger.warning(
        "JARVIS verileri yedekten geri yüklendi; önceki veriler burada korundu: %s",
        safety_backup,
    )
    return safety_backup
