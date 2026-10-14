"""STT — konuşma tanıma katmanı (çevrimiçi birincil + yerel yedek).

Gereksinim 5.4: Türkçe STT; internet yoksa çalışan yerel alternatif.
- Birincil (çevrimiçi): Groq whisper-large-v3 — mevcut JARVIS_GROQ_API_KEY
  otomatik kullanılır, düşük gecikmeli.
- Yedek (yerel): faster-whisper (kuruluysa) — uyandırma ifadesi tespiti
  ZORUNLU olarak bunu kullanır ("uyandırma tamamen yerel", 5.4).
"""
from __future__ import annotations

import io
import logging
import wave
from dataclasses import dataclass
from typing import Optional

import numpy as np

from .. import config

logger = logging.getLogger("jarvis.voice.stt")

SAMPLE_RATE = 16000

# ── Yerel motor (faster-whisper) — tembel yüklenir ──
_local_model = None
_local_load_attempted = False


def _get_local_model():
    """faster-whisper 'tiny' modeli (uyandırma için) — tek seferlik yükler."""
    global _local_model, _local_load_attempted
    if _local_load_attempted:
        return _local_model
    _local_load_attempted = True
    try:
        from faster_whisper import WhisperModel  # type: ignore

        _local_model = WhisperModel(
            "small", device="cpu", compute_type="int8",
        )
        logger.info("Yerel STT hazır (faster-whisper small, int8, CPU)")
    except ImportError:
        logger.warning(
            "faster-whisper kurulu değil — yerel uyandırma devre dışı. "
            "(pip install faster-whisper)"
        )
    except Exception:
        logger.exception("Yerel STT modeli yüklenemedi")
    return _local_model


def local_stt_available() -> bool:
    return _get_local_model() is not None


@dataclass
class STTResult:
    text: str
    engine: str  # "groq" | "local" | "none"
    ok: bool
    error: str = ""


def pcm_to_wav_bytes(pcm: np.ndarray, sample_rate: int = SAMPLE_RATE) -> bytes:
    """float32 PCM'yi 16-bit WAV baytlarına çevirir (API'lerin beklediği biçim)."""
    clipped = np.clip(pcm, -1.0, 1.0)
    ints = (clipped * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(ints.tobytes())
    return buf.getvalue()


def transcribe_local(pcm: np.ndarray, sample_rate: int = SAMPLE_RATE) -> STTResult:
    """Tamamen yerel tanıma — uyandırma ifadesi tespiti bunu kullanır."""
    model = _get_local_model()
    if model is None:
        return STTResult("", "none", False, "yerel STT kurulu değil")
    try:
        clipped = np.clip(pcm, -1.0, 1.0).astype(np.float32)
        segments, _info = model.transcribe(
            clipped, language="tr", beam_size=1, vad_filter=True,
        )
        text = " ".join(s.text for s in segments).strip()
        return STTResult(text, "local", True)
    except Exception as exc:
        logger.exception("Yerel STT hatası")
        return STTResult("", "local", False, str(exc))


async def transcribe_online(pcm: np.ndarray, sample_rate: int = SAMPLE_RATE) -> STTResult:
    """Groq whisper-large-v3 ile çevrimiçi tanıma (anahtar varsa)."""
    import httpx

    api_key = config.GROQ_API_KEY
    if not api_key:
        return STTResult("", "none", False, "Groq anahtarı yok")
    wav_bytes = pcm_to_wav_bytes(pcm, sample_rate)
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {api_key}"},
                files={"file": ("audio.wav", wav_bytes, "audio/wav")},
                data={"model": "whisper-large-v3", "language": "tr",
                      "response_format": "json"},
            )
        if resp.status_code != 200:
            return STTResult("", "groq", False, f"HTTP {resp.status_code}")
        return STTResult(resp.json().get("text", ""), "groq", True)
    except Exception as exc:
        return STTResult("", "groq", False, str(exc))


async def transcribe(pcm: np.ndarray, sample_rate: int = SAMPLE_RATE) -> STTResult:
    """Çevrimiçi birincil, yerel yedek. İkisi de yoksa hata."""
    result = await transcribe_online(pcm, sample_rate)
    if result.ok and result.text.strip():
        return result
    logger.info("Çevrimiçi STT kullanılamadı (%s) — yerel yedek deneniyor", result.error)
    local = transcribe_local(pcm, sample_rate)
    if local.ok and local.text.strip():
        return local
    if result.ok:  # ikisi de boş metin döndü
        return result if result.text else local
    return local
