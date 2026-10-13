"""LLM araç (function calling) tanımları ve yürütme.

Güvenlik: Burada YALNIZCA okuma amaçlı araçlar tanımlıdır. Shell komutu
çalıştıran, dosya silen vb. yıkıcı araçlar kasıtlı olarak YOKTUR
(gereksinim 5.3). Faz 5'te dosya transferi eklendiğinde de kullanıcı onayı
zorunlu tutulacaktır.
"""
from __future__ import annotations

import asyncio
import datetime
from typing import Any, Optional

from ..core import weather as weather_module

TOOL_SPECS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_system_stats",
            "description": (
                "Bilgisayarın canlı sistem istatistiklerini getirir: CPU yüzdesi, "
                "çekirdek sayısı, RAM ve disk kullanımı, çalışma süresi, sistem yükü."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Şu anki yerel tarih ve saati getirir.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": (
                "Şehir için güncel hava durumunu getirir. Şehir verilmezse "
                "ayarlanmış varsayılan şehir kullanılır. Örnek: 'Tuzla,TR'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "Hava durumu sorgulanacak şehir (örn. 'Tuzla,TR').",
                    }
                },
                "required": [],
            },
        },
    },
]

VALID_TOOL_NAMES = {spec["function"]["name"] for spec in TOOL_SPECS}


async def execute_tool(
    name: str,
    arguments: Optional[dict[str, Any]],
    monitor: Any = None,
) -> dict[str, Any]:
    """Aracı yürütür ve JSON-uyumlu bir sözlük döndürür."""
    arguments = arguments or {}

    if name == "get_system_stats":
        if monitor is not None:
            data = monitor.snapshot()
            if data:
                return data
        return {"error": "istatistikler henüz hazır değil, kısa süre sonra tekrar dene"}

    if name == "get_current_time":
        return {
            "datetime": datetime.datetime.now().isoformat(timespec="seconds"),
            "timezone": datetime.datetime.now().astimezone().tzname() or "",
        }

    if name == "get_weather":
        city = str(arguments.get("city") or "").strip() or None
        # Ağ çağrısı olay döngüsünü bloklamasın:
        return await asyncio.to_thread(weather_module.get, city)

    return {"error": f"bilinmeyen araç: {name}"}
