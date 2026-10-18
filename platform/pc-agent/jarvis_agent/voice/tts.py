"""TTS — gTTS ile Türkçe konuşma sentezi ve MP3 oynatma."""
from __future__ import annotations

import asyncio
import logging
import threading
from pathlib import Path
from tempfile import NamedTemporaryFile

logger = logging.getLogger("jarvis.voice.tts")

class TTSService:
    """Metni sese çevirir ve çalar; iptal edilebilir."""

    def __init__(self, tmp_dir: Path | None = None) -> None:
        self._cancel = threading.Event()
        self._speaking = threading.Event()
        self._tmp_dir = tmp_dir

    @property
    def speaking(self) -> bool:
        return self._speaking.is_set()

    def cancel(self) -> None:
        """Kullanıcı konuşmaya başladı — mevcut konuşmayı kes (barge-in)."""
        self._cancel.set()

    async def speak(self, text: str) -> bool:
        """Metni seslendirir. İptal edilirse False döner."""
        text = (text or "").strip()
        if not text:
            return False
        self._cancel.clear()
        self._speaking.set()
        try:
            return await self._speak_inner(text)
        finally:
            self._speaking.clear()

    async def _speak_inner(self, text: str) -> bool:
        path: Path | None = None
        try:
            from gtts import gTTS

            with NamedTemporaryFile(
                suffix=".mp3", delete=False, dir=self._tmp_dir
            ) as tmp:
                tmp_path = Path(tmp.name)
            path = tmp_path
            await asyncio.to_thread(gTTS(text=text, lang="tr", slow=False).save, str(path))
            if self._cancel.is_set():
                path.unlink(missing_ok=True)
                return False
            return await asyncio.to_thread(self._play_mp3_blocking, path)
        except Exception:
            logger.exception("gTTS konuşma üretimi veya oynatması başarısız")
            if path is not None:
                path.unlink(missing_ok=True)
            return False

    def _play_mp3_blocking(self, path: Path) -> bool:
        """gTTS tarafından üretilen MP3'ü çalar."""
        try:
            from playsound import playsound

            playsound(str(path))
            return not self._cancel.is_set()
        finally:
            path.unlink(missing_ok=True)
