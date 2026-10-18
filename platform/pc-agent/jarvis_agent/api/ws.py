"""WebSocket uçları — canlı istatistik akışı."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .. import security
from .routes_system import build_stats_payload

logger = logging.getLogger("jarvis.api.ws")

router = APIRouter()

PUSH_INTERVAL_SECONDS = 2.0


@dataclass
class _Connection:
    client_id: str
    websocket: WebSocket


class ConnectionManager:
    """Tracks isolated sockets; targeted sends never broadcast globally."""

    def __init__(self) -> None:
        self._connections: dict[str, _Connection] = {}

    async def connect(self, websocket: WebSocket, client_id: str) -> None:
        await websocket.accept()
        self._connections[client_id] = _Connection(client_id, websocket)

    def disconnect(self, client_id: str) -> None:
        self._connections.pop(client_id, None)

    async def send_personal_message(self, client_id: str, payload: Any) -> None:
        connection = self._connections.get(client_id)
        if connection is not None:
            await connection.websocket.send_json(payload)


manager = ConnectionManager()


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
        device = security.verify_token(token)
        if device is None:
            await websocket.close(code=4401)
            return
        websocket.state.device = device
    _owner, client_id = security.websocket_owner(websocket)
    await manager.connect(websocket, client_id)
    try:
        while True:
            payload = build_stats_payload(websocket.app)
            payload["client_id"] = client_id
            await manager.send_personal_message(client_id, payload)
            await asyncio.sleep(PUSH_INTERVAL_SECONDS)
    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception:  # beklenmedik kopma — uygulama düşmemeli
        manager.disconnect(client_id)
        try:
            await websocket.close()
        except Exception:
            pass
