"""JARVIS Platform — PC Agent yapılandırması.

Ortam değişkenleri aşağıdaki sırayla yüklenen .env dosyalarından okunur
(aynı anahtar için ilk bulunan değer kazanır; gerçek ortam değişkenleri
her zaman .env dosyalarından önceliklidir):

1. platform/pc-agent/.env
2. platform/.env
3. <depo kökü>/.env          ← mevcut JARVIS v10 anahtarları otomatik devralınır

Anahtar değerleri koda asla gömülmez (bkz. .env.example).
"""
from __future__ import annotations

import os
from pathlib import Path

APP_VERSION = "1.0.0"

AGENT_ROOT = Path(__file__).resolve().parent.parent      # platform/pc-agent
PLATFORM_ROOT = AGENT_ROOT.parent                       # platform/
REPO_ROOT = PLATFORM_ROOT.parent                        # depo kökü
WEB_DIST_DIR = PLATFORM_ROOT / "web" / "dist"

APP_DATA_DIR = Path.home() / ".jarvis-platform"
APP_DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = APP_DATA_DIR / "agent.db"
SESSIONS_FILE = APP_DATA_DIR / "sessions.count"
LOG_DIR = APP_DATA_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "agent.log"

ALLOWED_BG_COLORS = ("red", "green", "blue")

# Şablon dosyalarındaki sahte anahtar değerleri geçersiz sayılır.
_PLACEHOLDER_PREFIXES = ("your_", "xxx", "changeme")


def _looks_like_placeholder(value: str) -> bool:
    lowered = value.lower()
    return any(lowered.startswith(prefix) for prefix in _PLACEHOLDER_PREFIXES)


def _load_dotenv() -> None:
    candidates = [
        AGENT_ROOT / ".env",
        PLATFORM_ROOT / ".env",
        REPO_ROOT / ".env",
    ]
    for env_path in candidates:
        if not env_path.is_file():
            continue
        try:
            raw = env_path.read_text(encoding="utf-8")
        except OSError:
            continue
        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


_load_dotenv()


def env(name: str, default: str = "") -> str:
    """Ortam değişkeni okur; boş veya placeholder değerler default'a düşer."""
    value = os.getenv(name, "").strip()
    if not value or _looks_like_placeholder(value):
        return default
    return value


# ── Sunucu bağlantısı ────────────────────────────────────────────────────────
# Varsayılan 127.0.0.1: yalnızca bu makine. Yerel ağdan (telefon) erişmek için
# .env dosyasında JARVIS_BIND=0.0.0.0 yapın.
# GÜVENLİK NOTU: Faz 1'de kimlik doğrulama yoktur; güvenli olmayan ağlarda
# localhost'ta kalın. Kimlik doğrulama Faz 2'de (QR eşleştirme) eklenir.
BIND_HOST = env("JARVIS_BIND", "127.0.0.1")
BIND_PORT = int(env("JARVIS_PORT", "8000"))


# ── LLM sağlayıcısı ──────────────────────────────────────────────────────────
LLM_PROVIDER = env("JARVIS_LLM_PROVIDER").lower()    # boş → otomatik algılama
LLM_MODEL = env("JARVIS_LLM_MODEL")                  # boş → sağlayıcı varsayılanı

GROQ_API_KEY = env("JARVIS_GROQ_API_KEY") or env("GROQ_API_KEY")
GROQ_MODEL = env("JARVIS_GROQ_MODEL", "openai/gpt-oss-20b")
OPENAI_API_KEY = env("JARVIS_OPENAI_API_KEY") or env("OPENAI_API_KEY")
ANTHROPIC_API_KEY = env("JARVIS_ANTHROPIC_API_KEY") or env("ANTHROPIC_API_KEY")
OLLAMA_URL = env("JARVIS_OLLAMA_URL")                # boş → devre dışı

DEFAULT_MODELS = {
    "groq": GROQ_MODEL,
    "openai": "gpt-4o-mini",
    "anthropic": "claude-sonnet-4-20250514",
    "ollama": "llama3.1",
    "mock": "mock-1",
}


def detect_provider() -> str:
    """Hangi sağlayıcının anahtarı varsa onu seçer (öncelik sırasıyla)."""
    if GROQ_API_KEY:
        return "groq"
    if OPENAI_API_KEY:
        return "openai"
    if ANTHROPIC_API_KEY:
        return "anthropic"
    if OLLAMA_URL:
        return "ollama"
    return "mock"


def active_provider() -> str:
    return LLM_PROVIDER or detect_provider()


def active_model() -> str:
    return LLM_MODEL or DEFAULT_MODELS.get(active_provider(), "mock-1")


# ── Hava durumu ──────────────────────────────────────────────────────────────
OWM_API_KEY = env("JARVIS_OWM_API_KEY") or env("OWM_API_KEY")
DEFAULT_CITY = env("JARVIS_CITY", "Tuzla,TR")

# ── Relay (Faz 4: hatırlatıcılar relay'de yaşar) ─────────────────────────────
# Boş bırakılırsa hatırlatıcı modülü devre dışı kalır (yerel test kolaylığı).
RELAY_URL = env("JARVIS_RELAY_URL")                     # ör. ws://192.168.1.10:8100
RELAY_TOKEN = env("JARVIS_RELAY_TOKEN")
RELAY_HTTP_URL = env("JARVIS_RELAY_HTTP_URL")           # ör. http://192.168.1.10:8100
# Alarm kullanıcı hareketiyle susma koşulu: son X saniyede giriş varsa "duyuldu" say.
ALARM_IDLE_ACK_SECONDS = float(env("JARVIS_ALARM_IDLE_ACK_SECONDS", "5"))

# ── Arayüz varsayılanları ────────────────────────────────────────────────────
DEFAULT_BG_COLOR = env("JARVIS_DEFAULT_BG_COLOR", "blue")
if DEFAULT_BG_COLOR not in ALLOWED_BG_COLORS:
    DEFAULT_BG_COLOR = "blue"
