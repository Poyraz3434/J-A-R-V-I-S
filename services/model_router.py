"""
JARVIS v10 APEX PRIME — Çoklu Model Yönlendirme Sistemi
==========================================================
Desteklenen sağlayıcılar (hepsi opsiyonel):
  • Groq      — JARVIS_GROQ_API_KEY
  • OpenAI    — JARVIS_OPENAI_API_KEY
  • Anthropic — JARVIS_ANTHROPIC_API_KEY
  • Gemini    — JARVIS_GEMINI_API_KEY
  • Ollama    — JARVIS_OLLAMA_URL (yerel, ücretsiz)

API key yoksa ilgili sağlayıcı sessizce devre dışı kalır.
Model başarısız olursa fallback zincirindeki sıradaki denenir.
"""
from __future__ import annotations

import json
import os
import time
import threading
from enum import Enum
from typing import Iterator

from logger_setup import logger

# ── Görev tipleri ──────────────────────────────────────────────────────────
class TaskType(str, Enum):
    CHAT         = "chat"         # Genel sohbet
    CODE         = "code"         # Kod yazma / analiz
    LONG_CONTEXT = "long_context" # Uzun bağlam (belgeler, PDF)
    VISION       = "vision"       # Görsel analiz


# ── Sağlayıcı durum kaydı ──────────────────────────────────────────────────
class ProviderStatus:
    def __init__(self):
        self._lock = threading.Lock()
        self._failures: dict[str, int] = {}
        self._cooldown_until: dict[str, float] = {}
        self.COOLDOWN_SEC = 60  # başarısızlık sonrası bekleme

    def record_failure(self, provider: str):
        with self._lock:
            self._failures[provider] = self._failures.get(provider, 0) + 1
            self._cooldown_until[provider] = time.time() + self.COOLDOWN_SEC
            logger.warning("[ModelRouter] %s başarısız, %d sn cooldown.", provider, self.COOLDOWN_SEC)

    def record_success(self, provider: str):
        with self._lock:
            self._failures[provider] = 0
            self._cooldown_until.pop(provider, None)

    def is_available(self, provider: str) -> bool:
        with self._lock:
            until = self._cooldown_until.get(provider, 0)
            return time.time() >= until


_provider_status = ProviderStatus()


# ── Ortak provider arayüzleri ─────────────────────────────────────────────

def _chat_groq(history: list, msg: str, system: str, model: str, stream: bool) -> str | Iterator[str]:
    """Groq (mevcut AIEngine mantığının aynen taşınmış hâli)."""
    try:
        from services.ai_client import create_groq_client
        key = os.environ.get("JARVIS_GROQ_API_KEY") or os.environ.get("GROQ_API_KEY", "")
        if not key:
            raise RuntimeError("Groq API key yok")
        client = create_groq_client(key)
        msgs = [{"role": "system", "content": system}] + history[-20:] + [{"role": "user", "content": msg}]
        if stream:
            def _gen():
                resp = client.chat.completions.create(
                    model=model, messages=msgs, max_tokens=1024, temperature=0.75, stream=True)
                for chunk in resp:
                    delta = chunk.choices[0].delta if chunk.choices else None
                    if delta and getattr(delta, "content", None):
                        yield delta.content
            return _gen()
        resp = client.chat.completions.create(
            model=model, messages=msgs, max_tokens=1024, temperature=0.75)
        return resp.choices[0].message.content
    except Exception as exc:
        raise RuntimeError(f"Groq: {exc}") from exc


def _chat_openai(history: list, msg: str, system: str, model: str, stream: bool) -> str | Iterator[str]:
    try:
        import openai
        key = os.environ.get("JARVIS_OPENAI_API_KEY", "")
        if not key:
            raise RuntimeError("OpenAI API key yok")
        client = openai.OpenAI(api_key=key)
        msgs = [{"role": "system", "content": system}] + history[-20:] + [{"role": "user", "content": msg}]
        if stream:
            def _gen():
                resp = client.chat.completions.create(
                    model=model, messages=msgs, max_tokens=1024, temperature=0.75, stream=True)
                for chunk in resp:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        yield delta.content
            return _gen()
        resp = client.chat.completions.create(
            model=model, messages=msgs, max_tokens=1024, temperature=0.75)
        return resp.choices[0].message.content
    except Exception as exc:
        raise RuntimeError(f"OpenAI: {exc}") from exc


def _chat_anthropic(history: list, msg: str, system: str, model: str, stream: bool) -> str | Iterator[str]:
    try:
        import anthropic
        key = os.environ.get("JARVIS_ANTHROPIC_API_KEY", "")
        if not key:
            raise RuntimeError("Anthropic API key yok")
        client = anthropic.Anthropic(api_key=key)
        # Anthropic system mesajı ayrı parametre
        msgs = history[-20:] + [{"role": "user", "content": msg}]
        if stream:
            def _gen():
                with client.messages.stream(
                    model=model, system=system, messages=msgs, max_tokens=1024
                ) as stream_:
                    for text in stream_.text_stream:
                        yield text
            return _gen()
        resp = client.messages.create(
            model=model, system=system, messages=msgs, max_tokens=1024)
        return resp.content[0].text
    except Exception as exc:
        raise RuntimeError(f"Anthropic: {exc}") from exc


def _chat_gemini(history: list, msg: str, system: str, model: str, stream: bool) -> str | Iterator[str]:
    try:
        import google.generativeai as genai
        key = os.environ.get("JARVIS_GEMINI_API_KEY", "")
        if not key:
            raise RuntimeError("Gemini API key yok")
        genai.configure(api_key=key)
        gmodel = genai.GenerativeModel(
            model_name=model,
            system_instruction=system
        )
        # Geçmişi Gemini formatına çevir
        gemini_history = []
        for m in history[-20:]:
            role = "user" if m["role"] == "user" else "model"
            gemini_history.append({"role": role, "parts": [m["content"]]})
        chat = gmodel.start_chat(history=gemini_history)
        if stream:
            def _gen():
                resp = chat.send_message(msg, stream=True)
                for chunk in resp:
                    if chunk.text:
                        yield chunk.text
            return _gen()
        resp = chat.send_message(msg)
        return resp.text
    except Exception as exc:
        raise RuntimeError(f"Gemini: {exc}") from exc


def _chat_ollama(history: list, msg: str, system: str, model: str, stream: bool) -> str | Iterator[str]:
    try:
        import requests
        base_url = os.environ.get("JARVIS_OLLAMA_URL", "http://localhost:11434")
        msgs = [{"role": "system", "content": system}] + history[-20:] + [{"role": "user", "content": msg}]
        payload = {"model": model, "messages": msgs, "stream": stream}
        if stream:
            def _gen():
                with requests.post(f"{base_url}/api/chat", json=payload, stream=True, timeout=60) as resp:
                    resp.raise_for_status()
                    for line in resp.iter_lines():
                        if line:
                            data = json.loads(line)
                            content = data.get("message", {}).get("content", "")
                            if content:
                                yield content
                            if data.get("done"):
                                break
            return _gen()
        resp = requests.post(f"{base_url}/api/chat", json={**payload, "stream": False}, timeout=60)
        resp.raise_for_status()
        return resp.json()["message"]["content"]
    except Exception as exc:
        raise RuntimeError(f"Ollama: {exc}") from exc


# ── Provider → fonksiyon + varsayılan model eşlemesi ─────────────────────
PROVIDER_REGISTRY = {
    "groq":      (_chat_groq,      "openai/gpt-oss-20b"),
    "openai":    (_chat_openai,    "gpt-4o-mini"),
    "anthropic": (_chat_anthropic, "claude-3-5-haiku-20241022"),
    "gemini":    (_chat_gemini,    "gemini-2.0-flash"),
    "ollama":    (_chat_ollama,    "llama3.2"),
}

# Görev tipi → tercih sırası (önce tercih, sonra fallback)
TASK_PROVIDER_CHAINS: dict[TaskType, list[str]] = {
    TaskType.CHAT:         ["groq", "gemini", "ollama", "openai", "anthropic"],
    TaskType.CODE:         ["groq", "openai", "gemini", "anthropic", "ollama"],
    TaskType.LONG_CONTEXT: ["gemini", "anthropic", "openai", "groq", "ollama"],
    TaskType.VISION:       ["gemini", "openai", "anthropic"],
}

# Vision için özel modeller
VISION_MODELS = {
    "gemini":    "gemini-2.0-flash",
    "openai":    "gpt-4o",
    "anthropic": "claude-3-5-sonnet-20241022",
}


def _resolve_provider_chain(task_type: TaskType) -> list[tuple[str, str]]:
    """Görev tipi için sıralı (provider_name, model) listesi döndürür.
    Kullanıcı config override'ı önce kontrol edilir.
    """
    env_key = f"JARVIS_MODEL_FOR_{task_type.value.upper()}"
    override = os.environ.get(env_key, "").strip().lower()
    chain = TASK_PROVIDER_CHAINS.get(task_type, TASK_PROVIDER_CHAINS[TaskType.CHAT])
    if override and override in PROVIDER_REGISTRY:
        chain = [override] + [p for p in chain if p != override]

    result = []
    for provider in chain:
        if provider not in PROVIDER_REGISTRY:
            continue
        if task_type == TaskType.VISION:
            model = VISION_MODELS.get(provider, PROVIDER_REGISTRY[provider][1])
        else:
            # Kullanıcı belirli bir model override'ı tanımlamışsa kullan
            model_env = f"JARVIS_{provider.upper()}_MODEL"
            model = os.environ.get(model_env, PROVIDER_REGISTRY[provider][1])
        result.append((provider, model))
    return result


def _check_provider_key(provider: str) -> bool:
    """Provider için API key / bağlantı mevcut mu?"""
    if provider == "groq":
        return bool(os.environ.get("JARVIS_GROQ_API_KEY") or os.environ.get("GROQ_API_KEY"))
    if provider == "openai":
        return bool(os.environ.get("JARVIS_OPENAI_API_KEY"))
    if provider == "anthropic":
        return bool(os.environ.get("JARVIS_ANTHROPIC_API_KEY"))
    if provider == "gemini":
        return bool(os.environ.get("JARVIS_GEMINI_API_KEY"))
    if provider == "ollama":
        # Ollama yerel — key yok, URL yeterli
        return True
    return False


# ── Ana ModelRouter sınıfı ────────────────────────────────────────────────

class ModelRouter:
    """
    Çoklu model yönlendirme sistemi.
    
    Kullanım:
        router = ModelRouter()
        reply = router.chat(history, user_msg, system_prompt, task_type=TaskType.CODE)
        for chunk in router.stream(history, user_msg, system_prompt):
            print(chunk, end="")
    """

    def __init__(self):
        self._lock = threading.Lock()

    def _build_system(self, system: str) -> str:
        """Sistem promptuna tarih ekle."""
        import datetime
        return system + f"\n\nBugünün tarihi: {datetime.datetime.now().strftime('%d %B %Y, %H:%M')}"

    def chat(
        self,
        history: list,
        user_msg: str,
        system: str = "",
        task_type: TaskType = TaskType.CHAT,
        notify_cb=None,   # Kullanıcıya model değişim bildirimi için callback(str)
    ) -> str:
        """
        Senkron chat. Provider başarısız olursa otomatik fallback yapar.
        notify_cb(mesaj) ile fallback bildirimi gönderilir.
        """
        sys_prompt = self._build_system(system)
        chain = _resolve_provider_chain(task_type)

        last_error = "Hiçbir model sağlayıcısı mevcut değil."
        tried = []

        for provider, model in chain:
            if not _check_provider_key(provider):
                continue
            if not _provider_status.is_available(provider):
                logger.info("[ModelRouter] %s cooldown'da, atlanıyor.", provider)
                continue

            tried.append(provider)
            func, _ = PROVIDER_REGISTRY[provider]
            try:
                logger.info("[ModelRouter] Deneniyor: %s / %s (görev: %s)", provider, model, task_type)
                result = func(history, user_msg, sys_prompt, model, stream=False)
                _provider_status.record_success(provider)
                if len(tried) > 1 and notify_cb:
                    notify_cb(f"Model değişti: {tried[-2]} başarısız, {provider} kullanılıyor.")
                return result
            except RuntimeError as exc:
                _provider_status.record_failure(provider)
                last_error = str(exc)
                logger.warning("[ModelRouter] %s başarısız: %s", provider, exc)
                if notify_cb:
                    notify_cb(f"{provider} yanıt vermedi, {self._next_available(chain, tried)} deneniyor...")

        return f"Tüm AI modelleri başarısız oldu. Son hata: {last_error}"

    def stream(
        self,
        history: list,
        user_msg: str,
        system: str = "",
        task_type: TaskType = TaskType.CHAT,
        notify_cb=None,
    ) -> Iterator[str]:
        """
        Streaming chat. Token token yield eder.
        Provider başarısız olursa fallback'e geçer ve yeniden başlar.
        """
        sys_prompt = self._build_system(system)
        chain = _resolve_provider_chain(task_type)
        tried = []

        for provider, model in chain:
            if not _check_provider_key(provider):
                continue
            if not _provider_status.is_available(provider):
                continue

            tried.append(provider)
            func, _ = PROVIDER_REGISTRY[provider]
            try:
                logger.info("[ModelRouter] Stream: %s / %s", provider, model)
                gen = func(history, user_msg, sys_prompt, model, stream=True)
                # Generator başarıyla açıldı — ilk chunk'ı dene
                collected = False
                for chunk in gen:
                    if not collected:
                        collected = True
                        _provider_status.record_success(provider)
                        if len(tried) > 1 and notify_cb:
                            notify_cb(f"Model değişti: {tried[-2]} → {provider}")
                    yield chunk
                return  # başarılı
            except RuntimeError as exc:
                _provider_status.record_failure(provider)
                logger.warning("[ModelRouter] Stream %s başarısız: %s", provider, exc)
                if notify_cb:
                    next_p = self._next_available(chain, tried)
                    if next_p:
                        notify_cb(f"{provider} başarısız, {next_p} deneniyor...")
            except StopIteration:
                return

        yield "Tüm AI modelleri başarısız oldu. Lütfen API key'lerinizi kontrol edin."

    def analyze_image(
        self,
        image_path: str,
        question: str,
        system: str = "",
        notify_cb=None,
    ) -> str:
        """
        Görsel analiz (vision). Destekleyen ilk sağlayıcıyı kullanır.
        image_path: yerel dosya yolu veya URL.
        """
        import base64
        from pathlib import Path

        chain = _resolve_provider_chain(TaskType.VISION)
        last_error = "Vision destekleyen model yok."

        # Görseli base64'e çevir (URL değilse)
        image_b64 = None
        image_url = None
        if image_path.startswith("http"):
            image_url = image_path
        else:
            try:
                image_b64 = base64.b64encode(Path(image_path).read_bytes()).decode()
            except Exception as exc:
                return f"Görsel okunamadı: {exc}"

        for provider, model in chain:
            if not _check_provider_key(provider):
                continue
            if not _provider_status.is_available(provider):
                continue

            try:
                if provider == "gemini":
                    result = self._vision_gemini(image_path, image_b64, image_url, question, model, system)
                elif provider == "openai":
                    result = self._vision_openai(image_b64, image_url, question, model, system)
                elif provider == "anthropic":
                    result = self._vision_anthropic(image_b64, image_url, question, model, system)
                else:
                    continue
                _provider_status.record_success(provider)
                return result
            except Exception as exc:
                _provider_status.record_failure(provider)
                last_error = str(exc)
                logger.warning("[ModelRouter] Vision %s başarısız: %s", provider, exc)

        return f"Görsel analiz başarısız. Son hata: {last_error}"

    def _vision_gemini(self, path, b64, url, question, model, system):
        import google.generativeai as genai
        from pathlib import Path
        key = os.environ.get("JARVIS_GEMINI_API_KEY", "")
        if not key:
            raise RuntimeError("Gemini key yok")
        genai.configure(api_key=key)
        gmodel = genai.GenerativeModel(model_name=model, system_instruction=system or "Görsel analiz et.")
        if b64:
            import PIL.Image, io
            img = PIL.Image.open(io.BytesIO(bytes.fromhex("")))
            img = PIL.Image.open(Path(path))
            resp = gmodel.generate_content([question, img])
        else:
            resp = gmodel.generate_content([question, {"url": url}])
        return resp.text

    def _vision_openai(self, b64, url, question, model, system):
        import openai
        key = os.environ.get("JARVIS_OPENAI_API_KEY", "")
        if not key:
            raise RuntimeError("OpenAI key yok")
        client = openai.OpenAI(api_key=key)
        content = [{"type": "text", "text": question}]
        if b64:
            content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})
        else:
            content.append({"type": "image_url", "image_url": {"url": url}})
        msgs = [{"role": "system", "content": system}] if system else []
        msgs.append({"role": "user", "content": content})
        resp = client.chat.completions.create(model=model, messages=msgs, max_tokens=1024)
        return resp.choices[0].message.content

    def _vision_anthropic(self, b64, url, question, model, system):
        import anthropic
        key = os.environ.get("JARVIS_ANTHROPIC_API_KEY", "")
        if not key:
            raise RuntimeError("Anthropic key yok")
        client = anthropic.Anthropic(api_key=key)
        content = []
        if b64:
            content.append({"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}})
        else:
            content.append({"type": "image", "source": {"type": "url", "url": url}})
        content.append({"type": "text", "text": question})
        resp = client.messages.create(
            model=model, system=system or "Görsel analiz et.", messages=[{"role": "user", "content": content}],
            max_tokens=1024)
        return resp.content[0].text

    @staticmethod
    def _next_available(chain: list[tuple], tried: list[str]) -> str:
        for provider, _ in chain:
            if provider not in tried and _check_provider_key(provider):
                return provider
        return ""

    def available_providers(self) -> list[str]:
        """Mevcut (key'i olan) sağlayıcıları döndür."""
        return [p for p in PROVIDER_REGISTRY if _check_provider_key(p)]

    def status_report(self) -> str:
        """Hangi provider'ların aktif olduğunu gösteren özet."""
        lines = ["[ModelRouter] Sağlayıcı durumu:"]
        for name in PROVIDER_REGISTRY:
            has_key = _check_provider_key(name)
            available = _provider_status.is_available(name)
            if not has_key:
                state = "❌ Key yok"
            elif not available:
                state = "⏳ Cooldown"
            else:
                state = "✓ Aktif"
            _, default_model = PROVIDER_REGISTRY[name]
            lines.append(f"  {name:12} {state:16} (varsayılan model: {default_model})")
        return "\n".join(lines)


# ── Singleton ────────────────────────────────────────────────────────────
_router_instance: ModelRouter | None = None
_router_lock = threading.Lock()


def get_router() -> ModelRouter:
    """Thread-safe singleton."""
    global _router_instance
    with _router_lock:
        if _router_instance is None:
            _router_instance = ModelRouter()
    return _router_instance
