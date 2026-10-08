"""Persistent user preferences and profile data."""
from __future__ import annotations

import datetime
from copy import deepcopy

from config import PROFILE_FILE, SETTINGS_FILE, safe_read_json, safe_write_json
from logger_setup import logger

DEFAULT_SETTINGS = {
    "voice_gender": "male",
    "font_size": 13,
    "tts_enabled": True,
    "wake_word": True,
    "night_mode_auto": True,
    "tts_speed": "+0%",
    "finance_voice_pro": True,
    "briefing_auto": True,
    "atlas_auto_open": True,
    "show_filters": True,
    "response_depth": "balanced",
    "low_bandwidth_mode": True,
    "low_resource_mode": None,
}


def settings_load() -> dict:
    settings = dict(DEFAULT_SETTINGS)
    saved = safe_read_json(SETTINGS_FILE, {})
    if isinstance(saved, dict):
        settings.update(saved)
    return settings


def settings_save(settings: dict) -> None:
    safe_write_json(SETTINGS_FILE, settings)


class LongMemory:
    """Persist user preferences, favorite items, and session summaries."""

    _defaults = {
        "name": "Efendim",
        "favorite_stocks": [],
        "favorite_currencies": ["USD", "EUR", "GBP"],
        "interests": [],
        "session_summaries": [],
        "total_sessions": 0,
        "first_seen": None,
        "last_seen": None,
        "custom_notes": {},
        "preferred_tone": "casual",
    }

    def __init__(self):
        self._data = dict(self._defaults)
        self._load()

    def _load(self):
        saved = safe_read_json(PROFILE_FILE, {})
        if isinstance(saved, dict):
            self._data.update(saved)
        if not self._data["first_seen"]:
            self._data["first_seen"] = datetime.datetime.now().isoformat()
        self._data["last_seen"] = datetime.datetime.now().isoformat()
        self._data["total_sessions"] = self._data.get("total_sessions", 0) + 1
        try:
            self._save()
        except Exception:
            logger.exception("[Profile] Oturum başında profil güncellenemedi")

    def _save(self):
        try:
            safe_write_json(PROFILE_FILE, self._data)
        except Exception:
            logger.exception("[Profile] Kullanıcı profili kaydedilemedi")
            raise

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        previous = deepcopy(self._data)
        self._data[key] = value
        try:
            self._save()
        except Exception:
            self._data = previous
            raise

    def replace_data(self, data: dict) -> None:
        previous = self._data
        updated = dict(self._defaults)
        updated.update(data)
        self._data = updated
        try:
            self._save()
        except Exception:
            self._data = previous
            raise

    def snapshot(self) -> dict:
        return deepcopy(self._data)

    def add_favorite_stock(self, ticker: str):
        stocks = list(self._data.get("favorite_stocks", []))
        ticker = ticker.upper()
        if ticker not in stocks:
            stocks.append(ticker)
            self.set("favorite_stocks", stocks)
            return True
        return False

    def remove_favorite_stock(self, ticker: str):
        stocks = list(self._data.get("favorite_stocks", []))
        ticker = ticker.upper()
        if ticker in stocks:
            stocks.remove(ticker)
            self.set("favorite_stocks", stocks)
            return True
        return False

    def add_session_summary(self, summary: str):
        summaries = list(self._data.get("session_summaries", []))
        summaries.insert(0, {
            "date": datetime.datetime.now().strftime("%d.%m.%Y %H:%M"),
            "summary": summary[:300],
        })
        self.set("session_summaries", summaries[:10])

    def get_context_string(self) -> str:
        parts = []
        name = self._data.get("name", "Efendim")
        if name != "Efendim":
            parts.append(f"Kullanıcının adı: {name}")
        favorite_stocks = self._data.get("favorite_stocks", [])
        if favorite_stocks:
            parts.append(f"Favori hisseler: {', '.join(favorite_stocks)}")
        favorite_currencies = self._data.get("favorite_currencies", [])
        if favorite_currencies:
            parts.append(
                f"İlgilendiği para birimleri: {', '.join(favorite_currencies)}"
            )
        tone = self._data.get("preferred_tone", "casual")
        parts.append(
            f"Konuşma tarzı tercihi: {'resmi' if tone == 'formal' else 'samimi'}"
        )
        return "\n".join(parts)

    def save_note(self, key: str, value: str):
        notes = dict(self._data.get("custom_notes", {}))
        notes[key] = value
        self.set("custom_notes", notes)

    def get_note(self, key: str) -> str | None:
        return self._data.get("custom_notes", {}).get(key)

    def list_notes(self) -> dict:
        return dict(self._data.get("custom_notes", {}))

    def delete_note(self, key: str) -> bool:
        notes = dict(self._data.get("custom_notes", {}))
        if key not in notes:
            return False
        del notes[key]
        self.set("custom_notes", notes)
        return True
