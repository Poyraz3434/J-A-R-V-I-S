"""Ortak WhatsApp gönderim adaptörü.

CallMeBot yapılandırılmışsa hafif HTTP gönderimi kullanılır; aksi halde
masaüstü uygulaması için mevcut pywhatkit fallback'i korunur.
"""
from __future__ import annotations

import datetime
import os
import re
import urllib.parse
import urllib.request
from typing import Any


_CALLMEBOT_API = "https://api.callmebot.com/whatsapp.php"


def _settings() -> tuple[str, str]:
    return (
        os.getenv("JARVIS_WA_PHONE", "").strip(),
        os.getenv("JARVIS_WA_APIKEY", "").strip(),
    )


def callmebot_available() -> bool:
    phone, key = _settings()
    return bool(phone and key and key != "change-me")


def available() -> bool:
    return callmebot_available()


def send_message(phone: str, message: str) -> dict[str, Any]:
    """Mesaj gönderir; sonucu ortak, güvenli bir sözlükte döndürür."""
    safe_phone = re.sub(r"[^0-9+]", "", str(phone or ""))
    safe_message = str(message or "").strip()[:500]
    if not safe_phone or len(safe_phone) < 10:
        return {"ok": False, "error": "Geçersiz telefon numarası."}

    _configured_phone, api_key = _settings()
    if api_key and api_key != "change-me":
        try:
            query = urllib.parse.urlencode(
                {"phone": safe_phone, "text": safe_message, "apikey": api_key}
            )
            request = urllib.request.Request(f"{_CALLMEBOT_API}?{query}")
            with urllib.request.urlopen(request, timeout=15.0) as response:
                status = response.status
                body = response.read(4096).decode("utf-8", errors="replace").strip().lower()
            if status == 200 and "queued" in body:
                return {"ok": True, "provider": "callmebot", "to": safe_phone}
            if status == 429:
                return {"ok": False, "error": "CallMeBot günlük kotası doldu."}
            return {"ok": False, "error": f"CallMeBot HTTP {status}"}
        except Exception as exc:
            return {"ok": False, "error": f"CallMeBot gönderimi başarısız: {exc}"}

    try:
        import pywhatkit as kit
    except ImportError:
        return {"ok": False, "error": "WhatsApp yapılandırılmamış; CallMeBot veya pywhatkit gerekli."}

    try:
        now = datetime.datetime.now()
        minute = now.minute + 2
        hour, minute = now.hour + minute // 60, minute % 60
        kit.sendwhatmsg(safe_phone, safe_message, hour % 24, minute, wait_time=15, tab_close=True)
        return {"ok": True, "provider": "pywhatkit", "to": safe_phone, "scheduled": f"{hour % 24:02d}:{minute:02d}"}
    except Exception as exc:
        return {"ok": False, "error": f"WhatsApp gönderimi başarısız: {exc}"}
