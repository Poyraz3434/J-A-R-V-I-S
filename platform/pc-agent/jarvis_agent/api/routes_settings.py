"""Ayarlar uçları — kullanıcıya özel tema/şehir/dil/panel konumu (Bölüm A).

Kurallar:
- Her istek ``request.state.owner`` etiketiyle gelir (app.py middleware);
  ayarlar bu etikete göre user_settings tablosunda izole tutulur.
- Misafirler (owner 'guest:*') ayar GÖRÜR ama kalıcı yazamaz (madde 6).
- Tema değerleri config.ALLOWED_BG_COLORS ile sınırlıdır (madde 4: bordo dahil).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from .. import config
from ..store import database

router = APIRouter()


class SettingsUpdate(BaseModel):
    """Kısmi ayar güncellemesi; yalnızca gönderilen alanlar değişir."""

    background_color: str | None = None
    city: str | None = None
    language: str | None = None
    chat_position: str | None = None


@router.get("/api/settings")
def get_settings(request: Request) -> dict:
    owner = getattr(request.state, "owner", "local")
    row = database.get_user_settings(owner)
    theme = row["theme"] if row["theme"] in config.ALLOWED_BG_COLORS else config.DEFAULT_BG_COLOR
    language = row["language"] if row["language"] in config.ALLOWED_LANGUAGES else config.DEFAULT_LANGUAGE
    position = (
        row["chat_position"]
        if row["chat_position"] in config.ALLOWED_CHAT_POSITIONS
        else config.DEFAULT_CHAT_POSITION
    )
    return {
        "background_color": theme,
        "city": row["city"],
        "language": language,
        "chat_position": position,
        # "guest" test sözleşmesi; owner_is_guest geriye dönük uyumluluk için.
        "guest": database.is_guest(owner),
        "owner_is_guest": database.is_guest(owner),
        "allowed_background_colors": list(config.ALLOWED_BG_COLORS),
        "allowed_languages": list(config.ALLOWED_LANGUAGES),
        "allowed_chat_positions": list(config.ALLOWED_CHAT_POSITIONS),
    }


@router.put("/api/settings")
def update_settings(request: Request, payload: SettingsUpdate) -> dict:
    owner = getattr(request.state, "owner", "local")
    if database.is_guest(owner):
        # Madde 6/16: misafir oturumda kalıcı ayar yazma yok (401: kimlik gerekir).
        raise HTTPException(
            status_code=401, detail="Misafir oturumda ayarlar kalıcı olarak değiştirilemez."
        )

    patch: dict[str, str] = {}
    if payload.background_color is not None:
        if payload.background_color not in config.ALLOWED_BG_COLORS:
            raise HTTPException(status_code=422, detail="Geçersiz arka plan rengi.")
        patch["theme"] = payload.background_color
    if payload.language is not None:
        if payload.language not in config.ALLOWED_LANGUAGES:
            raise HTTPException(status_code=422, detail="Geçersiz dil.")
        patch["language"] = payload.language
    if payload.chat_position is not None:
        if payload.chat_position not in config.ALLOWED_CHAT_POSITIONS:
            raise HTTPException(status_code=422, detail="Geçersiz panel konumu.")
        patch["chat_position"] = payload.chat_position
    if payload.city is not None:
        city = payload.city.strip()
        if not (1 <= len(city) <= 64):
            raise HTTPException(
                status_code=422, detail="Şehir adı 1-64 karakter olmalı."
            )
        patch["city"] = city

    if patch:
        database.update_user_settings(owner, patch)
        database.audit(
            "settings.update",
            actor=owner,
            detail=",".join(f"{k}={v}" for k, v in sorted(patch.items()))[:200],
        )
    return get_settings(request)
