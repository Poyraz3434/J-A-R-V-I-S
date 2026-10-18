"""JARVIS WoL Node — Raspberry Pi / router üzerinde çalışan magic packet servisi.

Magic packet yerel ağ yayınıdır; PC'nin bulunduğu LAN'dan gönderilmek
zorundadır (gereklim 2 ve 7). Bu mini servis, relay'in HTTP komutunu alıp
aynı LAN'da UDP broadcast ile magic packet yollar.

Çalıştırma (Pi üzerinde):
    pip install -r requirements.txt
    JARVIS_WOL_SECRET=<güçlü-secret> python main.py
"""
from __future__ import annotations

import os
import re
import socket
import struct

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

SECRET = os.getenv("JARVIS_WOL_SECRET", "").strip()
BIND_PORT = int(os.getenv("JARVIS_WOL_PORT", "8080"))
if not SECRET:
    raise RuntimeError("JARVIS_WOL_SECRET yapılandırılmadan WoL node başlatılamaz.")

app = FastAPI(title="JARVIS WoL Node", version="1.0.0")

_MAC_RE = re.compile(r"^([0-9A-Fa-f]{2}[:\-]){5}[0-9A-Fa-f]{2}$")


def _require_secret(authorization: str | None) -> None:
    if not SECRET:
        raise HTTPException(status_code=503, detail="WoL secret yapılandırılmamış.")
    if SECRET and authorization != f"Bearer {SECRET}":
        raise HTTPException(status_code=401, detail="Geçersiz secret.")


class WakeRequest(BaseModel):
    mac: str
    port: int = 9  # standart WoL portu; bazı kartlar 7 veya 9 ister


def send_magic_packet(mac: str, port: int = 9, broadcast: str = "255.255.255.255") -> int:
    """Verilen MAC'e magic packet yollar; gönderilen bayt sayısını döner."""
    if not _MAC_RE.match(mac):
        raise HTTPException(status_code=422, detail="Geçersiz MAC adresi.")
    if port not in (7, 9):
        raise HTTPException(status_code=422, detail="WoL portu yalnızca 7 veya 9 olabilir.")
    mac_clean = mac.replace(":", "").replace("-", "")
    packet = bytes.fromhex("FF" * 6 + mac_clean * 16)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        return sock.sendto(packet, (broadcast, port))


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "secret_required": bool(SECRET)}


@app.post("/wake")
def wake(payload: WakeRequest, authorization: str | None = Header(default=None)) -> dict:
    _require_secret(authorization)
    sent = send_magic_packet(payload.mac, payload.port)
    return {"mac": payload.mac, "bytes_sent": sent}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=BIND_PORT)
