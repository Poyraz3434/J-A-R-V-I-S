"""Özellik 10 — Deep Research yuvarlak geri sayım göstergesi (mm:ss)."""
from __future__ import annotations

import time

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QApplication, QWidget

ROUND_COUNTDOWN_MIN_S = 300  # ≥5 dakikalık tahminlerde gösterilir


def should_show_countdown(estimate_s: float) -> bool:
    """Tahmini süre 5 dakika veya üzerindeyse geri sayım gösterilir."""
    return float(estimate_s) >= ROUND_COUNTDOWN_MIN_S


class RoundCountdownWidget(QWidget):
    """Ekran ortasında yuvarlak, mm:ss canlı güncellenen geri sayım."""

    SIZE = 150

    def __init__(self, parent: QWidget | None = None):
        super().__init__(
            parent,
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool,
        )
        self.setFixedSize(self.SIZE, self.SIZE)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._total = 0
        self._end = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._on_tick)

    # ── Kontrol ─────────────────────────────────────────────────────────────
    def start_countdown(self, total_s: int) -> None:
        """Geri sayımı başlat ve göster (toplam süre saniye)."""
        self._total = max(1, int(total_s))
        self._end = time.time() + self._total
        self._place_centered()
        self.show()
        self.raise_()
        self._timer.start()
        self.update()

    def stop_countdown(self) -> None:
        """Geri sayımı durdur ve gizle."""
        self._timer.stop()
        self.hide()

    def remaining(self) -> int:
        """Kalan süre (saniye, en az 0)."""
        if self._total <= 0:
            return 0
        return max(0, int(self._end - time.time()))

    # ── Dahili ──────────────────────────────────────────────────────────────
    def _on_tick(self) -> None:
        self.update()
        if self.remaining() <= 0:
            self.stop_countdown()

    def _place_centered(self) -> None:
        """Ana ekranın ortasına yerleştir."""
        try:
            screen = QApplication.primaryScreen()
            geo = screen.availableGeometry() if screen else None
            if geo is not None:
                self.move(
                    geo.center().x() - self.SIZE // 2,
                    geo.center().y() - self.SIZE // 2,
                )
        except Exception:
            pass

    def paintEvent(self, event) -> None:
        """Koyu daire + ilerleme halkası + ortada mm:ss."""
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            rect = QRectF(4, 4, self.SIZE - 8, self.SIZE - 8)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(8, 14, 24, 235))
            painter.drawEllipse(rect)

            total = max(1, self._total)
            frac = self.remaining() / total
            ring_pen = QPen(QColor("#3d8bfd"), 7)
            ring_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(ring_pen)
            start = 90 * 16  # saat 12'den başla (derece → 1/16°)
            painter.drawArc(rect.adjusted(6, 6, -6, -6), start, int(-360 * 16 * frac))

            secs = self.remaining()
            label = f"{secs // 60:02d}:{secs % 60:02d}"
            painter.setPen(QColor("#c8d8f0"))
            painter.setFont(QFont("Consolas", 15, QFont.Weight.Bold))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, label)
        except Exception:
            pass
        finally:
            painter.end()
        super().paintEvent(event)
