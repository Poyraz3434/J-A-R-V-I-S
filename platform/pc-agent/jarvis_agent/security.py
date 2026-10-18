"""Cihaz eşleştirme ve güvenlik katmanı (Faz 2).

Model (kişisel kullanım, makul güvenlik):
- PC'deki yerel arayüz (loopback) daima güvenilir: token istemez.
- Telefon/LAN cihazları: PC ekranında gösterilen 6 haneli kodla eşleşir,
  karşılığında uzun ömürlü ``device_token`` alır (SQLite'ta SHA-256 özeti).
- ``JARVIS_PAIRING_REQUIRED=1`` (veya bind=0.0.0.0) ise /api/* uçları
  loopback olmayan isteklerden geçerli token ister; /api/pair/* ve
  /api/health daima açıktır.
"""
from __future__ import annotations

import hashlib
import secrets
import socket
import sqlite3
import threading
import time
from contextlib import closing
from pathlib import Path
from typing import Any, Optional

from . import config

_CODE_TTL_SECONDS = 300          # eşleştirme kodu 5 dk geçerli
_DB_LOCK = threading.Lock()
_PAIR_LOCK = threading.Lock()
_DB_PATH: Optional[Path] = None

_pending_code: dict[str, Any] = {}  # {"code": ..., "expires_at": float}
_pair_failures = 0
_pair_blocked_until = 0.0
_PAIR_MAX_FAILURES = 5
_PAIR_BLOCK_SECONDS = 60.0

_SCHEMA = """
CREATE TABLE IF NOT EXISTS devices (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    token_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_seen_at TEXT
);
"""


def init(db_path: Path) -> None:
    global _DB_PATH
    _DB_PATH = db_path
    with closing(_connect()) as conn, conn:
        conn.executescript(_SCHEMA)


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH or "jarvis-security.db"), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


# ── Eşleştirme akışı ─────────────────────────────────────────────────────────

def start_pairing() -> dict[str, Any]:
    """Yeni 6 haneli kod üretir (eskisi geçersiz olur)."""
    global _pair_failures, _pair_blocked_until
    code = f"{secrets.randbelow(1_000_000):06d}"
    with _PAIR_LOCK:
        _pending_code.clear()
        _pending_code["code"] = code
        _pending_code["expires_at"] = time.time() + _CODE_TTL_SECONDS
        _pair_failures = 0
        _pair_blocked_until = 0.0
    return {"code": code, "expires_in": _CODE_TTL_SECONDS}


def pending_code_info() -> dict[str, Any]:
    if not _pending_code or _pending_code.get("expires_at", 0) < time.time():
        return {"active": False}
    return {
        "active": True,
        "code": _pending_code["code"],
        "expires_in": int(_pending_code["expires_at"] - time.time()),
    }


def claim(code: str, device_name: str) -> Optional[dict[str, Any]]:
    """Geçerli kodu cihaz token'ıyla takas eder; kod tek kullanımlıktır."""
    global _pair_failures, _pair_blocked_until
    with _PAIR_LOCK:
        now = time.time()
        if now < _pair_blocked_until:
            return None
        expected = str(_pending_code.get("code", ""))
        if not _pending_code or _pending_code.get("expires_at", 0) < now:
            return None
        if not secrets.compare_digest(str(code).strip(), expected):
            _pair_failures += 1
            if _pair_failures >= _PAIR_MAX_FAILURES:
                _pair_blocked_until = now + _PAIR_BLOCK_SECONDS
                _pair_failures = 0
            return None
        _pending_code.clear()
        _pair_failures = 0

        token = secrets.token_urlsafe(32)
        device = {
            "id": secrets.token_hex(4),
            "name": (device_name or "cihaz").strip()[:40] or "cihaz",
            "token_hash": _hash(token),
            "created_at": _now_iso(),
        }
    with _DB_LOCK, closing(_connect()) as conn, conn:
        conn.execute(
            "INSERT INTO devices (id, name, token_hash, created_at) VALUES (?, ?, ?, ?)",
            (device["id"], device["name"], device["token_hash"], device["created_at"]),
        )
    return {"device_id": device["id"], "name": device["name"], "device_token": token}


# ── Doğrulama / yönetim ──────────────────────────────────────────────────────

def verify_token(token: str) -> Optional[dict[str, Any]]:
    if not token:
        return None
    digest = _hash(token)
    with closing(_connect()) as conn:
        row = conn.execute(
            "SELECT * FROM devices WHERE token_hash = ?", (digest,)
        ).fetchone()
    if row is None:
        return None
    with closing(_connect()) as conn, conn:
        conn.execute(
            "UPDATE devices SET last_seen_at = ? WHERE id = ?", (_now_iso(), row["id"])
        )
    return {"device_id": row["id"], "name": row["name"]}


def list_devices() -> list[dict[str, Any]]:
    with closing(_connect()) as conn:
        rows = conn.execute(
            "SELECT id, name, created_at, last_seen_at FROM devices ORDER BY created_at"
        ).fetchall()
    return [dict(r) for r in rows]


def revoke(device_id: str) -> bool:
    with closing(_connect()) as conn, conn:
        cur = conn.execute("DELETE FROM devices WHERE id = ?", (device_id,))
    return cur.rowcount > 0


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def required() -> bool:
    """Cihaz doğrulaması şart mı? Loopback dışındaki tüm bind adresleri korunur."""
    bind = config.env("JARVIS_BIND", "127.0.0.1").strip().lower()
    return config.env("JARVIS_PAIRING_REQUIRED") == "1" or bind not in {
        "127.0.0.1",
        "::1",
        "localhost",
    }


def is_loopback(host: str) -> bool:
    return host in ("127.0.0.1", "::1", "localhost", "testclient")


# ── Yardımcılar ──────────────────────────────────────────────────────────────

def lan_ip() -> Optional[str]:
    """Varsayılan rotanın yerel IP'si (paket göndermez, sadece yönlendirir)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(0.5)
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return None
