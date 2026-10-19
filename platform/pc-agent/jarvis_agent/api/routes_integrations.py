"""Harici entegrasyon durumları ve güvenli bağlantı kontrolleri."""
from __future__ import annotations

from fastapi import APIRouter, Request

from .. import config
from ..integrations import google_home, home, mail, whatsapp

router = APIRouter()


def _status(configured: bool, *, reachable: bool | None = None,
            detail: str | None = None) -> dict:
    result = {"configured": configured}
    if reachable is not None:
        result["reachable"] = reachable
    if detail:
        result["detail"] = detail
    return result


def build_integrations_payload(request: Request) -> dict:
    relay = getattr(request.app.state, "relay", None)
    wol = getattr(request.app.state, "wol_cfg", {}) or {}
    provider = getattr(request.app.state, "llm", None)
    return {
        "llm": _status(
            provider is not None and provider.name != "mock",
            detail=provider.name if provider else "none",
        ),
        "weather": _status(bool(config.OWM_API_KEY)),
        "whatsapp": _status(
            whatsapp.available(),
            detail="outbound disabled" if not config.env("JARVIS_ALLOW_OUTBOUND_MESSAGES") == "1" else None,
        ),
        "smtp": _status(
            mail.send_available(),
            detail="outbound disabled" if not config.env("JARVIS_ALLOW_OUTBOUND_MESSAGES") == "1" else None,
        ),
        "imap": _status(mail.available()),
        "home_assistant": _status(home.available()),
        "google_home": _status(google_home.configured()),
        "relay": relay.status() if relay is not None else _status(False, reachable=False),
        "wol": _status(bool(wol.get("url") and wol.get("mac"))),
    }


@router.get("/api/integrations")
def integrations(request: Request) -> dict:
    """Anahtarları açığa çıkarmadan entegrasyonların konfigürasyon durumunu döndürür."""
    return {"integrations": build_integrations_payload(request)}


@router.get("/api/integrations/whatsapp")
def whatsapp_status() -> dict:
    return _status(whatsapp.available())


@router.get("/api/integrations/email")
def email_status() -> dict:
    return {
        "smtp": _status(mail.send_available()),
        "imap": _status(mail.available()),
    }


@router.get("/api/integrations/home-assistant")
def home_assistant_status() -> dict:
    return _status(home.available())


@router.get("/api/integrations/google-home")
def google_home_status(request: Request) -> dict:
    return google_home.status(str(request.headers.get("x-client-id") or "local"))


@router.get("/api/integrations/relay")
def relay_status(request: Request) -> dict:
    relay = getattr(request.app.state, "relay", None)
    return relay.status() if relay is not None else _status(False, reachable=False)
