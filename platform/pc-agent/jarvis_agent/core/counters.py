"""Oturum ve komut sayaçları."""
from __future__ import annotations

import logging
from pathlib import Path

from .. import config
from ..store import database

logger = logging.getLogger("jarvis.counters")


def _read_sessions() -> int:
    path = Path(config.SESSIONS_FILE)
    try:
        return int(path.read_text(encoding="utf-8").strip() or "0")
    except (OSError, ValueError):
        return 0


def bump_session_count() -> int:
    """Agent her başladığında çağrılır; toplam oturum sayısını artırır."""
    value = _read_sessions() + 1
    try:
        path = Path(config.SESSIONS_FILE)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(value), encoding="utf-8")
    except OSError:
        logger.warning("Oturum sayacı yazılamadı: %s", config.SESSIONS_FILE)
    return value


def get_session_count() -> int:
    return _read_sessions()


def bump_command_count() -> int:
    """Kullanıcı komut sayacını (DB'de) artırır."""
    return database.increment_setting_int("command_count")


def get_command_count() -> int:
    try:
        return int(database.get_setting("command_count", "0") or "0")
    except ValueError:
        return 0
