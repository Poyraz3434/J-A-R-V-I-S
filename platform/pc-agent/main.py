"""JARVIS PC Agent — giriş noktası.

Çalıştırma:
    python main.py            # http://127.0.0.1:8000
    python main.py --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import argparse
import logging

import uvicorn

from jarvis_agent import config
from jarvis_agent.app import create_app

logger = logging.getLogger("jarvis.main")


def main() -> None:
    parser = argparse.ArgumentParser(description="JARVIS PC Agent")
    parser.add_argument("--host", default=config.BIND_HOST)
    parser.add_argument("--port", type=int, default=config.BIND_PORT)
    args = parser.parse_args()

    app = create_app()

    logger.info(
        "Agent %s:%s adresinde başlıyor (Web UI: %s)",
        args.host,
        args.port,
        "hazır" if (config.WEB_DIST_DIR / "index.html").is_file() else "derlenmemiş",
    )
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level="info",
        # Tek süreç: reload ile çoklu DB bağlantısı/process karmaşası olmasın.
    )


if __name__ == "__main__":
    main()
