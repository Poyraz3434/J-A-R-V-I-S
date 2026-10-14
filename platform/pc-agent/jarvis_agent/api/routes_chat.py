"""Yazılı sohbet ucu — ortak çekirdek (chat/service.run_chat) + sesli moda geçiş.

Gereklim 5.4: yazılı modda "Jarvis sesli moda geç" algılanırsa "Tamamdır"
der ve sesli moda geçer.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ..chat.service import run_chat
from ..core import counters
from ..store import database
from ..voice.textmatch import is_enter_voice_command

logger = logging.getLogger("jarvis.api.chat")

router = APIRouter()


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


@router.post("/api/chat")
async def chat(payload: ChatRequest, request: Request) -> dict:
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="Mesaj boş olamaz.")

    counters.bump_command_count()
    voice = getattr(request.app.state, "voice", None)

    # ── "Jarvis sesli moda geç" — LLM'e gitmeden yerelde yakalanır ──
    if voice is not None and is_enter_voice_command(message):
        database.add_message("user", message)
        database.audit("chat.voice_enter_command", detail=message[:200])
        if voice.status().get("mic_available"):
            database.add_message("assistant", "Tamamdır.")
            voice.start_voice_mode(
                reason="text_command",
                response="Sesli moddayım efendim, sizi dinliyorum.",
            )
            return {
                "reply": "Tamamdır.",
                "used_tools": [],
                "provider": "local-command",
                "model": "voice-gate",
                "error": False,
                "voice_mode": True,
            }
        reply = (
            "Üzgünüm efendim, bu cihazda mikrofon bulunamadığı için sesli moda "
            "geçemiyorum."
        )
        database.add_message("assistant", reply)
        return {
            "reply": reply,
            "used_tools": [],
            "provider": "local-command",
            "model": "voice-gate",
            "error": False,
            "voice_mode": False,
        }

    result = await run_chat(
        message,
        request.app.state.llm,
        request.app.state.stats,
        source="text",
    )
    return result

