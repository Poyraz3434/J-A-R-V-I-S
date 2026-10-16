"""FastAPI uygulama fabrikası — tüm uçların bağlandığı yer.

Statik Web UI (platform/web/dist) mevcutsa aynen sunulur; yoksa yalnızca
API çalışır (arayüz geliştirilirken `npm run dev` + Vite proxy kullanılır).
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .relay_client import RelayClient, wake_via_node
from .api import (
    routes_camera,
    routes_chat,
    routes_conversation,
    routes_pair,
    routes_settings,
    routes_system,
    routes_voice,
)
from . import security
from .api import routes_files
from .api import routes_reminders
from .api import ws as ws_module
from .camera.service import CameraService
from .core import counters
from .core.stats import StatsMonitor
from .llm import build_provider
from .reminders.service import SERVICE as REMINDER_SERVICE
from .store import database
from .voice.service import VoiceService

logger = logging.getLogger("jarvis.app")


def _relay_command_handler(message: dict) -> Optional[dict]:
    """Relay'den gelen komutu yerel ReminderService'e uygular (worker thread)."""
    from .reminders import service as reminder_module

    kind = message.get("type")
    try:
        if kind == "reminder.create":
            due = reminder_module.parse_iso(str(message.get("target_at") or ""))
            if due is None:
                return {"type": "reminder.error", "error": "target_at geçersiz"}
            row = REMINDER_SERVICE.create(str(message.get("title") or "").strip()[:200], due)
            return {"type": "reminder.created", "reminder": row}
        if kind == "reminder.cancel":
            ok = REMINDER_SERVICE.delete(int(message.get("id") or 0))
            return {"type": "reminder.deleted", "id": message.get("id"), "ok": ok}
        if kind == "reminder.ack":
            row = REMINDER_SERVICE.ack(int(message.get("id") or 0), by="relay")
            return {"type": "reminder.acked", "id": message.get("id"), "ok": row is not None}
        if kind == "wake_pc":
            from .relay_client import wake_via_node

            cfg = {
                "url": config.env("JARVIS_WOL_NODE_URL", ""),
                "secret": config.env("JARVIS_WOL_NODE_SECRET", ""),
                "mac": config.env("JARVIS_TARGET_MAC", ""),
            }
            database.audit("wol.wake_requested", detail=cfg.get("mac") or "")
            return wake_via_node(cfg)
    except (TypeError, ValueError) as exc:
        return {"type": "reminder.error", "error": str(exc)}
    return None


def _make_announcer(voice: VoiceService, relay_client: Optional[Any]) -> Any:
    """Hatırlatıcı olaylarını TTS + audit + relay'e yayan kapama döndürür.

    Announcer, tick worker thread'inden çağrılır; ``voice.speak`` çağıran
    thread'i TTS bitene kadar bloklar — bu yüzden async döngüde değil,
    to_thread worker'ında çalışması güvenlidir.
    """

    def announce(message: dict) -> None:
        event = str(message.get("event") or "")
        payload = message.get("payload") or {}
        reminder = payload.get("reminder") or {}
        title = str(reminder.get("title") or "").strip()
        if event == "fired" and title:
            database.audit("reminder.fired", detail=title)
            try:
                voice.speak(f"Hatırlatma: {title}")
            except Exception:
                logger.exception("hatırlatıcı TTS başarısız")
        if relay_client is not None and event in ("fired", "acked", "expired"):
            relay_client.publish({"type": f"reminder.{event}", "reminder": reminder})

    return announce


def create_app() -> FastAPI:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )

    database.init_db()

    app = FastAPI(
        title="JARVIS PC Agent",
        version=config.APP_VERSION,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )

    # Dev modunda Vite (5173) bu CORS'a ihtiyaç duyar; üretimde aynı origin.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=False,
    )

    # ── Cihaz güvenliği (Faz 2): loopback dışı istekler eşleşmiş cihazdan
    #    geçerli X-Device-Token ile gelmek zorunda (pairing şartsa).
    security.init(config.DB_PATH)
    if security.required():

        @app.middleware("http")
        async def _device_guard(request: Request, call_next):
            path = request.url.path
            public = path == "/api/health" or path.startswith("/api/pair/")
            host = request.client.host if request.client else ""
            if not public and not security.is_loopback(host):
                device = security.verify_token(request.headers.get("x-device-token", ""))
                if device is None:
                    return JSONResponse(
                        {"detail": "Eşleşmemiş cihaz — QR ile eşleştirin."},
                        status_code=401,
                    )
                request.state.device = device
            return await call_next(request)

    # ── Uygulama durumu (bağımlılık enjeksiyonu yerine basit state) ──
    app.state.started_at = time.time()
    app.state.stats = StatsMonitor()
    app.state.camera = CameraService()
    app.state.llm = build_provider()
    app.state.voice = VoiceService(app.state.llm, app.state.stats)

    # Relay (Faz 2): JARVIS_RELAY_URL tanımlıysa outbound kanal açılır.
    wol_cfg = {
        "url": config.env("JARVIS_WOL_NODE_URL", ""),
        "secret": config.env("JARVIS_WOL_NODE_SECRET", ""),
        "mac": config.env("JARVIS_TARGET_MAC", ""),
    }
    app.state.wol_cfg = wol_cfg
    relay_url = config.env("JARVIS_RELAY_URL", "")
    relay_client = RelayClient(
        relay_url,
        config.env("JARVIS_RELAY_TOKEN", ""),
        _relay_command_handler,
    ) if relay_url else None
    app.state.relay = relay_client
    # Hatırlatıcı olayları → TTS + WS + relay (announcer bağlantısı).
    REMINDER_SERVICE.announcer = _make_announcer(app.state.voice, relay_client)
    app.state.reminders = REMINDER_SERVICE

    app.include_router(routes_system.router)
    app.include_router(routes_chat.router)
    app.include_router(routes_settings.router)
    app.include_router(routes_conversation.router)
    app.include_router(routes_camera.router)
    app.include_router(routes_voice.router)
    app.include_router(routes_reminders.router)
    app.include_router(routes_files.router)
    app.include_router(routes_pair.router)
    app.include_router(ws_module.router)

    @app.on_event("startup")
    async def _startup() -> None:
        import asyncio

        app.state.stats.start()
        # Ses servisi TTS/sohbet için ana event loop'a bağlanır (Faz 3).
        app.state.voice.bind_loop(asyncio.get_running_loop())
        if app.state.relay is not None:
            app.state.relay.start()
            logger.info("Relay kanalı açılıyor: %s", config.env("JARVIS_RELAY_URL", ""))
        sessions = counters.bump_session_count()
        database.audit("agent.start", detail=f"oturum #{sessions}")
        provider = app.state.llm
        logger.info(
            "JARVIS Agent v%s başladı — LLM: %s (%s)",
            config.APP_VERSION,
            provider.name,
            provider.model,
        )
        # Mikrofon varsayılan olarak KAPALI başlar (gizlilik: kullanıcı eylemi
        # şart). Otomatik wake dinleme istenirse .env: JARVIS_VOICE_AUTOSTART=1
        if config.env("JARVIS_VOICE_AUTOSTART") == "1":
            app.state.voice.start()
            logger.info("Ses servisi otomatik başlatıldı (JARVIS_VOICE_AUTOSTART=1)")

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        if app.state.relay is not None:
            await app.state.relay.stop()
        app.state.voice.stop()
        app.state.camera.close()
        app.state.stats.stop()
        database.audit("agent.stop")
        logger.info("JARVIS Agent durduruldu")

    # ── Statik Web UI (varsa) ──
    dist = config.WEB_DIST_DIR
    if (dist / "index.html").is_file():
        app.mount("/assets", StaticFiles(directory=str(dist / "assets")), name="assets")

        @app.get("/", include_in_schema=False)
        async def serve_index() -> FileResponse:
            return FileResponse(str(dist / "index.html"))

        @app.get("/{path:path}", include_in_schema=False)
        async def serve_spa(path: str):
            # API öneki altındaki bilinmeyen yollar SPA'ya düşmemeli:
            if path == "api" or path.startswith("api/"):
                return JSONResponse({"detail": "Not Found"}, status_code=404)
            # Path traversal koruması: yalnızca dist içindeki dosyalar sunulur.
            candidate = (dist / path).resolve()
            if not candidate.is_relative_to(dist.resolve()):
                return JSONResponse({"detail": "Not Found"}, status_code=404)
            if candidate.is_file():
                return FileResponse(str(candidate))
            # SPA fallback: dosya yoksa index.html (Faz 2'de QR vb. rotalar için)
            return FileResponse(str(dist / "index.html"))
    else:
        @app.get("/", include_in_schema=False)
        async def api_only_notice() -> JSONResponse:
            return JSONResponse(
                {
                    "name": "JARVIS PC Agent",
                    "version": config.APP_VERSION,
                    "note": (
                        "Web UI derlenmemiş. platform/web altında `npm install && "
                        "npm run build` çalıştırın veya geliştirme için "
                        "`npm run dev` kullanın."
                    ),
                    "docs": "/api/docs",
                }
            )

    return app
