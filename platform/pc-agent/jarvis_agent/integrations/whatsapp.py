"""WhatsApp entegrasyonu (Faz 7).

Kişisel kullanım için resmi WhatsApp Business API hem pahalı hem kurulumu
zordur; bot kullanımı WhatsApp koşullarına aykırıdır. Bu yüzden popüler,
ücretsiz ve kişisel kullanıma uygun **CallMeBot** köprüsünü kullanıyoruz:
tek yönlü mesaj gönderme (PC → kullanıcının telefonu).

Kurulum (tek seferlik, 2 dakika):
    1. Telefona +34 644 51 95 23 numarasını kaydet
    2. "I allow callmebot to send me messages" yazıp o numaraya gönder
    3. Gelen API anahtarını .env'e yaz:
       JARVIS_WA_PHONE=+905xxxxxxxxx
       JARVIS_WA_APIKEY=123456
"""
from __future__ import annotations

import logging
import os
import urllib.parse
from typing import Any

import httpx

logger = logging.getLogger("jarvis.integrations.whatsapp")

_TIMEOUT = 15.0
_API = "https://api.callmebot.com/whatsapp.php"


def _settings() -> tuple[str, str]:
    return (os.getenv("JARVIS_WA_PHONE", ""), os.getenv("JARVIS_WA_APIKEY", ""))


def available() -> bool:
    phone, key = _settings()
    return bool(phone and key and key != "change-me")


def send_message(text: str) -> dict[str, Any]:
    """Kısa bir mesajı kullanıcının WhatsApp'ına gönderir."""
    phone, key = _settings()
    if not available():
        return {"error": "WhatsApp yapılandırılmamış"}

    try:
        resp = httpx.get(
            _API,
            params={"phone": phone, "text": text, "apikey": key},
            timeout=_TIMEOUT,
            follow_redirects=True,
        )
    except Exception as exc:
        logger.warning("WhatsApp gönderimi başarısız: %s", exc)
        return {"error": f"gönderim başarısız: {exc}"}

    body = resp.text.strip().lower()
    if resp.status_code == 200 and "queued" in body:
        return {"sent": True, "to": phone, "text": text}
    if resp.status_code == 429:
        return {"error": "günlük CallMeBot sınırı aşıldı (kota dolu)"}
    logger.info("CallMeBot beklenmeyen yanıt: HTTP %s %s", resp.status_code, resp.text[:120])
    return {
        "error": f"servis yanıtı beklenmeyen (HTTP {resp.status_code})",
        "hint": "telefona CallMeBot kurulum adımlarını tamamlandığını doğrulayın",
    }