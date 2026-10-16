"""Faz 2/4 — Agent'ın relay'e kalıcı outbound bağlantısı.

Router'da port açılmaz: agent, relay'e DIŞARI DOĞRU WebSocket açar ve
komutları bu kanaldan alır (mimari gereksinim 2). JARVIS_RELAY_URL boşsa
bu modül hiç kullanılmaz; uygulama tamamen yerel çalışır.

Komut akışı (relay → agent):
    reminder.create / reminder.ack / reminder.cancel / ping

Olay akışı (agent → relay):
    hello, reminder.fired / reminder.acked / reminder.expired
"""
from __future__ import annotations

import asyncio
import json
import logging
import urllib.parse
from typing import Any, Callable, Optional

logger = logging.getLogger("jarvis.relay.client")

RECONNECT_MIN = 3.0
RECONNECT_MAX = 60.0


def build_ws_url(base: str, token: str = "", endpoint: str = "/agent-channel") -> str:
    """Relay taban adresini WS adresine çevirir.

    http(s) ön ekini ws(s)'e dönüştürür; token varsa query'ye ekler.
    """
    base = (base or "").strip().rstrip("/")
    if base.startswith("https://"):
        base = "wss://" + base[len("https://"):]
    elif base.startswith("http://"):
        base = "ws://" + base[len("http://"):]
    url = base + endpoint
    if token:
        url += ("&" if "?" in url else "?") + "token=" + urllib.parse.quote(token)
    return url


class RelayClient:
    """Yeniden bağlanmalı outbound WS istemcisi (üstel geri çekme 3→60 sn).

    Komutlar ``on_command`` işleyicisine (senkron) devredilir; işleyici
    worker thread'inde çağrılır (SQLite çağrıları event loop'u bloklamasın).
    """

    def __init__(
        self,
        base_url: str,
        token: str = "",
        *,
        on_command: Optional[Callable[[dict], Optional[dict]]] = None,
    ) -> None:
        self._url = build_ws_url(base_url, token)
        self._on_command = on_command
        self._queue: "asyncio.Queue[dict]" = asyncio.Queue(maxsize=200)
        self._task: Optional[asyncio.Task] = None
        self._stop = asyncio.Event()
        self.connected = False

    # ── Yaşam döngüsü ────────────────────────────────────────────────────────
    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stop.clear()
            self._task = asyncio.get_running_loop().create_task(self.run())

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            except Exception:  # pragma: no cover — kapanışta sessiz
                pass
            self._task = None
        self.connected = False

    # ── Gönderim (fire-and-forget) ──────────────────────────────────────────
    def publish(self, message: dict) -> None:
        try:
            self._queue.put_nowait(message)
        except asyncio.QueueFull:
            logger.warning("relay kuyruğu dolu — mesaj atıldı: %s", message.get("type"))

    # ── Ana döngü ───────────────────────────────────────────────────────────
    async def run(self) -> None:
        from websockets.asyncio.client import connect

        delay = RECONNECT_MIN
        while not self._stop.is_set():
            try:
                async with connect(self._url, open_timeout=8) as ws:
                    logger.info("Relay bağlandı: %s", self._url.split("?")[0])
                    self.connected = True
                    delay = RECONNECT_MIN
                    await self._session(ws)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Relay bağlantısı kurulamadı: %s", exc)
            finally:
                self.connected = False
            if self._stop.is_set():
                break
            await asyncio.sleep(delay)
            delay = min(delay * 1.6, RECONNECT_MAX)

    async def _session(self, ws: Any) -> None:
        sender = asyncio.create_task(self._sender(ws))
        receiver = asyncio.create_task(self._receiver(ws))
        await self._stop.wait()  # stop() istenene kadar iki görev de yaşar
        sender.cancel()
        receiver.cancel()

    async def _sender(self, ws: Any) -> None:
        await ws.send(json.dumps({"type": "hello", "client": "pc-agent"}))
        while True:
            message = await self._queue.get()
            await ws.send(json.dumps(message))

    async def _receiver(self, ws: Any) -> None:
        loop = asyncio.get_running_loop()
        async for raw in ws:
            try:
                message = json.loads(raw)
            except (TypeError, ValueError):
                continue
            if not isinstance(message, dict):
                continue
            if message.get("type") == "ping":
                self.publish({"type": "pong"})
                continue
            if self._on_command is None:
                continue
            try:
                reply = await loop.run_in_executor(None, self._on_command, message)
            except Exception:
                logger.exception("relay komutu işlenemedi: %s", message.get("type"))
                continue
            if reply:
                self.publish(reply)