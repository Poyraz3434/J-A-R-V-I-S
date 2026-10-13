"""Yazılı sohbet ucu — LLM + araç (tool) çağrı döngüsü."""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ..core import counters
from ..store import database
from ..llm.provider import ProviderError
from ..llm.tools import TOOL_SPECS, execute_tool

logger = logging.getLogger("jarvis.api.chat")

router = APIRouter()

MAX_TOOL_HOPS = 3

SYSTEM_PROMPT = (
    "Sen J.A.R.V.I.S adını taşıyan kişisel bir asistansın. "
    "Kullanıcınla doğal, saygılı ve akıcı Türkçe konuş; gerektiğinde "
    "'efendim' gibi kibar bir üslup kullanabilirsin. Yanıtlarını kısa ve öz tut. "
    "Sistem saati, hava durumu ve bilgisayar durumu gibi bilgilere yalnızca "
    "sana verilen araçlar (get_system_stats, get_current_time, get_weather) "
    "aracılığıyla erişebilirsin; bu bilgileri asla tahmin etme. "
    "Kullanıcı dosya silme, bilgisayarı kapatma gibi yıkıcı bir işlem isterse "
    "onay olmadan yapamayacağını açıkça belirt; shell komutu çalıştırma "
    "yetkin yoktur."
)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


@router.post("/api/chat")
async def chat(payload: ChatRequest, request: Request) -> dict:
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="Mesaj boş olamaz.")

    database.add_message("user", message)
    counters.bump_command_count()
    database.audit("chat.message", detail=message[:200])

    provider = request.app.state.llm
    monitor = request.app.state.stats

    # Geçmişi DB'den kur (az önce eklenen kullanıcı mesajı dahil).
    llm_messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    for row in database.get_messages(limit=24):
        llm_messages.append({"role": row["role"], "content": row["content"]})

    used_tools: list[str] = []
    final: str | None = None
    try:
        for _hop in range(MAX_TOOL_HOPS):
            result = await provider.chat(llm_messages, TOOL_SPECS)
            if not result.tool_calls:
                if result.content:
                    final = result.content.strip()
                break
            llm_messages.append(
                {
                    "role": "assistant",
                    "content": result.content or "",
                    "tool_calls": [
                        {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
                        for tc in result.tool_calls
                    ],
                }
            )
            for tc in result.tool_calls:
                output = await execute_tool(tc.name, tc.arguments, monitor=monitor)
                used_tools.append(tc.name)
                llm_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tc.name,
                        "content": json.dumps(output, ensure_ascii=False),
                    }
                )
    except ProviderError as exc:
        logger.warning("LLM çağrısı başarısız: %s", exc)
        reply = (
            "Üzgünüm efendim, yanıt alamadım. Yapay zekâ sağlayıcısına şu an "
            "ulaşılamıyor gibi görünüyor."
        )
        database.add_message("assistant", reply)
        database.audit("chat.error", detail=str(exc)[:400])
        return {
            "reply": reply,
            "used_tools": [],
            "provider": provider.name,
            "model": provider.model,
            "error": True,
        }

    if not final:
        final = (
            "Üzgünüm, şu an isteğinize anlamlı bir yanıt oluşturamadım. "
            "Lütfen tekrar dener misiniz?"
        )

    database.add_message("assistant", final)
    return {
        "reply": final,
        "used_tools": used_tools,
        "provider": provider.name,
        "model": provider.model,
        "error": False,
    }
