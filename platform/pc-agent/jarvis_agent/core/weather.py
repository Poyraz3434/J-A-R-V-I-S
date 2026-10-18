"""Güncel hava durumu — OpenWeatherMap istemcisi (kısa önbellekli)."""
from __future__ import annotations

import datetime
import logging
import threading
import time
from typing import Any, Optional

import httpx

from .. import config

logger = logging.getLogger("jarvis.weather")

_CACHE_TTL = 600.0  # 10 dk — ücretsiz katman dostu
_lock = threading.Lock()
_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def _now_iso() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def _unavailable(reason: str) -> dict[str, Any]:
    return {"available": False, "reason": reason, "fetched_at": _now_iso()}


def get(city: Optional[str] = None, force: bool = False) -> dict[str, Any]:
    """Şehir için güncel hava durumu; her hata zarif biçimde `available=False` döner."""
    city = (city or config.DEFAULT_CITY).strip()
    api_key = config.OWM_API_KEY
    if not api_key:
        return _unavailable("no_api_key")
    if not city:
        return _unavailable("no_city")

    if not force:
        with _lock:
            hit = _cache.get(city.lower())
            if hit and time.time() - hit[0] < _CACHE_TTL:
                return hit[1]

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={"q": city, "units": "metric", "lang": "tr", "appid": api_key},
            )
    except httpx.HTTPError as exc:
        logger.warning("Hava durumu isteği başarısız (%s): %s", city, exc)
        return _unavailable("network_error")

    if resp.status_code == 404:
        return _unavailable("invalid_city")
    if resp.status_code in (401, 403):
        return _unavailable("invalid_api_key")
    if resp.status_code != 200:
        logger.warning("Hava durumu HTTP %s", resp.status_code)
        return _unavailable("http_error")

    try:
        data = resp.json()
        payload = {
            "available": True,
            "city": data.get("name", city),
            "temperature": round(float(data["main"]["temp"]), 1),
            "feels_like": round(float(data["main"]["feels_like"]), 1),
            "humidity": int(data["main"]["humidity"]),
            "wind_speed": round(float(data["wind"]["speed"]), 1),
            "description": (data.get("weather") or [{}])[0].get("description", ""),
            "icon": (data.get("weather") or [{}])[0].get("icon", ""),
            "fetched_at": _now_iso(),
        }
    except (KeyError, ValueError, TypeError):
        logger.exception("Hava durumu yanıtı ayrıştırılamadı")
        return _unavailable("parse_error")

    with _lock:
        _cache[city.lower()] = (time.time(), payload)
    return payload
