"""Faz 5-6-7 entegrasyon araç köprüsü (INT57).

LLM'e mail/haber/dosya/akıllı ev/WhatsApp/e-posta araçlarını açar:
- ``install_int57_bridge(ns)``: ``TOOL_SPECS``'e araç tanımlarını ekler ve
  ``execute_tool``'u sarmalar (idempotent; tekrar çağrı güvenli).
- ``execute_int57_tool(name, args)``: aracı çalıştırır, sonucu her koşulda
  ``{"ok": bool, ...}`` JSON'una sarmalar (hata LLM'e sızmaz).
- ``inject_bindings(map)``: modül dışından (app/tests) fonksiyon bağlama.
"""
from __future__ import annotations

import inspect
import json
from typing import Any, Callable, Optional

# Bir aracın "yapılandırılmış" sayılması için modül fonksiyonu yeterli;
# send_file gibi kullanıcı onaylı işlemler bağlama (binding) ile açılır.
INT57_BINDINGS: dict[str, Callable[..., Any]] = {}

# Bağlam önbelleği (örn. haber başlıklarının kısa süreli saklanması).
# teardown/testler bu alanı temizleyebilir.
_cache: dict[str, Any] = {}

INT57_NAMES: tuple[str, ...] = (
    "check_email",
    "get_ai_news",
    "list_shared_files",
    "send_file",
    "smart_home_devices",
    "smart_home_control",
    "send_whatsapp_message",
    "send_email",
)


def _spec(name: str, description: str, properties: Optional[dict] = None,
          required: Optional[list[str]] = None) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties or {},
                "required": required or [],
            },
        },
    }


INT57_SPECS: list[dict[str, Any]] = [
    _spec(
        "check_email",
        "Gelen kutusundaki okunmamış son e-postaları listeler (salt okunur).",
    ),
    _spec(
        "get_ai_news",
        "Yapay zeka ve teknoloji haber başlıklarını RSS kaynaklarından getirir.",
        {"limit": {"type": "integer", "description": "Kaç başlık (1-20, varsayılan 8)"}},
    ),
    _spec(
        "list_shared_files",
        "Telefona aktarılabilecek paylaşılan dosyaların listesini getirir.",
    ),
    _spec(
        "send_file",
        "PC'deki bir dosyayı paylaşım klasörüne ekler ve indirme adını döndürür. "
        "Yalnızca kullanıcı açıkça bir dosya paylaşımı istediyse kullan.",
        {
            "path": {"type": "string", "description": "PC'deki dosyanın tam yolu"},
            "name": {"type": "string", "description": "Paylaşımdaki görünen ad (opsiyonel)"},
        },
        ["path"],
    ),
    _spec(
        "smart_home_devices",
        "Akıllı ev cihazlarını alan adına göre (ışık, priz, termostat...) listeler.",
    ),
    _spec(
        "smart_home_control",
        "Akıllı ev cihazını açar/kapatır veya durumunu okur. Eylem: on/off/status.",
        {
            "entity_id": {"type": "string", "description": "Örn. light.saloon"},
            "action": {"type": "string", "enum": ["on", "off", "status"]},
        },
        ["entity_id", "action"],
    ),
    _spec(
        "send_whatsapp_message",
        "Kullanıcının WhatsApp'ına kısa bir mesaj gönderir (CallMeBot köprüsü).",
        {"message": {"type": "string", "description": "Gönderilecek kısa metin"}},
        ["message"],
    ),
    _spec(
        "send_email",
        "Kullanıcının e-posta hesabından düz metin e-posta gönderir.",
        {
            "to": {"type": "string", "description": "Alıcı adresi"},
            "subject": {"type": "string", "description": "Konu"},
            "body": {"type": "string", "description": "Düz metin gövde"},
        },
        ["to", "subject", "body"],
    ),
]


def inject_bindings(bindings: dict[str, Callable[..., Any]]) -> None:
    """Araç çağrılarını harici fonksiyonlara bağla (app kurulumu / testler)."""
    INT57_BINDINGS.clear()
    if bindings:
        INT57_BINDINGS.update(bindings)


def resolutions() -> dict[str, Optional[Callable[..., Any]]]:
    """Araç adı → varsayılan modül fonksiyonu (None: bağlama gerekli)."""
    from ..integrations import files, home, mail, news, whatsapp

    return {
        "check_email": mail.fetch_unread,
        "get_ai_news": news.fetch_ai_news,
        "list_shared_files": files.list_files,
        "send_file": None,  # kullanıcı onaylı → yalnızca binding ile
        "smart_home_devices": home.summarize_states,
        "smart_home_control": home.control,
        "send_whatsapp_message": whatsapp.send_message,
        "send_email": mail.send_email,
    }


def _spec_properties(name: str) -> Optional[set[str]]:
    """Aracın spec'inde bildirilen parametre adları (yoksa None)."""
    for spec in INT57_SPECS:
        if spec["function"]["name"] == name:
            return set(spec["function"]["parameters"].get("properties") or {})
    return None


def _filter_kwargs(
    name: str, func: Callable[..., Any], args: dict[str, Any]
) -> dict[str, Any]:
    """Spec'te bildirilmeyen / fonksiyonun alamayacağı argümanları at."""
    try:
        params = inspect.signature(func).parameters
    except (TypeError, ValueError):
        params = None

    declared = _spec_properties(name)
    if declared:
        allowed: Optional[set[str]] = declared  # spec dışı parametre asla gitmez
    elif params is None:
        return dict(args)
    elif any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()):
        return dict(args)
    else:
        allowed = {
            nm
            for nm, p in params.items()
            if p.kind in (
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
            )
        }
    if allowed is None:
        return dict(args)
    # Fonksiyon **kw alsa bile spec'te bildirilmeyen anahtar filtrelenir.
    if params is not None and not any(
        p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()
    ):
        sig_allowed = {
            nm
            for nm, p in params.items()
            if p.kind in (
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
            )
        }
        allowed = allowed & (sig_allowed or allowed)
    return {k: v for k, v in args.items() if k in allowed}


async def execute_int57_tool(name: str, arguments: dict[str, Any]) -> str:
    """INT57 aracını çalıştır; sonucu her durumda JSON {'ok': bool} döndür."""
    table = resolutions()
    if name not in table:
        return json.dumps({"ok": False, "error": f"unknown tool: {name}"})

    # Bağlamalar (binding) daima varsayılan çözümlemelerin önünde geçer.
    func = INT57_BINDINGS.get(name) or table.get(name)
    if func is None:
        return json.dumps(
            {"ok": False, "error": f"tool not configured: {name}",
             "hint": ".env ayarlarını tamamlayın ya da uygulama bağlamasını ekleyin"}
        )

    call_args = _filter_kwargs(name, func, dict(arguments or {}))
    try:
        result = func(**call_args)
        if inspect.isawaitable(result):
            result = await result
    except Exception as exc:  # hata asla LLM'e ham halde sızmaz
        return json.dumps(
            {"ok": False, "error": f"{type(exc).__name__}: {exc}"},
            ensure_ascii=False,
        )

    if isinstance(result, dict):
        if "ok" not in result:
            result = {"ok": not bool(result.get("error")), **result}
        return json.dumps(result, ensure_ascii=False, default=str)
    return json.dumps({"ok": True, "data": result}, ensure_ascii=False, default=str)


def install_int57_bridge(ns: dict[str, Any]) -> bool:
    """Hedef modül ad uzayına (``vars(tools)``) araçları kurar — idempotent."""
    specs = ns.get("TOOL_SPECS")
    exec_fn = ns.get("execute_tool")
    if not isinstance(specs, list) or not callable(exec_fn):
        return False

    existing = {
        s.get("function", {}).get("name")
        for s in specs
        if isinstance(s, dict)
    }
    for spec in INT57_SPECS:
        if spec["function"]["name"] not in existing:
            specs.append(spec)

    if getattr(exec_fn, "_int57_wrapped", False):
        return True

    original = exec_fn

    async def execute_tool(name, arguments, monitor=None):  # noqa: ANN001, ANN202
        if name in INT57_NAMES:
            return await execute_int57_tool(name, arguments)
        kwargs = {"name": name, "arguments": arguments}
        try:
            params = inspect.signature(original).parameters
            if "monitor" in params or any(
                p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()
            ):
                kwargs["monitor"] = monitor
        except (TypeError, ValueError):
            pass
        return await original(**kwargs)

    execute_tool._int57_wrapped = True  # type: ignore[attr-defined]
    ns["execute_tool"] = execute_tool
    return True
