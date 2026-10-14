"""Hatırlatıcı REST uçları — Faz 4 (UI ve LLM araçları buradan geçer)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ..core import counters
from ..reminders.service import ReminderService, parse_iso
from ..store import database

router = APIRouter()


def _svc(request: Request) -> ReminderService:
    service = getattr(request.app.state, "reminders", None)
    if service is None:
        raise HTTPException(status_code=503, detail="Hatırlatıcı servisi hazır değil.")
    return service


class ReminderCreateBody(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    due_at: str = Field(min_length=8, max_length=40)  # ISO-8601 yerel
    note: str = Field(default="", max_length=1000)


class SnoozeBody(BaseModel):
    minutes: int = Field(default=10, ge=1, le=1440)


@router.get("/api/reminders")
def list_reminders(request: Request, history: bool = False) -> dict:
    return {"reminders": _svc(request).list(include_history=history)}


@router.post("/api/reminders")
def create_reminder(payload: ReminderCreateBody, request: Request) -> dict:
    due = parse_iso(payload.due_at)
    if due is None:
        raise HTTPException(
            status_code=422,
            detail="due_at ISO-8601 biçiminde olmalı (örn. 2026-10-14T09:00:00).",
        )
    counters.bump_command_count()
    reminder = _svc(request).create(
        payload.title.strip(), due, payload.note, source="ui"
    )
    return {"reminder": reminder}


@router.get("/api/reminders/alarms")
def active_alarms(request: Request) -> dict:
    return {"alarms": _svc(request).active_alarms()}


@router.post("/api/reminders/ack-all")
def ack_all(request: Request) -> dict:
    count = _svc(request).ack_all(by="ui")
    return {"acked": count}


@router.post("/api/reminders/activity")
def report_activity(request: Request) -> dict:
    """Arayüzden etkinlik ping'i — aktif alarm varsa susar (koşul 1)."""
    silenced = _svc(request).notify_user_activity(source="ui")
    return {"silenced": silenced}


@router.delete("/api/reminders/{rid}")
def delete_reminder(rid: int, request: Request) -> dict:
    if not _svc(request).delete(rid):
        raise HTTPException(status_code=404, detail="Hatırlatıcı bulunamadı.")
    return {"deleted": rid}


@router.post("/api/reminders/{rid}/ack")
def ack_reminder(rid: int, request: Request) -> dict:
    reminder = _svc(request).ack(rid, by="ui")
    if reminder is None:
        raise HTTPException(status_code=404, detail="Hatırlatıcı bulunamadı.")
    return {"reminder": reminder}


@router.post("/api/reminders/{rid}/snooze")
def snooze_reminder(rid: int, payload: SnoozeBody, request: Request) -> dict:
    reminder = _svc(request).snooze(rid, payload.minutes, by="ui")
    if reminder is None:
        raise HTTPException(status_code=404, detail="Hatırlatıcı bulunamadı.")
    return {"reminder": reminder}
