"""SQLite veri katmanı — sohbet geçmişi, ayarlar ve audit log.

Faz 2'de cihaz eşleştirme tabloları da buraya eklenecek; her özellik kendi
tablosunda tutulur ve tablolar `init_db` içinde bildirilir.
"""
from __future__ import annotations

import datetime
import sqlite3
import threading
from contextlib import closing
from typing import Any, Optional

from .. import config

_write_lock = threading.Lock()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id TEXT NOT NULL DEFAULT 'local',
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    actor TEXT NOT NULL,
    event TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT ''
);
"""


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    """Taze bir SQLite bağlantısı döndürür (WAL modu, satır sözlüğü)."""
    conn = sqlite3.connect(str(config.DB_PATH), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    """Tabloları oluşturur ve varsayılan ayarları ekler (idempotent)."""
    with _write_lock, closing(connect()) as conn, conn:
        conn.executescript(_SCHEMA)
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(messages)").fetchall()
        }
        if "owner_id" not in columns:
            conn.execute(
                "ALTER TABLE messages ADD COLUMN owner_id TEXT NOT NULL DEFAULT 'local'"
            )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_owner_id_id "
            "ON messages (owner_id, id)"
        )
        for key, value in _default_settings().items():
            conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, value),
            )


def _default_settings() -> dict[str, str]:
    return {
        "background_color": config.DEFAULT_BG_COLOR,
        "city": config.DEFAULT_CITY,
        "command_count": "0",
    }


# ── Ayarlar ──────────────────────────────────────────────────────────────────

def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    with closing(connect()) as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    with _write_lock, closing(connect()) as conn, conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def get_all_settings() -> dict[str, str]:
    with closing(connect()) as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
    return {row["key"]: row["value"] for row in rows}


def increment_setting_int(key: str, by: int = 1) -> int:
    """Bir sayaç ayarını artırır (upsert) ve yeni değeri döndürür."""
    with _write_lock, closing(connect()) as conn, conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = "
            "CAST(CAST(value AS INTEGER) + ? AS TEXT)",
            (key, str(by), by),
        )
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return int(row["value"])


# ── Sohbet geçmişi ───────────────────────────────────────────────────────────

def add_message(role: str, content: str, owner_id: str = "local") -> int:
    with _write_lock, closing(connect()) as conn, conn:
        cur = conn.execute(
            "INSERT INTO messages (owner_id, role, content, created_at) "
            "VALUES (?, ?, ?, ?)",
            (owner_id, role, content, _now()),
        )
    return int(cur.lastrowid or 0)


def get_messages(limit: int = 200, owner_id: str = "local") -> list[dict[str, Any]]:
    with closing(connect()) as conn:
        rows = conn.execute(
            "SELECT id, role, content, created_at FROM messages "
            "WHERE owner_id = ? ORDER BY id DESC LIMIT ?",
            (owner_id, limit),
        ).fetchall()
    return [dict(row) for row in reversed(rows)]


def clear_messages(owner_id: str = "local") -> int:
    with _write_lock, closing(connect()) as conn, conn:
        cur = conn.execute("DELETE FROM messages WHERE owner_id = ?", (owner_id,))
    return int(cur.rowcount or 0)


# ── Audit log (Faz 2'de cihaz kimlikleriyle birlikte) ─────────────────────────

def audit(event: str, actor: str = "local", detail: str = "") -> None:
    with _write_lock, closing(connect()) as conn, conn:
        conn.execute(
            "INSERT INTO audit_log (ts, actor, event, detail) VALUES (?, ?, ?, ?)",
            (_now(), actor, event, detail[:500]),
        )


def get_audit(limit: int = 100) -> list[dict[str, Any]]:
    with closing(connect()) as conn:
        rows = conn.execute(
            "SELECT id, ts, actor, event, detail FROM audit_log "
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]
