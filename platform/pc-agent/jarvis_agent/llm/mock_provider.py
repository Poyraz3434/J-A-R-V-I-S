"""Mock sağlayıcı — API anahtarı yokken sohbetin çalışmaya devam etmesini sağlar.

Gerçek bir LLM'e bağlanmaz; yerel verilerle (sistem istatistikleri, saat,
hava durumu) şablon yanıtlar üretir. Birim testlerinde de bu sağlayıcı
kullanılır, böylece testler ağa ve anahtara bağlı kalmaz.
"""
from __future__ import annotations

import datetime
from typing import Any, Optional

from .. import config
from ..core import weather as weather_module
from .provider import ChatProvider, ChatResult


class MockProvider(ChatProvider):
    name = "mock"
    model = "mock-1"

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> ChatResult:
        last_user = ""
        for msg in messages:
            if msg.get("role") == "user":
                last_user = msg.get("content") or ""
        text = last_user.lower()

        if any(
            keyword in text
            for keyword in ("sistem", "durum", "istatistik", "cpu", "ram", "disk", "bellek")
        ):
            body = (
                f"CPU kullanımı yüzde {self._cpu()}, RAM kullanımı yüzde {self._ram()}; "
                "diski de kontrol ettim, sistem görünürde stabil çalışıyor."
            )
            return ChatResult(
                content=f"Demo modu (gerçek LLM bağlı değil). {body}", model=self.model
            )

        if any(keyword in text for keyword in ("saat", "zaman", "tarih")):
            now = datetime.datetime.now()
            return ChatResult(
                content=(
                    f"Demo modu (gerçek LLM bağlı değil). Şu an saat "
                    f"{now.strftime('%H:%M')}, tarih {now.strftime('%d.%m.%Y')}."
                ),
                model=self.model,
            )

        if any(keyword in text for keyword in ("hava", "sıcaklık", "nem", "rüzgar")):
            info = weather_module.get(config.DEFAULT_CITY)
            if info.get("available"):
                return ChatResult(
                    content=(
                        f"Demo modu (gerçek LLM bağlı değil). {info['city']} için hava "
                        f"{info['description']}, sıcaklık {info['temperature']} °C."
                    ),
                    model=self.model,
                )
            return ChatResult(
                content=(
                    "Demo modu (gerçek LLM bağlı değil). Hava durumu anahtarı "
                    "tanımlı olmadığı için bu bilgiyi şu an getiremiyorum."
                ),
                model=self.model,
            )

        return ChatResult(
            content=(
                "Demo modu: henüz bir LLM sağlayıcısı yapılandırılmamış. "
                "platform/pc-agent/.env dosyasına bir API anahtarı eklediğinizde "
                "gerçek yanıtlar vermeye başlayacağım."
            ),
            model=self.model,
        )

    @staticmethod
    def _cpu() -> str:
        import psutil

        return str(round(psutil.cpu_percent(interval=0.2)))

    @staticmethod
    def _ram() -> str:
        import psutil

        return str(round(psutil.virtual_memory().percent))
