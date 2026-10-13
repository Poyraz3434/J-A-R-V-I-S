"""Sohbet geçmişi uçları — listeleme, temizleme, dışa aktarma (txt / md)."""
from __future__ import annotations

import datetime

from fastapi import APIRouter, Query
from fastapi.responses import Response

from ..store import database

router = APIRouter()

ROLE_LABELS = {"user": "Kullanıcı", "assistant": "JARVIS", "system": "Sistem"}


@router.get("/api/conversation")
def get_conversation(limit: int = Query(default=200, ge=1, le=1000)) -> dict:
    messages = database.get_messages(limit=limit)
    return {"messages": messages, "count": len(messages)}


@router.delete("/api/conversation")
def clear_conversation() -> dict:
    cleared = database.clear_messages()
    database.audit("conversation.clear", detail=f"{cleared} mesaj silindi")
    return {"cleared": cleared}


def _export_txt(messages: list[dict]) -> str:
    lines = [
        "JARVIS Konuşma Dökümü",
        f"Dışa aktarma: {datetime.datetime.now().isoformat(timespec='seconds')}",
        "=" * 60,
        "",
    ]
    for m in messages:
        label = ROLE_LABELS.get(m["role"], m["role"])
        lines.append(f"[{m['created_at']}] {label}:")
        lines.append(f"    {m['content']}")
        lines.append("")
    return "\n".join(lines)


def _export_md(messages: list[dict]) -> str:
    lines = ["# JARVIS Konuşma Dökümü", ""]
    for m in messages:
        label = ROLE_LABELS.get(m["role"], m["role"])
        lines.append(f"**{label}** · {m['created_at']}")
        lines.append("")
        lines.append(m["content"])
        lines.append("")
    return "\n".join(lines)


@router.get("/api/conversation/export")
def export_conversation(
    format: str = Query(default="txt", pattern="^(txt|md)$")
) -> Response:
    messages = database.get_messages(limit=1000)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    if format == "md":
        return Response(
            content=_export_md(messages),
            media_type="text/markdown; charset=utf-8",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="jarvis-conversation-{stamp}.md"'
                )
            },
        )
    return Response(
        content=_export_txt(messages),
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": (
                f'attachment; filename="jarvis-conversation-{stamp}.txt"'
            )
        },
    )
