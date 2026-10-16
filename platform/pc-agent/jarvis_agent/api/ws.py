"""WebSocket uçları — canlı istatistik akışı."""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .. import security
from .routes_system import build_stats_payload

logger = logging.getLogger("jarvis.api.ws")

router = APIRouter()

PUSH_INTERVAL_SECONDS = 2.0


@router.websocket("/ws/stats")
async def ws_stats(websocket: WebSocket) -> None:
    """İstemciye 2 saniyede bir sistem istatistiği iter.

    İstemci koparsa sessizce sonlanır; frontend kendi tarafında yeniden
    bağlanma zamanlayıcısını yönetir (otomatik retry gereksinimi).
    Güvenlik (Faz 2): eşleştirme şartsa loopback dışı istemciler geçerli
    ``?token=`` (device_token) göndermek zorundadır.
    """
    host = websocket.client.host if websocket.client else ""
    if security.required() and not security.is_loopback(host):
        token = websocket.query_params.get("token", "")
        if security.verify_token(token) is None:
            await websocket.close(code=4401)
            return
    await websocket.accept()
    try:
        while True:
            await websocket.send_json(build_stats_payload(websocket.app))
            await asyncio.sleep(PUSH_INTERVAL_SECONDS)
    except WebSocketDisconnect:
        pass
    except Exception:  # beklenmedik kopma — uygulama düşmemeli
        try:
            await websocket.close()
        except Exception:
            pass
