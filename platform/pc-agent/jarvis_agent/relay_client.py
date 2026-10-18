"""Agent → Relay outbound istemcisi (Faz 2).

PC'den dışarıya doğru kalıcı WebSocket; router'da port açılmasına gerek
yoktur (gereksinim 2.1). Relay bu kanaldan hatırlatıcı komutlarını ve
WoL denemelerini iletir. Agent'ın yayınladığı hatırlatıcı olayları da
relay'e yansıtılır (telefon bildirimleri için).

Ayarlar (.env):
    JARVIS_RELAY_URL=wss://relay.example.com/agent-channel
    JARVIS_RELAY_TOKEN=<paylaşımlı token>
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import urllib.parse
from typing import Any, Callable, Optional

import httpx

logger = logging.getLogger("jarvis.relay.client")

RECONNECT_SECONDS = 5.0
COMMAND_TYPES = {"reminder.create", "reminder.cancel", "reminder.ack", "wake_pc"}


class RelayClient:
    """Outbound WS istemcisi; hata durumunda sessizce yeniden bağlanır."""

    def __init__(self, url: str, token: str, handler: Callable[[dict], Any],
                 event_sink: Optional[Callable[[dict], None]] = None) -> None:
        self._url = url.rstrip("/")
        self._token = token
        self._handler = handler          # relay komutlarını çalıştırır (thread'de)
        self._event_sink = event_sink    # agent olaylarını relay'e yazar
        self._ws: Any = None
        self._connected = asyncio.Event()
        self._stopping = False
        self._task: Optional[asyncio.Task] = None

    # ------------------------------------------------------------- lifecycle
    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stopping = False
            self._connected.clear()
            self._task = asyncio.get_running_loop().create_task(self._run())

    async def stop(self) -> None:
        self._stopping = True
        self._connected.set()
        if self._ws is not None:
            with contextlib.suppress(Exception):
                await self._ws.close()
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        self._task = None

    @property
    def connected(self) -> bool:
        return self._connected.is_set() and not self._stopping

    def status(self) -> dict[str, Any]:
        host = urllib.parse.urlparse(self._url).netloc
        return {
            "configured": bool(self._url),
            "connected": self.connected,
            "relay": host or None,
        }

    # ------------------------------------------------------------ event push
    def publish(self, message: dict) -> None:
        """Agent olayını relay'e iletir (bağlantı yoksa sessizce düşer)."""
        if not self.connected or self._ws is None:
            return
        try:
            asyncio.get_running_loop().create_task(self._ws.send(json.dumps(message)))
        except RuntimeError:
            pass

    # -------------------------------------------------------------- main loop
    async def _run(self) -> None:
        import websockets

        target = self._url
        connect_options = {
            "open_timeout": 10,
            "additional_headers": (
                {"Authorization": f"Bearer {self._token}"}
                if self._token else {}
            ),
        }
        while not self._stopping:
            try:
                async with websockets.connect(target, **connect_options) as ws:
                    self._ws = ws
                    self._connected.set()
                    logger.info("Relay bağlandı: %s", self._url)
                    async for raw in ws:
                        try:
                            msg = json.loads(raw)
                        except (TypeError, ValueError):
                            continue
                        if isinstance(msg, dict) and msg.get("type") in COMMAND_TYPES:
                            reply = await asyncio.to_thread(self._safe_handle, msg)
                            if reply is not None:
                                await ws.send(json.dumps(reply))
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.debug("Relay bağlantısı koptu (%s) — %s sn sonra tekrar", exc, RECONNECT_SECONDS)
            finally:
                self._connected.clear()
                self._ws = None
            if not self._stopping:
                await asyncio.sleep(RECONNECT_SECONDS)

    def _safe_handle(self, msg: dict) -> Optional[dict]:
        try:
            result = self._handler(msg) or {}
        except Exception as exc:
            logger.warning("Relay komutu hata verdi: %s (%s)", msg.get("type"), exc)
            result = {"ok": False, "error": str(exc)}
        if isinstance(result, dict):
            return {"type": f"{msg.get('type')}.result", "ok": bool(result.get("ok", True)),
                    "data": {k: v for k, v in result.items() if k != "ok"}}
        return None



def make_relay_handler(reminders: Any, wol_cfg: dict[str, str]) -> Callable[[dict], dict]:
    """Relay komutlarını ReminderService + WoL HTTP'e bağlar (sync, thread'de çalışır)."""

    def handle(msg: dict) -> dict:
        kind = msg.get("type")
        if kind == "reminder.create":
            rem = reminders.create(str(msg.get("title") or ""), str(msg.get("target_at") or ""))
            return {"ok": True, "reminder": rem}
        if kind == "reminder.cancel":
            rid = int(msg.get("id") or 0)
            return {"ok": bool(reminders.delete(rid))}
        if kind == "reminder.ack":
            rid = int(msg.get("id") or 0)
            return {"ok": reminders.ack(rid, by="relay") is not None}
        if kind == "wake_pc":
            return wake_via_node(wol_cfg)
        return {"ok": False, "error": f"bilinmeyen komut: {kind}"}

    return handle


def wake_via_node(cfg: dict[str, str]) -> dict:
    """WoL node'a (LAN içi) magic packet komutu yollar."""
    url = (cfg.get("url") or "").strip()
    mac = (cfg.get("mac") or "").strip()
    if not url or not mac:
        return {"ok": False, "error": "WoL yapılandırılmamış (JARVIS_WOL_NODE_URL / JARVIS_TARGET_MAC)"}
    headers = {}
    if cfg.get("secret"):
        headers["Authorization"] = f"Bearer {cfg['secret']}"
    try:
        resp = httpx.post(url.rstrip("/") + "/wake", json={"mac": mac},
                          headers=headers, timeout=8.0)
    except Exception as exc:
        return {"ok": False, "error": f"node'a ulaşılamadı: {exc}"}
    if resp.status_code == 200:
        return {"ok": True, "mac": mac}
    return {"ok": False, "error": f"node HTTP {resp.status_code}"}
