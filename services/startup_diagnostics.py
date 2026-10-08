"""Non-secret startup checks for providers and optional integrations."""
from __future__ import annotations

import importlib.util
import os
import shutil

from config import GEMINI_API_KEY, GROQ_API_KEY, OWM_API_KEY


def collect_startup_diagnostics() -> list[tuple[str, str]]:
    """Return (status, message) pairs without exposing credential values."""
    checks = []
    providers_ready = bool(GROQ_API_KEY or GEMINI_API_KEY)
    checks.append((
        "OK" if providers_ready else "UYARI",
        "AI sağlayıcısı anahtarı yapılandırılmış."
        if providers_ready else
        "Groq ve Gemini anahtarı bulunamadı; sohbet yanıtları kullanılamayacak.",
    ))
    if GROQ_API_KEY:
        checks.append(("OK", "Groq API anahtarı bulundu (değeri gizli)."))
    if GEMINI_API_KEY:
        checks.append(("OK", "Gemini API anahtarı bulundu (değeri gizli)."))
    checks.append((
        "OK" if OWM_API_KEY else "BİLGİ",
        "Hava durumu API anahtarı yapılandırılmış."
        if OWM_API_KEY else "Hava durumu özelliği için OWM_API_KEY ayarlı değil.",
    ))
    for package, label in (
        ("yfinance", "Borsa verisi"),
        ("edge_tts", "Sesli yanıt"),
        ("speech_recognition", "Ses tanıma"),
        ("playwright", "Web otomasyonu"),
        ("speedtest", "Hız testi"),
    ):
        try:
            available = importlib.util.find_spec(package) is not None
        except (ImportError, ValueError):
            available = False
        checks.append((
            "OK" if available else "BİLGİ",
            f"{label} bileşeni kullanılabilir."
            if available else f"{label} bileşeni kurulu değil; ilgili özellik sınırlı.",
        ))
    checks.append((
        "OK" if shutil.which("tesseract") else "BİLGİ",
        "Tesseract OCR kullanılabilir."
        if shutil.which("tesseract") else
        "Tesseract OCR bulunamadı; PDF/görüntü OCR özelliği sınırlı olabilir.",
    ))
    if os.getenv("JARVIS_SHARE_CONTEXT", "").strip().lower() in {
        "1", "true", "yes", "on"
    }:
        checks.append((
            "UYARI",
            "Yerel belge bağlamı AI sağlayıcısına paylaşılacak şekilde etkin.",
        ))
    return checks


def format_startup_diagnostics() -> str:
    return "\n".join(
        f"{status}: {message}"
        for status, message in collect_startup_diagnostics()
    )
