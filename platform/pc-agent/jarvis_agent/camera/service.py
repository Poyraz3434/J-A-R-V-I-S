"""Kamera servisi — OpenCV ile açma/kapama ve fotoğraf çekme.

Güvenlik: kamera yalnızca kullanıcının açık isteğiyle açılır (UI'daki Open
butonu); arayüzde her zaman görünür bir durum göstergesi (LIVE) vardır.
"""
from __future__ import annotations

import base64
import datetime
import logging
import os
import platform
import threading
from typing import Any, Optional

logger = logging.getLogger("jarvis.camera")

try:
    import cv2  # type: ignore
except ImportError:  # opencv yüklü değil — modül düzgün biçimde devre dışı kalır
    cv2 = None


class CameraError(RuntimeError):
    """Kamera işlemi başarısız."""


class CameraService:
    """Tek kamera cihazını yöneten, iş parçacığı güvenli servis."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._cap: Optional[Any] = None
        self._width = 0
        self._height = 0

    # ── Yardımcılar ──
    @staticmethod
    def _disabled_by_env() -> bool:
        return os.getenv("JARVIS_CAMERA_DISABLED", "").strip().lower() in ("1", "true", "yes")

    def _ensure_cv2(self) -> None:
        if cv2 is None:
            raise CameraError("opencv-python kurulu değil: pip install opencv-python")

    def _capture_backend(self) -> int:
        # Windows'ta DSHOW arka ucu kamerayı çok daha hızlı açar.
        if platform.system() == "Windows" and cv2 is not None:
            try:
                return int(cv2.CAP_DSHOW)
            except Exception:  # pragma: no cover
                return 0
        return 0

    # ── Genel API ──
    def open(self, index: int = 0) -> dict[str, Any]:
        with self._lock:
            if self._disabled_by_env():
                raise CameraError("Kamera bu oturumda devre dışı (JARVIS_CAMERA_DISABLED=1).")
            self._ensure_cv2()
            if self._cap is not None:
                return self.status()

            cap = cv2.VideoCapture(index, self._capture_backend())
            if not cap.isOpened():
                cap.release()
                raise CameraError(f"Kamera açılamadı (index {index}). Bağlı bir kamera var mı?")
            ok, frame = cap.read()
            if not ok or frame is None:
                cap.release()
                raise CameraError("Kameradan görüntü alınamadı.")
            self._cap = cap
            self._height, self._width = frame.shape[:2]
            logger.info("Kamera açıldı: %sx%s", self._width, self._height)
            return self.status()

    def close(self) -> dict[str, Any]:
        with self._lock:
            if self._cap is not None:
                self._cap.release()
                self._cap = None
                logger.info("Kamera kapatıldı")
            return self.status()

    def status(self) -> dict[str, Any]:
        with self._lock:
            live = self._cap is not None
            return {
                "status": "live" if live else "off",
                "width": self._width if live else None,
                "height": self._height if live else None,
            }

    def capture(self) -> dict[str, Any]:
        with self._lock:
            if self._disabled_by_env():
                raise CameraError("Kamera bu oturumda devre dışı (JARVIS_CAMERA_DISABLED=1).")
            if self._cap is None:
                raise CameraError("Kamera kapalı; önce açın.")
            ok, frame = self._cap.read()
            if not ok or frame is None:
                raise CameraError("Fotoğraf çekilemedi; kamera yanıt vermiyor.")
            success, buffer = cv2.imencode(
                ".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85]
            )
            if not success:
                raise CameraError("Görüntü JPEG'e dönüştürülemedi.")
            encoded = base64.b64encode(buffer.tobytes()).decode("ascii")
            return {
                "image": f"data:image/jpeg;base64,{encoded}",
                "captured_at": datetime.datetime.now().isoformat(timespec="seconds"),
            }
