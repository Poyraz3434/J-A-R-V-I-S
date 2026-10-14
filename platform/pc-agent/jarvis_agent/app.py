"""FastAPI uygulama fabrikası — tüm uçların bağlandığı yer.

Statik Web UI (platform/web/dist) mevcutsa aynen sunulur; yoksa yalnızca
API çalışır (arayüz geliştirilirken `npm run dev` + Vite proxy kullanılır).
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .api import (
    routes_camera,
    routes_chat,
    routes_conversation,
    routes_settings,
    routes_system,
    routes_voice,
)
from .api import routes_reminders
from .api import ws as ws_module
from .camera.service import CameraService
from .core import counters
from .core.stats import StatsMonitor
from .llm import build_provider
from .store import database
from .voice.service import VoiceService

logger = logging.getLogger("jarvis.app")


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

    # ── Uygulama durumu (bağımlılık enjeksiyonu yerine basit state) ──
    app.state.started_at = time.time()
    app.state.stats = StatsMonitor()
    app.state.camera = CameraService()
    app.state.llm = build_provider()
    app.state.voice = VoiceService(app.state.llm, app.state.stats)

    app.include_router(routes_system.router)
    app.include_router(routes_chat.router)
    app.include_router(routes_settings.router)
    app.include_router(routes_conversation.router)
    app.include_router(routes_camera.router)
    app.include_router(routes_voice.router)
    app.include_router(routes_reminders.router)
    app.include_router(ws_module.router)

    @app.on_event("startup")
    async def _startup() -> None:
        import asyncio

        app.state.stats.start()
        # Ses servisi TTS/sohbet için ana event loop'a bağlanır (Faz 3).
        app.state.voice.bind_loop(asyncio.get_running_loop())
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
