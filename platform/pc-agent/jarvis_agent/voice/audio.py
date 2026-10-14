"""Mikrofon yakalama — sounddevice tabanlı, donanım yokluğunda zarif degrade.

Tüm ses katmanı 16 kHz mono float32 örnekleriyle çalışır (STT için
Whisper'ın beklediği biçim).
"""
from __future__ import annotations

import logging
import queue
import threading
from typing import Optional

import numpy as np

logger = logging.getLogger("jarvis.voice.audio")

SAMPLE_RATE = 16000
BLOCK_SIZE = 1600  # 100 ms — VAD için yeterince ince, CPU dostu

try:
    import sounddevice as sd  # type: ignore
    _SD_AVAILABLE = True
except (ImportError, OSError):
    sd = None  # type: ignore
    _SD_AVAILABLE = False


class MicrophoneError(RuntimeError):
    """Mikrofon açılamadı veya donanım yok."""


def has_audio_backend() -> bool:
    """sounddevice + en az bir giriş cihazı var mı?

    JARVIS_VOICE_DISABLED=1 ile tamamen kapatılabilir (test/CI ortamı).
    """
    import os

    if os.getenv("JARVIS_VOICE_DISABLED", "").strip().lower() in ("1", "true", "yes"):
        return False
    if not _SD_AVAILABLE:
        return False
    try:
        return any(
            d["max_input_channels"] > 0 for d in sd.query_devices()
        )
    except Exception:
        return False


class MicrophoneStream:
    """Arka plan iş parçacığında blok okuyan, kuyruk temelli mikrofon akışı."""

    def __init__(self, device: Optional[int] = None) -> None:
        self.device = device
        self._stream = None
        self._queue: "queue.Queue[np.ndarray]" = queue.Queue()
        self._lock = threading.Lock()
        self._active = False

    @property
    def active(self) -> bool:
        return self._active

    def start(self) -> None:
        with self._lock:
            if self._active:
                return
            if not _SD_AVAILABLE:
                raise MicrophoneError(
                    "sounddevice kurulu değil (pip install sounddevice)."
                )
            try:
                self._stream = sd.InputStream(
                    samplerate=SAMPLE_RATE,
                    channels=1,
                    dtype="float32",
                    blocksize=BLOCK_SIZE,
                    device=self.device,
                    callback=self._on_block,
                )
                self._stream.start()
                self._active = True
                logger.info("Mikrofon akışı başladı (16 kHz mono)")
            except Exception as exc:
                self._active = False
                raise MicrophoneError(f"Mikrofon açılamadı: {exc}") from exc

    def stop(self) -> None:
        with self._lock:
            if self._stream is not None:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception:
                    pass
                self._stream = None
            self._active = False
            # kuyruğu boşalt
            while not self._queue.empty():
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    break

    def _on_block(self, indata, frames, time_info, status) -> None:  # noqa: ANN001
        if status:
            logger.debug("Ses akışı uyarısı: %s", status)
        self._queue.put(indata[:, 0].copy())

    def read_block(self, timeout: float = 1.0) -> Optional[np.ndarray]:
        """Bir blok (100 ms) okur; timeout'ta None döner."""
        try:
            return self._queue.get(timeout=timeout)
        except queue.Empty:
            return None
