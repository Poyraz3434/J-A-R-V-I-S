"""JARVIS Relay Sunucusu — hatırlatıcıların kalıcı evi (Faz 4).

Bulutta (veya her zaman açık bir makinede) çalışır. PC kapalıyken de
zamanlayıcı burada çalışır (gereklim 5.5). Agent PC'den OUTBOUND WebSocket
ile bağlanır; relay PC'ye asla doğrudan bağlanmaz (router portu açılmaz).

Kimlik doğrulama: paylaşımlı token (JARVIS_RELAY_TOKEN). Üretimde TLS
için nginx/Caddy gibi bir reverse proxy önerilir (README'ye bakın).
"""
from __future__ import annotations

import asyncio
import datetime
import logging
import os
import uuid
from contextlib import closing
from pathlib import Path
from typing import Any, Optional

import httpx
import sqlite3
from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)-7s %(name)s: %(message)s"
)
logger = logging.getLogger("jarvis.relay")

DATA_DIR = Path(os.getenv("JARVIS_RELAY_DATA", Path.home() / ".jarvis-relay"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "relay.db"

RELAY_TOKEN = os.getenv("JARVIS_RELAY_TOKEN", "").strip()
if not RELAY_TOKEN:
    raise RuntimeError("JARVIS_RELAY_TOKEN yapılandırılmadan relay başlatılamaz.")
PRE_NOTIFY_MINUTES = 30          # hedefden 30 dk önce ön bildirim
TICK_SECONDS = 10.0              # zamanlayıcı adımı
REPEAT_MINUTES = 2               # ack edilmeyen alarm tekrar aralığı (5.5)
MAX_REPEATS = 60                 # 2 dk × 60 = ~2 saat sonra otomatik susma
WOL_URL = os.getenv("JARVIS_WOL_NODE_URL", "").strip()   # http://pi:8080
WOL_SECRET = os.getenv("JARVIS_WOL_NODE_SECRET", "").strip()
WOL_MAC = os.getenv("JARVIS_TARGET_MAC", "").strip()     # PC'nin MAC adresi

_schema = """
CREATE TABLE IF NOT EXISTS reminders (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    target_at TEXT NOT NULL,
    pre_notified INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'agent',
    fired_at TEXT,
    repeats INTEGER NOT NULL DEFAULT 0,
    last_repeat_at TEXT
);
"""


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _iso(dt: datetime.datetime) -> str:
    return dt.astimezone(datetime.timezone.utc).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    with closing(connect()) as conn, conn:
        conn.executescript(_schema)


def _require_token(authorization: Optional[str]) -> None:
    if not RELAY_TOKEN:
        raise HTTPException(status_code=503, detail="Relay secret yapılandırılmamış.")
    if authorization != f"Bearer {RELAY_TOKEN}":
        raise HTTPException(status_code=401, detail="Geçersiz token.")


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


# ── CRUD ─────────────────────────────────────────────────────────────────────

def create_reminder(title: str, target_at: datetime.datetime, source: str = "agent") -> dict:
    rid = uuid.uuid4().hex[:12]
    with closing(connect()) as conn, conn:
        conn.execute(
            "INSERT INTO reminders (id, title, target_at, created_at, source) "
            "VALUES (?, ?, ?, ?, ?)",
            (rid, title, _iso(target_at), _iso(_utcnow()), source),
        )
    return {"id": rid, "title": title, "target_at": _iso(target_at)}


def list_reminders(include_done: bool = False) -> list[dict]:
    query = "SELECT * FROM reminders"
    if not include_done:
        query += " WHERE status = 'pending'"
    query += " ORDER BY target_at ASC"
    with closing(connect()) as conn:
        rows = conn.execute(query).fetchall()
    return [row_to_dict(r) for r in rows]


def get_reminder(rid: str) -> Optional[dict]:
    with closing(connect()) as conn:
        row = conn.execute("SELECT * FROM reminders WHERE id = ?", (rid,)).fetchone()
    return row_to_dict(row) if row else None


def update_reminder(rid: str, **fields: Any) -> bool:
    if not fields:
        return False
    sets = ", ".join(f"{k} = ?" for k in fields)
    with closing(connect()) as conn, conn:
        cur = conn.execute(
            f"UPDATE reminders SET {sets} WHERE id = ?", (*fields.values(), rid)
        )
    return bool(cur.rowcount)


def delete_reminder(rid: str) -> bool:
    with closing(connect()) as conn, conn:
        cur = conn.execute("DELETE FROM reminders WHERE id = ?", (rid,))
    return bool(cur.rowcount)


def ack_reminder(rid: str) -> bool:
    with closing(connect()) as conn, conn:
        cur = conn.execute(
            "UPDATE reminders SET status = 'acked' WHERE id = ? AND status != 'acked'",
            (rid,),
        )
    return bool(cur.rowcount)


# ── Agent kanalı: bağlı agent + teslim edilemeyen eventler ────────────────────

class AgentHub:
    """Agent bağlantılarını ve offline event kuyruğunu yönetir."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._sockets: list[WebSocket] = []
        self._pending: list[dict] = []   # agent offline iken biriken eventler

    async def register(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._sockets.append(ws)
        logger.info("Agent kanalı açıldı (toplam %d)", len(self._sockets))
        if self._pending:
            backlog = self._pending
            self._pending = []
            for event in backlog:
                await self._safe_send(ws, event)

    async def unregister(self, ws: WebSocket) -> None:
        async with self._lock:
            if ws in self._sockets:
                self._sockets.remove(ws)
        logger.info("Agent kanalı kapandı (kalan %d)", len(self._sockets))

    @property
    def has_agent(self) -> bool:
        return bool(self._sockets)

    async def _safe_send(self, ws: WebSocket, event: dict) -> None:
        try:
            await ws.send_json(event)
        except Exception:
            await self.unregister(ws)

    async def push(self, event: dict, queue_if_offline: bool = True) -> None:
        """Event'i bağlı agentlara iter; hiçbiri yoksa kuyruğa alır."""
        async with self._lock:
            sockets = list(self._sockets)
            if not sockets:
                if queue_if_offline:
                    self._pending.append(event)
                    if len(self._pending) > 200:
                        self._pending = self._pending[-200:]
                return
            for ws in sockets:
                await self._safe_send(ws, event)


hub = AgentHub()


async def try_wake_pc() -> None:
    """PC kapalıysa: WoL node'a magic packet komutu gönderir (5.5)."""
    if not (WOL_URL and WOL_MAC):
        logger.info("WoL yapılandırılmamış — uzaktan uyandırma atlandı")
        return
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(
                f"{WOL_URL}/wake",
                json={"mac": WOL_MAC},
                headers={"Authorization": f"Bearer {WOL_SECRET}"} if WOL_SECRET else {},
            )
        logger.info("WoL komutu gönderildi: HTTP %s", resp.status_code)
    except httpx.HTTPError as exc:
        logger.warning("WoL node'a ulaşılamadı: %s", exc)


def list_active_reminders() -> list[dict]:
    """Bekleyen + çalmış (ack edilmemiş) hatırlatıcılar — zamanlayıcı bunları işler."""
    with closing(connect()) as conn:
        rows = conn.execute(
            "SELECT * FROM reminders WHERE status IN ('pending', 'fired') "
            "ORDER BY target_at ASC"
        ).fetchall()
    return [row_to_dict(r) for r in rows]


def _parse_iso(value: str) -> datetime.datetime:
    dt = datetime.datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt


async def scheduler_tick() -> None:
    """Zamanlayıcı adımı: ön bildirimler, asıl alarmlar ve tekrarlar (5.5 akışı)."""
    now = _utcnow()
    for rem in list_active_reminders():
        target = _parse_iso(rem["target_at"])

        # 1) Ön bildirim: hedefden 30 dk önce, bir kez
        if rem["status"] == "pending" and not rem["pre_notified"]:
            pre_at = target - datetime.timedelta(minutes=PRE_NOTIFY_MINUTES)
            if now >= pre_at:
                update_reminder(rem["id"], pre_notified=1)
                local_time = target.astimezone().strftime("%H:%M")
                await hub.push(
                    {
                        "type": "reminder.pre",
                        "id": rem["id"],
                        "title": rem["title"],
                        "target_at": rem["target_at"],
                        "message": f"{local_time} alarmınıza {PRE_NOTIFY_MINUTES} dakika kaldı.",
                    }
                )
                continue

        # 2) Asıl alarm: tam zamanında (bir kez)
        if rem["status"] == "pending" and now >= target:
            update_reminder(rem["id"], status="fired", fired_at=_iso(now), repeats=1,
                            last_repeat_at=_iso(now))
            await hub.push(
                {
                    "type": "reminder.fired",
                    "id": rem["id"],
                    "title": rem["title"],
                    "target_at": rem["target_at"],
                    "message": f"Kurulan alarm: {rem['title']}",
                    "repeat": 1,
                }
            )
            # Agent bağlı değilse PC'yi uyandırmayı dene; event kuyruğa alındı.
            if not hub.has_agent:
                await try_wake_pc()
            continue

        # 3) Tekrar: kullanıcı yanıt verene dek (5.5). Kapalı PC'de de sürer;
        #    kuyruk taşmasın diye tekrarlar yalnızca agent bağlıyken iletilir.
        if rem["status"] == "fired":
            last = _parse_iso(rem["last_repeat_at"] or rem["fired_at"] or _iso(now))
            if now >= last + datetime.timedelta(minutes=REPEAT_MINUTES):
                if rem["repeats"] >= MAX_REPEATS:
                    update_reminder(rem["id"], status="expired")
                    await hub.push(
                        {"type": "reminder.expired", "id": rem["id"], "title": rem["title"]}
                    )
                    continue
                update_reminder(rem["id"], repeats=rem["repeats"] + 1, last_repeat_at=_iso(now))
                await hub.push(
                    {
                        "type": "reminder.repeat",
                        "id": rem["id"],
                        "title": rem["title"],
                        "message": f"Kurulan alarm (tekrar {rem['repeats'] + 1}): {rem['title']}",
                        "repeat": rem["repeats"] + 1,
                    }
                )


async def scheduler_loop() -> None:
    logger.info("Zamanlayıcı başladı (%s sn adım)", TICK_SECONDS)
    while True:
        try:
            await scheduler_tick()
        except Exception:
            logger.exception("Zamanlayıcı adımı başarısız")
        await asyncio.sleep(TICK_SECONDS)


# ── FastAPI uygulaması ────────────────────────────────────────────────────────

app = FastAPI(title="JARVIS Relay", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip().rstrip("/")
        for origin in os.getenv("JARVIS_RELAY_CORS_ORIGINS", "").split(",")
        if origin.strip()
    ],
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


class ReminderCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    target_at: str = Field(min_length=8, max_length=40)  # ISO 8601 (tz bilgili)


@app.on_event("startup")
async def _startup() -> None:
    init_db()
    asyncio.get_running_loop().create_task(scheduler_loop())
    logger.info("JARVIS Relay hazır — token koruması: AÇIK")


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "agent_connected": hub.has_agent,
        "pending_events": len(hub._pending),
        "wol_configured": bool(WOL_URL and WOL_MAC),
    }


@app.get("/api/reminders")
def api_list(authorization: Optional[str] = Header(default=None), all: bool = False) -> dict:
    _require_token(authorization)
    return {"reminders": list_reminders(include_done=all)}


@app.post("/api/reminders")
def api_create(payload: ReminderCreate, authorization: Optional[str] = Header(default=None)) -> dict:
    _require_token(authorization)
    try:
        target = _parse_iso(payload.target_at)
    except ValueError:
        raise HTTPException(status_code=422, detail="target_at ISO 8601 olmalı.")
    if target <= _utcnow():
        raise HTTPException(status_code=422, detail="Hedef zaman geçmişte olamaz.")
    rem = create_reminder(payload.title.strip(), target)
    return {"created": rem}


@app.delete("/api/reminders/{rid}")
def api_delete(rid: str, authorization: Optional[str] = Header(default=None)) -> dict:
    _require_token(authorization)
    if not delete_reminder(rid):
        raise HTTPException(status_code=404, detail="Hatırlatıcı bulunamadı.")
    return {"deleted": rid}


@app.post("/api/reminders/{rid}/ack")
async def api_ack(rid: str, authorization: Optional[str] = Header(default=None)) -> dict:
    _require_token(authorization)
    if not ack_reminder(rid):
        raise HTTPException(status_code=404, detail="Hatırlatıcı bulunamadı.")
    await hub.push({"type": "reminder.acked", "id": rid})
    return {"acked": rid}


@app.websocket("/agent-channel")
async def agent_channel(ws: WebSocket) -> None:
    """Agent'ın outbound bağlantısı (router'da port açmaya gerek yok)."""
    if RELAY_TOKEN:
        authorization = ws.headers.get("authorization", "")
        token = authorization.removeprefix("Bearer ").strip()
        if token != RELAY_TOKEN:
            await ws.close(code=4401)
            return
    await hub.register(ws)
    try:
        while True:
            msg = await ws.receive_json()
            await _handle_agent_message(msg)
    except WebSocketDisconnect:
        pass
    finally:
        await hub.unregister(ws)

async def _handle_agent_message(msg: dict) -> None:
    """Agent'tan gelen senkron mesajlarını işler."""
    kind = msg.get("type")
    if kind == "reminder.create":
        try:
            target = _parse_iso(str(msg.get("target_at", "")))
            rem = create_reminder(str(msg.get("title", ""))[:200], target, source="agent")
            await hub.push({"type": "reminder.created", **rem})
        except ValueError:
            logger.warning("Agent'tan geçersiz hatırlatıcı: %s", msg)
    elif kind == "reminder.cancel":
        delete_reminder(str(msg.get("id", "")))
    elif kind == "reminder.ack":
        ack_reminder(str(msg.get("id", "")))
    elif kind == "ping":
        pass  # bağlantı diri tutma





if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("JARVIS_RELAY_PORT", "8001")))
