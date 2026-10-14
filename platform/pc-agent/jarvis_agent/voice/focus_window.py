"""Çift alkışta Jarvis penceresini öne getirme (Windows).

İsteğe bağlı: pygetwindow kuruluysa "J.A.R.V.I.S" başlıklı tarayıcı
penceresini bulur ve öne getirir. Kurulu değilse/yoksa sessizce boş geçer —
sesli yanıt her durumda verilir.
"""
from __future__ import annotations

import logging

logger = logging.getLogger("jarvis.voice.focus")

_TITLE_HINTS = ("j.a.r.v", "jarvis")


def bring_jarvis_to_front() -> bool:
    try:
        import pygetwindow as gw  # type: ignore

        for title_hint in _TITLE_HINTS:
            for win in gw.getAllWindows():
                title = (win.title or "").lower()
                if title and title_hint in title and win.isVisible:
                    try:
                        win.activate()
                        return True
                    except Exception:
                        continue
    except ImportError:
        logger.debug("pygetwindow kurulu değil — pencere öne getirme atlandı")
    except Exception:
        logger.exception("Pencere öne getirme başarısız")
    return False
