"""Özellik 4 — IP + makine kimliğine dayalı kalıcı tercih saklama.

Tercihler birincil anahtar olarak yerel IP adresiyle (kullanıcı gereksinimi),
yedek anahtar olarak sabit makine kimliğiyle saklanır; çünkü IP dinamik olabilir
(ağ değişikliği, DHCP). Okuma sırası: IP girişi → makine girişi → default.
"""
from __future__ import annotations

import hashlib
import logging
import platform
import uuid

logger = logging.getLogger(__name__)

_ip_cache: str | None = None


def get_local_ip() -> str:
    """Yerel LAN IPv4 adresi (paket göndermeden; hata → '0.0.0.0')."""
    global _ip_cache
    if _ip_cache:
        return _ip_cache
    import socket
    ip = "0.0.0.0"
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.connect(("8.8.8.8", 80))  # UDP connect veri göndermez
            ip = sock.getsockname()[0]
        finally:
            sock.close()
    except OSError:
        try:
            ip = socket.gethostbyname(socket.gethostname())
        except OSError:
            ip = "0.0.0.0"
    _ip_cache = ip
    return ip


def get_machine_id() -> str:
    """Cihaz başına sabit kimlik (hostname + MAC/node özeti; IP'den bağımsız)."""
    raw = f"{platform.node()}|{uuid.getnode()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def save_device_pref(settings: dict, key: str, value) -> None:
    """Tercihi hem mevcut IP hem de makine kimliği altında sakla (dict'e yazar).

    Not: kalıcı dosyaya yazmak çağıranın işidir (örn. ``settings_save``),
    böylece işlev saf kalır ve test edilebilir.
    """
    ip = get_local_ip()
    mid = get_machine_id()
    prefs = settings.get("device_prefs")
    if not isinstance(prefs, dict):
        prefs = settings["device_prefs"] = {}
    for storage_key in (ip, f"machine:{mid}"):
        entry = prefs.get(storage_key)
        if not isinstance(entry, dict):
            entry = prefs[storage_key] = {}
        entry["machine_id"] = mid
        entry[key] = value
    logger.debug("[DevicePrefs] %s=%r kaydedildi (ip=%s)", key, value, ip)


def load_device_pref(settings: dict, key: str, default=None):
    """Tercihi oku: IP girişi → makine girişi → default."""
    prefs = settings.get("device_prefs")
    if isinstance(prefs, dict):
        mid = get_machine_id()
        for storage_key in (get_local_ip(), f"machine:{mid}"):
            entry = prefs.get(storage_key)
            if isinstance(entry, dict) and key in entry:
                return entry[key]
    return default
