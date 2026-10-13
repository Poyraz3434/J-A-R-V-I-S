"""Ayarlar uçları — arka plan rengi ve şehir."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import config
from ..store import database

router = APIRouter()


class SettingsUpdate(BaseModel):
    background_color: str | None = None
    city: str | None = None


@router.get("/api/settings")
def get_settings() -> dict:
    stored = database.get_all_settings()
    bg = stored.get("background_color", config.DEFAULT_BG_COLOR)
    if bg not in config.ALLOWED_BG_COLORS:
        bg = config.DEFAULT_BG_COLOR
    return {
        "background_color": bg,
        "city": stored.get("city", config.DEFAULT_CITY),
        "allowed_background_colors": list(config.ALLOWED_BG_COLORS),
    }


@router.put("/api/settings")
def update_settings(payload: SettingsUpdate) -> dict:
    if payload.background_color is not None:
        if payload.background_color not in config.ALLOWED_BG_COLORS:
            raise HTTPException(status_code=422, detail="Geçersiz arka plan rengi.")
        database.set_setting("background_color", payload.background_color)
        database.audit(
            "settings.update", detail=f"background_color={payload.background_color}"
        )
    if payload.city is not None:
        city = payload.city.strip()
        if not (1 <= len(city) <= 64):
            raise HTTPException(
                status_code=422, detail="Şehir adı 1-64 karakter olmalı."
            )
        database.set_setting("city", city)
        database.audit("settings.update", detail=f"city={city}")
    return get_settings()
