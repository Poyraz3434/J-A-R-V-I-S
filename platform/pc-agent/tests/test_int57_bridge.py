"""INT57 (Faz 5-6-7) entegrasyon köprüsü sözleşme testleri — hermetik, ağ yok."""
from __future__ import annotations

import asyncio
import json

from jarvis_agent.llm import int57_bridge as ib


def _run(coro):
    return asyncio.run(coro)


def teardown_function():
    ib.inject_bindings({})
    ib._cache.clear()


def test_specs_gecerli_ve_tekil():
    names = [s["function"]["name"] for s in ib.INT57_SPECS]
    assert len(names) == len(set(names)) == 8
    for s in ib.INT57_SPECS:
        assert s["type"] == "function"
        assert s["function"]["description"]
        assert s["function"]["parameters"]["type"] == "object"


def test_bilinmeyen_arac_hata_dondurur():
    out = _run(ib.execute_int57_tool("boyle_bir_arac_yok", {}))
    data = json.loads(out)
    assert data["ok"] is False and "unknown" in data["error"]


def test_cozumlenemeyen_arac_zarif_doner():
    out = _run(ib.execute_int57_tool("get_ai_news", {}))
    data = json.loads(out)
    assert isinstance(data.get("ok"), bool)  # True (bulundu) ya da False (yapılandırılmamış)


def test_enjekte_edilen_async_cagri():
    seen = {}

    async def fake_send(**kw):
        seen.update(kw)
        return {"ok": True, "sent": kw.get("to")}

    ib.inject_bindings({"send_email": fake_send})
    out = _run(ib.execute_int57_tool(
        "send_email", {"to": "a@b.c", "subject": "s", "body": "b", "hack": 1}))
    data = json.loads(out)
    assert data["ok"] is True and data["sent"] == "a@b.c"
    # imzaya-toleranslı filtreleme: tanımsız parametre gitmez
    assert seen == {"to": "a@b.c", "subject": "s", "body": "b"}


def test_enjekte_edilen_sync_sonuc_sarmalanir():
    ib.inject_bindings({"send_whatsapp_message": lambda message: f"gitti:{message}"})
    out = _run(ib.execute_int57_tool("send_whatsapp_message", {"message": "selam"}))
    data = json.loads(out)
    assert data == {"ok": True, "data": "gitti:selam"}


def test_hata_sizdirmez():
    def patla(path):
        raise RuntimeError("pat")

    ib.inject_bindings({"send_file": patla})
    out = _run(ib.execute_int57_tool("send_file", {"path": "x"}))
    data = json.loads(out)
    assert data["ok"] is False and "pat" in data["error"]


def test_kopru_kurulumu_idempotent():
    from jarvis_agent.llm import tools as core

    assert ib.install_int57_bridge(vars(core)) is True
    say = len(core.TOOL_SPECS)
    assert ib.install_int57_bridge(vars(core)) is True
    assert len(core.TOOL_SPECS) == say  # çift eklenmedi
    names = {s["function"]["name"] for s in core.TOOL_SPECS}
    assert set(ib.INT57_NAMES) <= names
    assert getattr(core.execute_tool, "_int57_wrapped", False) is True


def test_kopru_dispatch_uzerinden():
    from jarvis_agent.llm import tools as core

    ib.install_int57_bridge(vars(core))
    ib.inject_bindings({"send_whatsapp_message": lambda message: f"ok:{message}"})
    out = _run(core.execute_tool("send_whatsapp_message", {"message": "m"}))
    assert json.loads(out)["data"] == "ok:m"


def test_resolutions_sekli():
    r = ib.resolutions()
    assert set(r) == set(ib.INT57_NAMES)
