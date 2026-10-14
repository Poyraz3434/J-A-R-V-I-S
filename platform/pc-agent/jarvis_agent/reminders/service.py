"""Reminder service: scheduling, firing, acknowledgement and snooze.

The service owns the ``reminders`` SQLite table (created on first use) and
exposes the in-process API used by the API routes, LLM tools, chat and voice
services. Alarm events are emitted through an optional ``announcer`` callable
(the app wires this to the WebSocket broadcast layer).
"""

from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Iterator, List, Optional

try:  # optional wiring - nlp parser
    from jarvis_agent.reminders.nlp import parse_iso as _nlp_parse_iso
except Exception:  # pragma: no cover
    _nlp_parse_iso = None

try:  # optional wiring - shared sqlite connection factory
    from jarvis_agent.store.database import connect as _db_connect
except Exception:  # pragma: no cover
    _db_connect = None

try:  # optional wiring - settings
    from jarvis_agent import config as _config
except Exception:  # pragma: no cover
    _config = None

logger = logging.getLogger(__name__)

#: How many times an unacknowledged alarm may repeat before it expires.
MAX_REPEATS = 3
#: Minimum delay between two fires of the same alarm (seconds).
REPEAT_EVERY_SECONDS = 120

STATUS_PENDING = "pending"
STATUS_FIRING = "firing"
STATUS_ACKED = "acked"
STATUS_EXPIRED = "expired"
ACTIVE_STATUSES = (STATUS_PENDING, STATUS_FIRING)

_ACK_PHRASES = (
    "tamam", "kapat", "kapatti", "anladi", "duydum", "oldu",
    "yeter", "sus", "sessiz", "ok", "stop",
)


def _as_naive(value: datetime) -> datetime:
    if value.tzinfo is not None:
        value = value.astimezone().replace(tzinfo=None)
    return value


def _fallback_parse_iso(value: Any) -> datetime:
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return _as_naive(datetime.fromisoformat(text))


parse_iso: Callable[[Any], datetime] = _nlp_parse_iso or _fallback_parse_iso


def _parse_due(value: Any) -> datetime:
    if isinstance(value, datetime):
        return _as_naive(value)
    try:
        parsed = parse_iso(value)
        if isinstance(parsed, datetime):
            return _as_naive(parsed)
    except Exception:
        pass
    return _fallback_parse_iso(value)


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat(timespec="seconds") if value else None


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _alarm_idle_ack_seconds() -> int:
    return int(getattr(_config, "ALARM_IDLE_ACK_SECONDS", 5) or 5)


class ReminderService:
    """SQLite-backed reminder store with a manually driven alarm loop."""

    def __init__(
        self,
        announcer: Optional[Callable[[Dict[str, Any]], Any]] = None,
        *,
        db_path: Optional[str] = None,
        broadcast: Optional[Callable[[Dict[str, Any]], Any]] = None,
    ) -> None:
        self.announcer = announcer or broadcast
        self._db_path = db_path
        self._activity_counts: Dict[str, int] = {}
        self._last_activity_at: Optional[datetime] = None
        self._ensure_schema()

    # ------------------------------------------------------------------ storage
    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        if _db_connect is not None:
            conn = _db_connect()
        else:  # pragma: no cover - direct fallback
            conn = sqlite3.connect(self._db_path or "jarvis.db")
            conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _ensure_schema(self) -> None:
        with self._connection() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS reminders ("
                " id INTEGER PRIMARY KEY AUTOINCREMENT,"
                " title TEXT NOT NULL,"
                " due_at TEXT NOT NULL,"
                " status TEXT NOT NULL DEFAULT 'pending',"
                " repeat_count INTEGER NOT NULL DEFAULT 0,"
                " last_fired_at TEXT,"
                " created_at TEXT NOT NULL,"
                " updated_at TEXT NOT NULL)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_reminders_status_due"
                " ON reminders (status, due_at)"
            )

    @staticmethod
    def _to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "id": row["id"],
            "title": row["title"],
            "due_at": row["due_at"],
            "status": row["status"],
            "repeat_count": row["repeat_count"],
            "last_fired_at": row["last_fired_at"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    # ------------------------------------------------------------------ events
    def _broadcast(self, event: str, payload: Dict[str, Any]) -> None:
        message: Dict[str, Any] = {"type": "reminder", "event": event, "payload": payload}
        if self.announcer is None:
            return
        try:
            self.announcer(message)
        except Exception:
            logger.exception("reminder announcer failed")

    # ------------------------------------------------------------------ CRUD
    def create(self, title: str, due: Any = None, *, due_at: Any = None) -> Dict[str, Any]:
        raw = due if due is not None else due_at
        if raw is None:
            raise ValueError("create() requires a due datetime or ISO string")
        clean_title = str(title or "").strip()
        if not clean_title:
            raise ValueError("create() requires a non-empty title")
        moment = _parse_due(raw)
        now = _now_iso()
        with self._connection() as conn:
            cursor = conn.execute(
                "INSERT INTO reminders (title, due_at, status, repeat_count, created_at, updated_at)"
                " VALUES (?, ?, ?, 0, ?, ?)",
                (clean_title, _iso(moment), STATUS_PENDING, now, now),
            )
            new_id = int(cursor.lastrowid or 0)
        reminder = self.get(new_id)
        assert reminder is not None
        self._broadcast("created", {"reminder": reminder})
        return reminder

    def get(self, reminder_id: int) -> Optional[Dict[str, Any]]:
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM reminders WHERE id = ?", (int(reminder_id),)
            ).fetchone()
        return self._to_dict(row) if row is not None else None

    def list(self, include_history: bool = True) -> List[Dict[str, Any]]:
        query = "SELECT * FROM reminders"
        params: tuple = ()
        if not include_history:
            marks = ",".join("?" * len(ACTIVE_STATUSES))
            query += f" WHERE status IN ({marks})"
            params = ACTIVE_STATUSES
        query += " ORDER BY due_at ASC, id ASC"
        with self._connection() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._to_dict(row) for row in rows]

    def delete(self, reminder_id: int) -> bool:
        with self._connection() as conn:
            cursor = conn.execute(
                "DELETE FROM reminders WHERE id = ?", (int(reminder_id),)
            )
            deleted = cursor.rowcount > 0
        if deleted:
            self._broadcast("deleted", {"id": int(reminder_id)})
        return deleted

    # ------------------------------------------------------------------ alarm loop
    def tick(self) -> List[Dict[str, Any]]:
        now = datetime.now()
        results: List[Dict[str, Any]] = []
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM reminders WHERE status IN (?, ?) ORDER BY due_at ASC",
                ACTIVE_STATUSES,
            ).fetchall()
            for row in rows:
                due = _parse_due(row["due_at"])
                repeat_count = int(row["repeat_count"] or 0)
                last_fired = _parse_due(row["last_fired_at"]) if row["last_fired_at"] else None
                fire = False
                expire = False
                if row["status"] == STATUS_PENDING:
                    if due <= now:
                        fire = True  # first fire keeps repeat_count at 0
                else:  # STATUS_FIRING
                    if repeat_count >= MAX_REPEATS:
                        expire = True
                    else:
                        anchor = last_fired or due
                        if (now - anchor).total_seconds() >= REPEAT_EVERY_SECONDS:
                            repeat_count += 1
                            fire = True
                if expire:
                    conn.execute(
                        "UPDATE reminders SET status = ?, updated_at = ? WHERE id = ?",
                        (STATUS_EXPIRED, _now_iso(), row["id"]),
                    )
                    results.append({**self._to_dict(row), "status": STATUS_EXPIRED})
                elif fire:
                    fired_at = _now_iso()
                    conn.execute(
                        "UPDATE reminders SET status = ?, repeat_count = ?,"
                        " last_fired_at = ?, updated_at = ? WHERE id = ?",
                        (STATUS_FIRING, repeat_count, fired_at, fired_at, row["id"]),
                    )
                    results.append({
                        **self._to_dict(row),
                        "status": STATUS_FIRING,
                        "repeat_count": repeat_count,
                        "last_fired_at": fired_at,
                    })
        for reminder in results:
            event = "expired" if reminder["status"] == STATUS_EXPIRED else "fired"
            self._broadcast(event, {"reminder": reminder})
        return results

    def active_alarms(self) -> List[Dict[str, Any]]:
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM reminders WHERE status = ?"
                " ORDER BY last_fired_at DESC, due_at ASC",
                (STATUS_FIRING,),
            ).fetchall()
        return [self._to_dict(row) for row in rows]

    def ack(self, reminder_id: int, by: str = "user") -> Optional[Dict[str, Any]]:
        with self._connection() as conn:
            cursor = conn.execute(
                "UPDATE reminders SET status = ?, updated_at = ?"
                " WHERE id = ? AND status != ?",
                (STATUS_ACKED, _now_iso(), int(reminder_id), STATUS_EXPIRED),
            )
            updated = cursor.rowcount > 0
        reminder = self.get(reminder_id)
        if updated:
            self._broadcast("acked", {"reminder": reminder, "by": by})
        return reminder

    def ack_all(self, by: str = "user") -> int:
        marks = ",".join("?" * len(ACTIVE_STATUSES))
        with self._connection() as conn:
            cursor = conn.execute(
                f"UPDATE reminders SET status = ?, updated_at = ? WHERE status IN ({marks})",
                (STATUS_ACKED, _now_iso(), *ACTIVE_STATUSES),
            )
            count = int(cursor.rowcount or 0)
        if count:
            logger.debug("ack_all by=%s count=%s", by, count)
            self._broadcast("acked_all", {"by": by, "count": count})
        return count

    def snooze(self, reminder_id: int, minutes: float, by: str = "user") -> Optional[Dict[str, Any]]:
        try:
            minutes = float(minutes)
        except (TypeError, ValueError):
            raise ValueError("snooze() requires a numeric minutes value")
        if minutes <= 0:
            raise ValueError("snooze() requires a positive number of minutes")
        moment = datetime.now() + timedelta(minutes=minutes)
        with self._connection() as conn:
            cursor = conn.execute(
                "UPDATE reminders SET status = ?, due_at = ?, repeat_count = 0,"
                " updated_at = ? WHERE id = ? AND status IN (?, ?, ?)",
                (STATUS_PENDING, _iso(moment), _now_iso(), int(reminder_id),
                 STATUS_PENDING, STATUS_FIRING, STATUS_ACKED),
            )
            updated = cursor.rowcount > 0
        reminder = self.get(reminder_id)
        if updated and reminder is not None:
            self._broadcast("snoozed", {"reminder": reminder, "by": by})
        return reminder

    # ------------------------------------------------------------------ user signals
    def notify_user_text(self, text: str, *, source: str = "voice") -> Dict[str, Any]:
        normalized = " ".join(str(text or "").lower().split())
        matched = [phrase for phrase in _ACK_PHRASES if phrase in normalized]
        alarms = self.active_alarms()
        if not matched or not alarms:
            return {
                "silenced": False,
                "acked": 0,
                "matched": matched,
                "remaining": len(alarms),
            }
        acked = 0
        for alarm in alarms:
            if self.ack(alarm["id"], by=f"{source}:text") is not None:
                acked += 1
        return {
            "silenced": acked > 0,
            "acked": acked,
            "matched": matched,
            "remaining": max(len(alarms) - acked, 0),
        }

    def notify_user_activity(self, source: str = "input") -> int:
        """Kullanıcı etkinliği ping'i — ALARM_IDLE_ACK_SECONDS içinde ateşlenmiş
        aktif alarmları sessize alır (koşul 1: kullanıcı zaten başında).

        Returns:
            Sessize alınan (ack edilen) alarm sayısı.
        """
        now = datetime.now()
        self._activity_counts[source] = self._activity_counts.get(source, 0) + 1
        self._last_activity_at = now
        silenced = 0
        threshold = _alarm_idle_ack_seconds()
        for alarm in self.active_alarms():
            fired_at = _parse_due(alarm["last_fired_at"]) if alarm["last_fired_at"] else None
            if fired_at is not None and (now - fired_at).total_seconds() <= threshold:
                if self.ack(alarm["id"], by=f"{source}:activity") is not None:
                    silenced += 1
        return silenced


#: Module-level singleton shared by tools, chat and voice services.
SERVICE = ReminderService()

__all__ = [
    "MAX_REPEATS",
    "REPEAT_EVERY_SECONDS",
    "ReminderService",
    "SERVICE",
    "STATUS_ACKED",
    "STATUS_EXPIRED",
    "STATUS_FIRING",
    "STATUS_PENDING",
    "parse_iso",
]