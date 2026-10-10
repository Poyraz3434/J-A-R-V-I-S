"""Merkezi pencere yönetimi — JARVIS ve ATLAS pencereleri karşılıklı dışlayıcıdır.

Tek bir WindowManager ekranda hangi pencerenin olduğunu bilir; pencereler
kendi kendilerine show/hide kararı vermez. Özellik 6 (ATLAS ↔ JARVIS pencere
geçişi) için temel altyapı.
"""
from __future__ import annotations

import logging
from enum import Enum

from PySide6.QtCore import QEasingCurve, QObject, QPropertyAnimation, Signal

logger = logging.getLogger(__name__)


class ActiveWindow(str, Enum):
    """Ekranda aktif (görünür) olan pencereyi belirtir."""

    JARVIS = "jarvis"
    ATLAS = "atlas"


class WindowManager(QObject):
    """JARVIS ve ATLAS pencerelerinin görünürlüğünü tek yerden yönetir.

    Kurallar:
    * Her anda yalnızca tek pencere görünür (karşılıklı dışlayıcı).
    * Geçişlerde pencereler kapatılmaz, gizlenir (hide); böylece sohbet
      geçmişi ve oturum bağlamı korunur.
    * Manuel "JARVIS'i aç" istekleri (tepsi menüsü, uyandırma kelimesi)
      ATLAS aktifken reddedilir; ATLAS öne alınır.
    """

    active_changed = Signal(str)  # ActiveWindow.value ("jarvis" | "atlas")

    FADE_MS = 160  # yumuşak açılış süresi (ms)

    def __init__(self, animate: bool = True, parent: QObject | None = None):
        super().__init__(parent)
        self._windows: dict[ActiveWindow, object] = {}
        self._active = ActiveWindow.JARVIS
        self._animations: list[QPropertyAnimation] = []
        self.animate = animate

    # ── Kayıt ─────────────────────────────────────────────────────────────
    @property
    def active(self) -> ActiveWindow:
        """Ekranda aktif olan pencere."""
        return self._active

    def register(self, role: ActiveWindow, window) -> None:
        """Bir pencereyi yöneticiye kaydet.

        Pencere duck-typed: show/hide/raise_/activateWindow/setWindowOpacity
        metotlarına sahip olmalı; olmayanlar sessizce atlanır.
        """
        self._windows[role] = window
        logger.debug("[WindowManager] Kayıt: %s -> %s", role.value, type(window).__name__)

    # ── Geçişler ──────────────────────────────────────────────────────────
    def open_atlas(self) -> None:
        """ATLAS'ı göster; JARVIS'i gizle."""
        self._switch(ActiveWindow.ATLAS)

    def open_jarvis(self) -> None:
        """JARVIS'i göster; ATLAS'ı gizle."""
        self._switch(ActiveWindow.JARVIS)

    def request_jarvis(self) -> bool:
        """Manuel "JARVIS'i aç" isteği (tepsi menüsü, uyandırma kelimesi).

        ATLAS aktifse JARVIS açılmaz; ATLAS öne alınır ve ``False`` döner.
        ATLAS kapalıysa JARVIS'e geçilir ve ``True`` döner.
        """
        if self._active is ActiveWindow.ATLAS:
            atlas = self._windows.get(ActiveWindow.ATLAS)
            if atlas is not None:
                self._raise(atlas)
            logger.info("[WindowManager] JARVIS açma isteği reddedildi — ATLAS aktif.")
            return False
        self._switch(ActiveWindow.JARVIS)
        return True

    # ── Dahili ────────────────────────────────────────────────────────────
    def _switch(self, target: ActiveWindow) -> None:
        """Hedef pencereyi öne çıkar; diğerini gizle (dışlayıcı davranış)."""
        window = self._windows.get(target)
        if window is None:
            logger.warning("[WindowManager] %s kayıtlı değil; geçiş iptal edildi.", target.value)
            return
        previous = self._active
        if previous is not target:
            other = self._windows.get(previous)
            if other is not None:
                try:
                    other.hide()
                except Exception as exc:
                    logger.warning("[WindowManager] %s gizlenemedi: %s", previous.value, exc)
        self._active = target
        try:
            window.show()
            self._raise(window)
            if previous is not target:
                self._fade_in(window)
        except Exception as exc:
            logger.error("[WindowManager] %s gösterilemedi: %s", target.value, exc)
            return
        if previous is not target:
            logger.info("[WindowManager] Geçiş: %s -> %s", previous.value, target.value)
            self.active_changed.emit(target.value)

    @staticmethod
    def _raise(window) -> None:
        """Pencereyi öne çıkar ve odakla (duck-typed, metot yoksa sessizce atla)."""
        for name in ("raise_", "activateWindow"):
            method = getattr(window, name, None)
            if callable(method):
                try:
                    method()
                except Exception as exc:
                    logger.debug("[WindowManager] %s çağrılamadı: %s", name, exc)

    def _fade_in(self, window) -> None:
        """Yumuşak açılış (fade-in) — ani/sert atlama olmadan geçiş hissi."""
        if not self.animate or not hasattr(window, "setWindowOpacity"):
            return
        try:
            window.setWindowOpacity(0.0)
            anim = QPropertyAnimation(window, b"windowOpacity", self)
            anim.setDuration(self.FADE_MS)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)

            def _finish() -> None:
                try:
                    window.setWindowOpacity(1.0)  # kesinti olsa bile tam opak kal
                finally:
                    if anim in self._animations:
                        self._animations.remove(anim)
                    anim.deleteLater()

            anim.finished.connect(_finish)
            self._animations.append(anim)
            anim.start()
        except Exception as exc:
            logger.warning("[WindowManager] Fade-in atlandı: %s", exc)
            try:
                window.setWindowOpacity(1.0)
            except Exception:
                pass
