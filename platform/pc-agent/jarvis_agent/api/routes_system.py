"""Sistem uçları: sağlık kontrolü, canlı istatistik, hava durumu, audit."""
from __future__ import annotations

import time

from fastapi import APIRouter, Request

from .. import config
from ..core import counters
from ..core import weather as weather_module
from ..store import database

router = APIRouter()


def build_stats_payload(app) -> dict:
    """İstatistik anlık görüntüsü + kullanıcı sayaçları (REST ve WS ortak).

    ``app`` doğrudan FastAPI uygulamasıdır (Request/WebSocket'ten ``.app``
    ile alınır); böylece iki protokol aynı kodu paylaşır.
    """
    snap = dict(app.state.stats.snapshot())
    snap["command_count"] = counters.get_command_count()
    snap["session_count"] = counters.get_session_count()
    # Mikrofon dinleme durumu her istatistik itmesinde taşınır (gereklim 5.4).
    voice = getattr(app.state, "voice", None)
    if voice is not None:
        snap["voice"] = voice.status()
    return snap


@router.get("/api/health")
def health(request: Request) -> dict:
    """Ölçüm uç noktası — arayüz bağlantı durumunu buradan anlar.

    Bilinçli olarak hafiftir: ağ çağrısı yapmaz, yalnızca bellekteki
    duruma bakar. Offline algılamanın hızlı ve garantili olması için.
    """
    provider = getattr(request.app.state, "llm", None)
    started = getattr(request.app.state, "started_at", None)
    return {
        "status": "ok",
        "version": config.APP_VERSION,
        "agent_uptime_seconds": round(time.time() - started, 1) if started else 0.0,
        "llm_provider": provider.name if provider else "none",
        "llm_ready": bool(provider is not None and provider.name != "mock"),
        "session_count": counters.get_session_count(),
    }


@router.get("/api/system/stats")
def system_stats(request: Request) -> dict:
    return build_stats_payload(request.app)


@router.get("/api/weather")
def get_weather(request: Request, refresh: bool = False) -> dict:
    city = database.get_setting("city", config.DEFAULT_CITY) or config.DEFAULT_CITY
    return weather_module.get(city, force=refresh)


@router.get("/api/audit")
def get_audit(limit: int = 100) -> dict:
    """Son audit kayıtları (Faz 1: yerel; Faz 2: cihaz bazlı)."""
    return {"entries": database.get_audit(limit=limit)}
