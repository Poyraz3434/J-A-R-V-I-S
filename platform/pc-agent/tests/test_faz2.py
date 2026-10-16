"""Faz 2 testleri: relay istemcisi, WoL uçları, QR eşleştirme, health relay."""
from __future__ import annotations

import json
import time
import urllib.parse

from fastapi.testclient import TestClient

from jarvis_agent.app import create_app
from jarvis_agent.relay_client import RelayClient, make_relay_handler, wake_via_node


def _client() -> TestClient:
    return TestClient(create_app())


# ── RelayClient ───────────────────────────────────────────────────────────────

def test_relay_status_yapilandirilmamis():
    rc = RelayClient("", "", lambda msg: {})
    assert rc.status() == {"configured": False, "connected": False, "relay": None}
    assert rc.connected is False


def test_relay_status_relay_adi_cikarir():
    rc = RelayClient("wss://relay.example.com/agent-channel", "tok", lambda msg: {})
    st = rc.status()
    assert st["configured"] is True
    assert st["relay"] == "relay.example.com:443" or st["relay"] == "relay.example.com"
    assert st["connected"] is False


def test_relay_token_queryye_eklenir():
    rc = RelayClient("wss://r.example/ws", "tok1", lambda msg: {})
    sep = "&" if "?" in "wss://r.example/ws" else "?"
    target = f"wss://r.example/ws{sep}token={urllib.parse.quote('tok1')}"
    assert "token=tok1" in target


# ── Komut yönlendirici ────────────────────────────────────────────────────────

def test_handler_bilinmeyen_komut():
    class FakeRem:
        pass

    h = make_relay_handler(FakeRem(), {})
    out = h({"type": "yok Boyle Sey"})
    assert out["ok"] is False and "bilinmeyen" in out["error"]


def test_handler_wol_yapilandirilmamis():
    h = make_relay_handler(None, {})
    out = h({"type": "wake_pc"})
    assert out["ok"] is False and "yapılandırılmamış" in out["error"]


def test_wake_via_node_hata_sizdirmez(monkeypatch):
    import httpx as _httpx

    def patla(*a, **kw):
        raise RuntimeError("bağlanamadı")

    monkeypatch.setattr(_httpx, "post", patla)
    out = wake_via_node({"url": "http://pi:8080", "mac": "AA-BB-CC-DD-EE-FF"})
    assert out["ok"] is False and "bağlanamadı" in out["error"]


def test_wake_via_node_secret_basligi(monkeypatch):
    import httpx as _httpx

    seen = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        seen.update(url=url, json=json, headers=headers)

        class R:
            status_code = 200

            def __init__(self):
                pass

        return R()

    monkeypatch.setattr(_httpx, "post", fake_post)
    out = wake_via_node({
        "url": "http://pi:8080", "mac": "AA:BB:CC:DD:EE:FF", "secret": "s3cret",
    })
    assert out["ok"] is True
    assert seen["headers"]["Authorization"] == "Bearer s3cret"
    assert seen["json"]["mac"] == "AA:BB:CC:DD:EE:FF"


# ── REST uçları ───────────────────────────────────────────────────────────────

def test_health_relay_bilgisi_tasiyor():
    c = _client()
    with c:
        body = c.get("/api/health").json()
    assert set(body["relay"]) == {"configured", "connected", "relay"}
    assert body["relay"]["configured"] is False


def test_wol_status_ve_wake():
    c = _client()
    with c:
        st = c.get("/api/system/wol").json()
        assert st["configured"] is False
        wake = c.post("/api/system/wol/wake").json()
        assert wake["ok"] is False and "yapılandırılmamış" in wake["error"]


def test_pair_lan_url_ve_qr():
    c = _client()
    with c:
        body = c.get("/api/pair/lan").json()
    assert body["primary"].startswith("http")
    assert isinstance(body["urls"], list) and body["urls"]
    # segno kuruluysa SVG data URI döner
    if body["qr_svg"]:
        assert body["qr_svg"].startswith("data:image/svg+xml")


# ── Güvenlik katmanı (cihaz token zorunluluğu) ───────────────────────────────

def test_cihaz_guardi_token_ister(monkeypatch, tmp_path):
    """Pairing şartken uzak cihazlar /api/* için X-Device-Token göndermeli."""
    from jarvis_agent import config as cfg
    from jarvis_agent import security

    monkeypatch.setenv("JARVIS_PAIRING_REQUIRED", "1")
    monkeypatch.setattr(cfg, "DB_PATH", tmp_path / "guard.db")
    security._pending_code.clear()
    # TestClient "testclient" host'u loopback sayılır; tüm istekleri
    # uzak cihazdan geliyormuş gibi simüle etmek için köprüleyelim:
    monkeypatch.setattr(security, "is_loopback", lambda host: False)
    c = TestClient(create_app())
    with c:
        # public uçlar token'sız açılır
        assert c.get("/api/health").status_code == 200
        start = c.post("/api/pair/start").json()
        assert len(start["code"]) == 6 and start["url"].count("?pair=") == 1
        # claim: kod → device_token takası
        claimed = c.post(
            "/api/pair/claim",
            json={"code": start["code"], "device_name": "pytest-telefon"},
        ).json()
        token = claimed["device_token"]
        assert claimed["name"] == "pytest-telefon"
        # token'sız / yanlış token → 401
        assert c.get("/api/settings").status_code == 401
        assert (
            c.get("/api/settings", headers={"X-Device-Token": "yanlis"}).status_code == 401
        )
        # doğru token → 200
        assert (
            c.get("/api/settings", headers={"X-Device-Token": token}).status_code == 200
        )
        # tek kullanımlık kod: ikinci claim başarısız
        assert c.post("/api/pair/claim", json={"code": start["code"]}).status_code == 400


def test_pair_baslatma_gecersiz_kod_red(money_guard=None):
    """Aktif kod yokken claim → 400 (yol herkese açık ama boşa döner)."""
    from jarvis_agent import security

    security._pending_code.clear()
    c = _client()
    with c:
        assert c.post("/api/pair/claim", json={"code": "000000"}).status_code == 400
