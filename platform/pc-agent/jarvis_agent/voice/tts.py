"""TTS — konuşma sentezi: edge-tts (çevrimiçi) + Windows SAPI (yerel yedek).

Gereksinim 5.4: doğal Türkçe ses; internet yoksa çalışan yerel alternatif.
- Birincil: edge-tts "tr-TR-AhmetNeural" (doğal, ücretsiz Microsoft uç noktası)
- Yedek: pyttsx3 + Windows SAPI (çevrimdışı, daha robotik ama garantili)
Barge-in (kullanıcı konuşunca susma): konuşma öncesi iptal bayrağı.
"""
from __future__ import annotations

import asyncio
import logging
import threading
from pathlib import Path
from tempfile import NamedTemporaryFile

from .. import config

logger = logging.getLogger("jarvis.voice.tts")

EDGE_VOICE = "tr-TR-AhmetNeural"
SAPI_VOICE_HINT = "Microsoft"  # Türkçe SAPI sesi varsa seç


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

    # ── Birincil: edge-tts → mp3 → çal (bağımsız iş parçacığında) ──
    async def _speak_inner(self, text: str) -> bool:
        try:
            import edge_tts

            communicate = edge_tts.Communicate(text, EDGE_VOICE)
            with NamedTemporaryFile(
                suffix=".mp3", delete=False, dir=self._tmp_dir
            ) as tmp:
                tmp_path = Path(tmp.name)
            try:
                await communicate.save(str(tmp_path))
            except Exception:
                tmp_path.unlink(missing_ok=True)
                raise
            if self._cancel.is_set():
                tmp_path.unlink(missing_ok=True)
                return False
            return await asyncio.to_thread(self._play_mp3_blocking, tmp_path)
        except ImportError:
            logger.warning("edge-tts kurulu değil — SAPI yedeğine geçiliyor")
        except Exception as exc:
            logger.warning("edge-tts başarısız (%s) — SAPI yedeğine geçiliyor", exc)
        # ── Yedek: Windows SAPI (çevrimdışı) ──
        return await asyncio.to_thread(self._speak_sapi_blocking, text)

    def _play_mp3_blocking(self, path: Path) -> bool:
        """MP3'ü çalar (mpv/wmplayer yoksa Python ses motorlarına düşer)."""
        played = False
        try:
            # 1) ses oynatıcıları dene (hızlı yol)
            try:
                from playsound import playsound  # type: ignore

                playsound(str(path))
                played = True
            except Exception:
                pass
            if not played:
                # 2) pygame fallback
                try:
                    import pygame  # type: ignore

                    if not pygame.mixer.get_init():
                        pygame.mixer.init()
                    pygame.mixer.music.load(str(path))
                    pygame.mixer.music.play()
                    while pygame.mixer.music.get_busy():
                        if self._cancel.is_set():
                            pygame.mixer.music.stop()
                            break
                        pygame.time.wait(100)
                    played = True
                except Exception:
                    pass
            if not played:
                logger.warning("MP3 oynatıcı bulunamadı — SAPI yedeğine geçiliyor")
                return False
            return not self._cancel.is_set()
        finally:
            path.unlink(missing_ok=True)

    def _speak_sapi_blocking(self, text: str) -> bool:
        """pyttsx3 + Windows SAPI ile çevrimdışı konuşma."""
        try:
            import pyttsx3  # type: ignore

            engine = pyttsx3.init()
            for voice in engine.getProperty("voices"):
                name = (getattr(voice, "name", "") or "").lower()
                if "turkish" in name or "türk" in name or "tr-tr" in name.replace(" ", "-"):
                    engine.setProperty("voice", voice.id)
                    break
            engine.setProperty("rate", 175)
            engine.startLoop(False)
            engine.say(text)
            engine.iterate()
            while engine.isBusy():
                if self._cancel.is_set():
                    engine.stop()
                    return False
                engine.iterate()
            engine.endLoop()
            return not self._cancel.is_set()
        except Exception:
            logger.exception("SAPI TTS de başarısız — sesli yanıt verilemiyor")
            return False
