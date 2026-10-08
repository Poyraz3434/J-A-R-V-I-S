"""Persistent allowlisted daily routines stored in Jarvis's private SQLite DB."""
from __future__ import annotations

import datetime as dt
import re
import sqlite3
from dataclasses import dataclass

from config import DB_PATH


@dataclass(frozen=True)
class Routine:
    id: int
    title: str
    action: str
    run_at: str
    enabled: bool


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH, timeout=5.0)
    connection.execute("PRAGMA busy_timeout=5000")
    connection.execute(
        """CREATE TABLE IF NOT EXISTS jarvis_routines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            action TEXT NOT NULL CHECK(action = 'daily_briefing'),
            run_at TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            last_run_date TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_jarvis_routines_due "
        "ON jarvis_routines(enabled, run_at)"
    )
    return connection


def add_daily_briefing(run_at: str) -> int:
    match = re.fullmatch(r"(\d{1,2}):(\d{2})", str(run_at).strip())
    if not match:
        raise ValueError("Saat HH:MM biçiminde olmalı.")
    try:
        parsed = dt.time(int(match.group(1)), int(match.group(2)))
    except ValueError as exc:
        raise ValueError("Saat HH:MM biçiminde olmalı.") from exc
    normalized_time = parsed.strftime("%H:%M")
    connection = _connect()
    try:
        with connection:
            cursor = connection.execute(
                """INSERT INTO jarvis_routines(title, action, run_at, enabled)
                   VALUES (?, 'daily_briefing', ?, 1)""",
                ("Günlük brifing", normalized_time),
            )
            return int(cursor.lastrowid)
    finally:
        connection.close()


def list_routines() -> list[Routine]:
    connection = _connect()
    try:
        rows = connection.execute(
            "SELECT id, title, action, run_at, enabled FROM jarvis_routines "
            "ORDER BY run_at, id"
        ).fetchall()
        return [
            Routine(int(row[0]), str(row[1]), str(row[2]), str(row[3]), bool(row[4]))
            for row in rows
        ]
    finally:
        connection.close()


def remove_routine(routine_id: int) -> bool:
    if routine_id < 1:
        raise ValueError("Rutin numarası geçersiz.")
    connection = _connect()
    try:
        with connection:
            cursor = connection.execute(
                "DELETE FROM jarvis_routines WHERE id=?", (routine_id,)
            )
            return cursor.rowcount > 0
    finally:
        connection.close()


def claim_due_routines(now: dt.datetime | None = None) -> list[Routine]:
    """Claim today's due routines once, even when the monitor polls repeatedly."""
    current = now or dt.datetime.now()
    today = current.date().isoformat()
    current_time = current.strftime("%H:%M")
    connection = _connect()
    try:
        with connection:
            rows = connection.execute(
                """SELECT id, title, action, run_at, enabled
                   FROM jarvis_routines
                   WHERE enabled=1 AND run_at<=? AND
                         (last_run_date IS NULL OR last_run_date<>?)
                   ORDER BY run_at, id""",
                (current_time, today),
            ).fetchall()
            if rows:
                connection.executemany(
                    "UPDATE jarvis_routines SET last_run_date=? WHERE id=?",
                    [(today, int(row[0])) for row in rows],
                )
        return [
            Routine(int(row[0]), str(row[1]), str(row[2]), str(row[3]), bool(row[4]))
            for row in rows
        ]
    finally:
        connection.close()
