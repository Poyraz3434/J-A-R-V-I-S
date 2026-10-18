"""Sohbet çekirdeği — REST ucu ve sesli modun birlikte kullandığı hatt.

Buradaki ``run_chat`` hem POST /api/chat hem de sesli moddan gelen
sözlü komutları işler; tek gerçek (source of truth) budur.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional

from ..core.stats import StatsMonitor
from ..llm.provider import ChatProvider, ProviderError
from ..llm.tools import TOOL_SPECS, execute_tool
from ..store import database

logger = logging.getLogger("jarvis.chat")

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


async def run_chat(
    message: str,
    provider: ChatProvider,
    monitor: Optional[StatsMonitor] = None,
    *,
    persist: bool = True,
    source: str = "text",
    owner_id: str = "local",
) -> dict[str, Any]:
    """Bir kullanıcı iletisini uçtan uca işler.

    persist=False yalnızca içsel denemeler içindir; üretimde her mesaj
    geçmişe yazılır (gereksinim 5.3: konuşma geçmişi yerelde saklanır).
    """
    message = (message or "").strip()

    if persist:
        database.add_message("user", message, owner_id=owner_id)
        database.audit("chat.message", detail=f"[{source}] {message[:200]}")

    llm_messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    if persist:
        for row in database.get_messages(limit=24, owner_id=owner_id):
            llm_messages.append({"role": row["role"], "content": row["content"]})
    else:
        llm_messages.append({"role": "user", "content": message})

    used_tools: list[str] = []
    final: Optional[str] = None
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
        if persist:
            database.add_message("assistant", reply, owner_id=owner_id)
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

    if persist:
        database.add_message("assistant", final, owner_id=owner_id)
    return {
        "reply": final,
        "used_tools": used_tools,
        "provider": provider.name,
        "model": provider.model,
        "error": False,
    }
