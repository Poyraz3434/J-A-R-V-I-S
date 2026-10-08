"""Opt-in release checks; downloaded files are never installed or executed."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from urllib.parse import urlparse

from config import APP_VERSION
from services.network import DEFAULT_HTTP_TIMEOUT, HTTP_SESSION

_VERSION_RE = re.compile(r"^v?(\d+(?:\.\d+){1,3})$")


@dataclass(frozen=True)
class UpdateInfo:
    latest_version: str
    release_url: str
    update_available: bool | None
    release_notes: str = ""


def _version_tuple(value: str) -> tuple[int, ...] | None:
    match = _VERSION_RE.fullmatch(str(value or "").strip())
    if not match:
        return None
    parts = tuple(int(part) for part in match.group(1).split("."))
    return parts + (0,) * (4 - len(parts))


def is_update_check_configured() -> bool:
    """JARVIS_UPDATE_URL ayarlıysa True döner (otomatik denetim buna bakar)."""
    return bool(os.getenv("JARVIS_UPDATE_URL", "").strip())


def check_for_update(
    manifest_url: str | None = None,
    current_version: str | None = None,
) -> UpdateInfo:
    """Read a GitHub-compatible release manifest over HTTPS without auto-updating."""
    url = (manifest_url or os.getenv("JARVIS_UPDATE_URL", "")).strip()
    if not url:
        raise ValueError(
            "Güncelleme kaynağı ayarlı değil. JARVIS_UPDATE_URL için HTTPS "
            "GitHub 'latest release' API adresi yapılandırılmalı."
        )
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Güncelleme adresi geçerli bir HTTPS URL olmalı.")

    response = HTTP_SESSION.get(url, timeout=DEFAULT_HTTP_TIMEOUT)
    response.raise_for_status()
    manifest = response.json()
    if not isinstance(manifest, dict):
        raise ValueError("Güncelleme yanıtı JSON nesnesi değil.")
    version = str(manifest.get("tag_name", "")).strip()
    if not version or _version_tuple(version) is None:
        raise ValueError("Güncelleme yanıtında geçerli bir sürüm etiketi yok.")
    release_url = str(manifest.get("html_url", "")).strip()
    release_parsed = urlparse(release_url)
    if release_parsed.scheme != "https" or not release_parsed.hostname:
        raise ValueError("Yayın sayfası HTTPS URL değil.")

    # JARVIS_VERSION tanımsızsa paketle gelen APP_VERSION ile karşılaştır;
    # böylece 'güncel mi?' sorusu ayar olmadan da yanıtlanabilir.
    current = current_version or os.getenv("JARVIS_VERSION", "") or APP_VERSION
    latest_tuple = _version_tuple(version)
    current_tuple = _version_tuple(current)
    available = (
        latest_tuple > current_tuple if current_tuple is not None else None
    )
    notes = str(manifest.get("body", "")).strip()[:4000]
    return UpdateInfo(version, release_url, available, notes)
