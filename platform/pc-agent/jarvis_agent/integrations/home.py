"""Home Assistant entegrasyonu (Faz 6 — akıllı ev).

Kişisel kullanım için en makul seçim: Home Assistant REST API. Yerel
çalışır, onlarca protokolü (Tuya, Zigbee, WiFi prizler) tek çatı altında
toplar ve resmi token tabanlı kimlik doğrulaması vardır.

.env anahtarları:
    JARVIS_HA_URL=https://ha.example.local:8123
    JARVIS_HA_TOKEN=<uzun erişim belirteci>
"""
from __future__ import annotations

import os
from typing import Any

import httpx

_TIMEOUT = 8.0

# Bu alanları listeleme özetinde gösterelim (gerisini sessizce at).
_SHOW_DOMAINS = ("light", "switch", "climate", "cover", "fan", "media_player", "binary_sensor")


def _settings() -> tuple[str, str]:
    return (os.getenv("JARVIS_HA_URL", "").rstrip("/"), os.getenv("JARVIS_HA_TOKEN", ""))


def available() -> bool:
    url, token = _settings()
    return bool(url and token and token != "change-me")


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def summarize_states() -> dict[str, Any]:
    """Cihazları alan adına göre gruplanmış kompakt özet döndürür."""
    url, token = _settings()
    if not available():
        return {"error": "akıllı ev yapılandırılmamış"}
    try:
        resp = httpx.get(f"{url}/api/states", headers=_headers(token), timeout=_TIMEOUT)
        resp.raise_for_status()
        states = resp.json()
    except httpx.HTTPStatusError as exc:
        return {"error": f"Home Assistant hatası: HTTP {exc.response.status_code}"}
    except Exception as exc:  # bağlantı/DNS/zaman aşımı
        return {"error": f"Home Assistant'a ulaşılamadı: {exc}"}

    devices: dict[str, list[dict[str, Any]]] = {}
    for st in states:
        entity_id = st.get("entity_id", "")
        domain = entity_id.split(".")[0]
        if domain not in _SHOW_DOMAINS:
            continue
        attr = st.get("attributes", {})
        devices.setdefault(domain, []).append(
            {
                "entity_id": entity_id,
                "name": attr.get("friendly_name", entity_id),
                "state": st.get("state", ""),
                # Işıklarda sıcaklık/parlaklık gibi yararlı ek bilgi
                "detail": attr.get("temperature") or attr.get("brightness"),
            }
        )
    total = sum(len(v) for v in devices.values())
    return {"devices": devices, "total": total, "url": url}


def control(entity_id: str, action: str) -> dict[str, Any]:
    """Bir cihazı açar/kapatır veya anlık durumunu döndürür.

    Güvenlik: yalnızca 'on'/'off'/'status' eylemleri desteklenir; kilidi
    açma (lock.open) gibi hassas servisler kasıtlı olarak dışarıda.
    """
    url, token = _settings()
    if not available():
        return {"error": "akıllı ev yapılandırılmamış"}
    domain = entity_id.split(".")[0]
    if action == "status":
        return _get_state(url, token, entity_id)

    service = "turn_on" if action == "on" else "turn_off"
    try:
        resp = httpx.post(
            f"{url}/api/services/{domain}/{service}",
            headers=_headers(token),
            json={"entity_id": entity_id},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code
        if code == 404:
            return {"error": f"cihaz bulunamadı: {entity_id}", "entity_id": entity_id}
        return {"error": f"Home Assistant hatası: HTTP {code}", "entity_id": entity_id}
    except Exception as exc:
        return {"error": f"Home Assistant'a ulaşılamadı: {exc}"}

    state = _get_state(url, token, entity_id)
    return {"entity_id": entity_id, "action": action, "ok": True, "new_state": state.get("state")}


def _get_state(url: str, token: str, entity_id: str) -> dict[str, Any]:
    try:
        resp = httpx.get(f"{url}/api/states/{entity_id}", headers=_headers(token), timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        return {
            "entity_id": entity_id,
            "state": data.get("state", ""),
            "name": data.get("attributes", {}).get("friendly_name", entity_id),
        }
    except Exception as exc:
        return {"entity_id": entity_id, "error": f"durum alınamadı: {exc}"}