"""Google Home Device Access (SDM) integration."""
from __future__ import annotations

import base64
import hashlib
import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from typing import Any
from urllib.parse import urlencode

import httpx

from .. import config
from ..store import database

_TOKEN_URL = "https://oauth2.googleapis.com/token"
_SDM_BASE = "https://smartdevicemanagement.googleapis.com/v1"
_SCOPES = "https://www.googleapis.com/auth/sdm.service"
_TIMEOUT = 10.0
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="google-home")
_refresh_lock = threading.Lock()


def configured() -> bool:
    return all((config.GOOGLE_HOME_CLIENT_ID, config.GOOGLE_HOME_CLIENT_SECRET,
                config.GOOGLE_HOME_PROJECT_ID, config.GOOGLE_HOME_TOKEN_KEY))


def _fernet():
    try:
        from cryptography.fernet import Fernet
    except ImportError as exc:
        raise RuntimeError("cryptography paketi gerekli") from exc
    raw = config.GOOGLE_HOME_TOKEN_KEY.encode("utf-8")
    key = raw if len(raw) == 44 else base64.urlsafe_b64encode(hashlib.sha256(raw).digest())
    return Fernet(key)


def _encrypt(value: dict[str, Any]) -> str:
    import json
    return _fernet().encrypt(json.dumps(value).encode("utf-8")).decode("ascii")


def _decrypt(value: str) -> dict[str, Any]:
    import json
    return json.loads(_fernet().decrypt(value.encode("ascii")).decode("utf-8"))


def status(owner_id: str) -> dict[str, Any]:
    if not configured():
        return {"configured": False, "connected": False, "reason": "oauth_not_configured"}
    return {"configured": True, "connected": database.get_google_home_token(owner_id or "local") is not None}


def authorization_url(owner_id: str, state_store: dict[str, dict[str, Any]]) -> str:
    if not configured():
        raise RuntimeError("Google Home OAuth yapılandırılmamış")
    state = secrets.token_urlsafe(32)
    state_store[state] = {"owner_id": owner_id or "local", "expires_at": time.time() + 600}
    query = urlencode({
        "client_id": config.GOOGLE_HOME_CLIENT_ID,
        "redirect_uri": config.GOOGLE_HOME_REDIRECT_URI,
        "response_type": "code",
        "scope": _SCOPES,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    })
    return f"https://accounts.google.com/o/oauth2/v2/auth?{query}"


def complete_oauth(code: str, state: str, state_store: dict[str, dict[str, Any]]) -> str:
    item = state_store.pop(state, None)
    if not item or float(item["expires_at"]) < time.time():
        raise ValueError("OAuth state geçersiz veya süresi dolmuş")
    response = httpx.post(_TOKEN_URL, data={
        "code": code, "client_id": config.GOOGLE_HOME_CLIENT_ID,
        "client_secret": config.GOOGLE_HOME_CLIENT_SECRET,
        "redirect_uri": config.GOOGLE_HOME_REDIRECT_URI,
        "grant_type": "authorization_code",
    }, timeout=_TIMEOUT)
    response.raise_for_status()
    token = response.json()
    if not token.get("refresh_token"):
        raise ValueError("Google refresh token döndürmedi; yeniden izin verin")
    token["expires_at"] = time.time() + int(token.get("expires_in", 3600))
    database.save_google_home_token(str(item["owner_id"]), _encrypt(token))
    return str(item["owner_id"])


def disconnect(owner_id: str) -> None:
    database.delete_google_home_token(owner_id or "local")


def _access_token(owner_id: str) -> str:
    owner_id = owner_id or "local"
    encrypted = database.get_google_home_token(owner_id)
    if not encrypted:
        raise RuntimeError("Google Home hesabı bağlı değil")
    token = _decrypt(encrypted)
    if float(token.get("expires_at", 0)) > time.time() + 60:
        return str(token["access_token"])
    with _refresh_lock:
        token = _decrypt(database.get_google_home_token(owner_id) or "")
        if float(token.get("expires_at", 0)) <= time.time() + 60:
            response = httpx.post(_TOKEN_URL, data={
                "client_id": config.GOOGLE_HOME_CLIENT_ID,
                "client_secret": config.GOOGLE_HOME_CLIENT_SECRET,
                "refresh_token": token["refresh_token"],
                "grant_type": "refresh_token",
            }, timeout=_TIMEOUT)
            response.raise_for_status()
            refreshed = response.json()
            token.update(refreshed)
            token["expires_at"] = time.time() + int(refreshed.get("expires_in", 3600))
            database.save_google_home_token(owner_id, _encrypt(token))
    return str(token["access_token"])


def _request(owner_id: str, method: str, path: str, **kwargs: Any) -> httpx.Response:
    response = httpx.request(method, f"{_SDM_BASE}{path}",
                             headers={"Authorization": f"Bearer {_access_token(owner_id)}"},
                             timeout=_TIMEOUT, **kwargs)
    if response.status_code == 401:
        database.delete_google_home_token(owner_id or "local")
    response.raise_for_status()
    return response


def list_devices(owner_id: str) -> dict[str, Any]:
    response = _request(owner_id, "GET", f"/enterprises/{config.GOOGLE_HOME_PROJECT_ID}/devices")
    grouped: dict[str, list[dict[str, Any]]] = {}
    for raw in response.json().get("devices", []):
        device = _normalize_device(raw)
        grouped.setdefault(device["room"], []).append(device)
    return {"devices": grouped, "total": sum(map(len, grouped.values()))}


def _normalize_device(raw: dict[str, Any]) -> dict[str, Any]:
    traits = raw.get("traits", {})
    relations = raw.get("parentRelations") or [{}]
    relation = relations[0]
    state: dict[str, Any] = {}
    for values in traits.values():
        if isinstance(values, dict):
            state.update(values)
    return {
        "id": str(raw.get("name", "")),
        "name": relation.get("displayName") or str(raw.get("name", "")).rsplit("/", 1)[-1],
        "room": relation.get("displayName") or "Diğer",
        "type": next(iter(traits), "Device").rsplit(".", 1)[-1],
        "traits": list(traits),
        "state": state,
        "online": traits.get("sdm.devices.traits.Connectivity", {}).get("connectivityState") == "ONLINE",
    }


def command(owner_id: str, device_id: str, action: str, value: float | None = None) -> dict[str, Any]:
    known_ids = {
        device["id"]
        for devices in list_devices(owner_id)["devices"].values()
        for device in devices
    }
    if device_id not in known_ids:
        raise ValueError("Cihaz bu Google Home hesabına ait değil")
    commands: dict[str, tuple[str, dict[str, Any]]] = {
        "on": ("sdm.devices.commands.OnOff.SetOn", {}),
        "off": ("sdm.devices.commands.OnOff.SetOff", {}),
    }
    if action == "brightness":
        if value is None or not 0 <= value <= 100:
            raise ValueError("Parlaklık 0-100 arasında olmalı")
        commands[action] = ("sdm.devices.commands.Brightness.SetBrightness", {"brightness": value})
    if action == "temperature":
        if value is None or not 7 <= value <= 35:
            raise ValueError("Sıcaklık 7-35 arasında olmalı")
        commands[action] = ("sdm.devices.commands.ThermostatTemperatureSetpoint.SetHeat",
                            {"heatCelsius": value})
    if action not in commands:
        raise ValueError("Desteklenmeyen cihaz komutu")
    future = _executor.submit(_request, owner_id, "POST", f"/{device_id}:executeCommand",
                              json={"command": commands[action][0], "params": commands[action][1]})
    try:
        future.result(timeout=_TIMEOUT + 2)
    except TimeoutError as exc:
        future.cancel()
        raise TimeoutError("Google Home komutu zaman aşımına uğradı") from exc
    return {"ok": True, "device_id": device_id, "action": action}
