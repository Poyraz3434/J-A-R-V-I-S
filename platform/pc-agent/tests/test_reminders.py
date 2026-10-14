"""Hatırlatıcı servisi birim testleri — relay/voice/pynput gerektirmez.

Zamanlayıcı iş parçacığı başlatılmaz; `tick()` manuel çağrılır.
"""
from __future__ import annotations

import datetime
import uuid

from jarvis_agent.reminders.service import ReminderService


def _unique_title(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _cleanup(svc: ReminderService) -> None:
    for r in svc.list(include_history=True):
        svc.delete(r["id"])


def test_create_due_fire_and_ack():
    svc = ReminderService()
    try:
        title = _unique_title("test-ack")
        rid = svc.create(title, datetime.datetime.now() - datetime.timedelta(seconds=1))["id"]
        assert svc.get(rid)["status"] == "pending"

        svc.tick()  # zamanı geçmiş → firing + anons
        alarms = svc.active_alarms()
        assert any(a["id"] == rid for a in alarms), "Alarm firing durumda olmalı"

        acked = svc.ack(rid, by="test")
        assert acked is not None and acked["status"] == "acked"
        assert not any(a["id"] == rid for a in svc.active_alarms())
    finally:
        _cleanup(svc)


def test_repeat_then_voice_text_silence():
    svc = ReminderService()
    try:
        rid = svc.create(
            _unique_title("test-sus"),
            datetime.datetime.now() - datetime.timedelta(seconds=1),
        )["id"]
        svc.tick()
        first = svc.get(rid)
        assert first["repeat_count"] == 0

        # zaman geri alınıyor gibi: last_fired_at'i 3 dk önce yap → tekrar tetiklenir
        import sqlite3
        past = (datetime.datetime.now() - datetime.timedelta(minutes=3)).isoformat(timespec="seconds")
        conn = sqlite3.connect(":memory:")  # sadece bağlantı kalıbı; gerçek DB aşağıda
        conn.close()
        from jarvis_agent.store.database import connect as db_connect
        with db_connect() as c:
            c.execute("UPDATE reminders SET last_fired_at = ? WHERE id = ?", (past, rid))
            c.commit()

        svc.tick()
        repeated = svc.get(rid)
        assert repeated["repeat_count"] == 1, "2 dk geçen alarm tekrarlanmalı"

        result = svc.notify_user_text("tamam kapat")
        assert result["silenced"] is True
        assert svc.get(rid)["status"] == "acked"
    finally:
        _cleanup(svc)


def test_snooze_pushes_future():
    svc = ReminderService()
    try:
        rid = svc.create(
            _unique_title("test-ertele"),
            datetime.datetime.now() - datetime.timedelta(seconds=1),
        )["id"]
        svc.tick()
        snoozed = svc.snooze(rid, 15, by="test")
        assert snoozed["status"] == "pending"
        assert datetime.datetime.fromisoformat(snoozed["due_at"]) > datetime.datetime.now()
    finally:
        _cleanup(svc)


def test_activity_silences_active_alarm():
    svc = ReminderService()
    try:
        rid = svc.create(
            _unique_title("test-activity"),
            datetime.datetime.now() - datetime.timedelta(seconds=1),
        )["id"]
        svc.tick()
        assert svc.active_alarms()
        silenced = svc.notify_user_activity(source="test")
        assert silenced >= 1
        assert svc.get(rid)["status"] == "acked"
    finally:
        _cleanup(svc)


def test_expired_after_max_repeats():
    svc = ReminderService()
    try:
        rid = svc.create(
            _unique_title("test-expire"),
            datetime.datetime.now() - datetime.timedelta(seconds=1),
        )["id"]
        svc.tick()
        from jarvis_agent.store.database import connect as db_connect
        with db_connect() as c:
            c.execute(
                "UPDATE reminders SET repeat_count = ? WHERE id = ?",
                (svc and __import__("jarvis_agent.reminders.service", fromlist=["MAX_REPEATS"]).MAX_REPEATS, rid),
            )
            c.commit()
        svc.tick()
        assert svc.get(rid)["status"] == "expired"
    finally:
        _cleanup(svc)
