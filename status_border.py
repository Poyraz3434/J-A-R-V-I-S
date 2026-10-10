"""Özellik 7 — Durum çerçevesi (StatusBorder).

Uygulama genel durumunu (idle / busy / error / success) pencereyi saran ince,
yuvarlatılmış bir çerçeveyle gösterir; renk geçişleri yumuşak interpolasyonla
yapılır (ani/sert atlama yok). Üst renkli durum çubuğunun yerini alır.

Bileşenler:
* ``AppState``              — dört durumun enum'u.
* ``StatusColorController`` — durumu yumuşak renge çeviren, tekrar kullanılabilir
  merkezi kontrolör (JARVIS çerçevesi ile ATLAS overlay'i paylaşır).
* ``StatusBorderWidget``    — içeriği saran, controller'ı çizen çerçeve widget'ı.

Durum makinesi:
* BUSY    → mavi  (işleniyor / aktif çalışma)
* ERROR   → kırmızı (bağlantı/hata)
* SUCCESS → yeşil; TAM ``SUCCESS_MS`` (12 sn) kalır, sonra idle'a döner.
  Süre dolmadan yeni mesaj gelirse (BUSY) sayaç anında iptal edilir.
* IDLE    → düşük opaklıkta nötr ton + yavaş "nefes alma" animasyonu.
"""
from __future__ import annotations

import logging
import math
from enum import Enum

from PySide6.QtCore import (
    QEasingCurve,
    QObject,
    QRectF,
    Qt,
    QTimer,
    QVariantAnimation,
    Signal,
)
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QVBoxLayout, QWidget

logger = logging.getLogger(__name__)


class AppState(str, Enum):
    """Uygulama geneli durum (çerçeve rengini besler)."""

    IDLE = "idle"
    BUSY = "busy"
    ERROR = "error"
    SUCCESS = "success"


class StatusColorController(QObject):
    """Durumu yumuşak renk geçişine çeviren merkezi kontrolör.

    JARVIS StatusBorderWidget ve ATLAS overlay aynı controller'ı paylaşır;
    böylece iki ekran aynı durum renginde kalır (kod tekrarı yok).
    """

    color_changed = Signal(object)  # QColor — her ara karede
    state_changed = Signal(str)     # AppState.value

    SUCCESS_MS = 12_000   # yeşil kalma süresi (ms)
    TRANSITION_MS = 500   # yumuşak renk geçişi (ms)
    BREATH_MS = 2_600     # nefes yarım-döngüsü (ms) — tam tur 2× bu süre
    BREATH_TICK_MS = 40   # nefes zamanlayıcı adımı (~25 fps, hafif)

    COLORS = {
        AppState.IDLE:    QColor("#aebfce"),  # nötr/loş gri-beyaz (varsayım)
        AppState.BUSY:    QColor("#3d8bfd"),  # mavi
        AppState.ERROR:   QColor("#ff4455"),  # kırmızı
        AppState.SUCCESS: QColor("#2fe08a"),  # yeşil
    }
    BASE_ALPHA = {
        AppState.IDLE: 110,    # loş + nefes payı eklenir
        AppState.BUSY: 235,    # net ama göz yormayan
        AppState.ERROR: 235,
        AppState.SUCCESS: 235,
    }

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._state = AppState.IDLE
        self._color = self._base_color(AppState.IDLE)
        self._breath = 0.0

        self._transition = QVariantAnimation(self)
        self._transition.setDuration(self.TRANSITION_MS)
        self._transition.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._transition.valueChanged.connect(self._on_transition_value)

        self._success_timer = QTimer(self)
        self._success_timer.setSingleShot(True)
        self._success_timer.timeout.connect(self._on_success_elapsed)

        # Nefes animasyonu: QTimer + kosinüs fazı. (QVariantAnimation ping-pong
        # yerine; PySide6'da AlternateForward yönü her sürümde bulunmayabilir →
        # platformdan bağımsız, yumuşak çözüm.)
        self._breath_phase = 0.0
        self._breath_timer = QTimer(self)
        self._breath_timer.setInterval(self.BREATH_TICK_MS)
        self._breath_timer.timeout.connect(self._tick_breath)
        self._breath_timer.start()

    # ── Durum makinesi ─────────────────────────────────────────────────────
    @property
    def state(self) -> AppState:
        """Mevcut durum."""
        return self._state

    @property
    def color(self) -> QColor:
        """Görünen anlık çerçeve rengi (idle'da nefes payı dahil)."""
        color = QColor(self._color)
        if self._state is AppState.IDLE:
            color.setAlpha(max(0, min(255, color.alpha() + self._breath_delta())))
        return color

    def set_state(self, state) -> None:
        """Yeni duruma geç; SUCCESS her girişte12 sn sayacını (yeniden) başlatır.

        BUSY/ERROR/IDLE'a geçiş var olan success sayacını iptal eder — yeni
        mesaj gönderildiğinde kullanıcı12 sn yeşil için beklemez.
        """
        try:
            state = AppState(state)
        except ValueError:
            logger.warning("[StatusBorder] Bilinmeyen durum yok sayıldı: %r", state)
            return
        if state is AppState.SUCCESS:
            self._success_timer.start(self.SUCCESS_MS)
        else:
            self._success_timer.stop()
        if state is self._state:
            return
        self._state = state
        self._transition.stop()
        self._transition.setStartValue(QColor(self._color))
        self._transition.setEndValue(self._base_color(state))
        self._transition.start()
        self.state_changed.emit(state.value)
        logger.debug("[StatusBorder] Durum: %s", state.value)

    def notify_idle(self) -> None:
        """"idle" bildirimi — success beklemesindeyken yeşili KORUR (12 sn kuralı)."""
        if self._state is not AppState.SUCCESS:
            self.set_state(AppState.IDLE)

    @classmethod
    def _base_color(cls, state: AppState) -> QColor:
        """Durumun tam opaklık-ayarlı hedef rengi."""
        color = QColor(cls.COLORS[state])
        color.setAlpha(cls.BASE_ALPHA[state])
        return color

    def _on_success_elapsed(self) -> None:
        """12 sn doldu → idle'a yumuşak geç."""
        if self._state is AppState.SUCCESS:
            self.set_state(AppState.IDLE)

    def _on_transition_value(self, value) -> None:
        self._color = QColor(value)
        self.color_changed.emit(self.color)

    def _tick_breath(self) -> None:
        """Nefes fazını ilerlet (tam tur = 2 × BREATH_MS, yumuşak kosinüs 0→1→0)."""
        self._breath_phase += 2.0 * math.pi * (
            self.BREATH_TICK_MS / (2.0 * self.BREATH_MS)
        )
        if self._breath_phase >= 2.0 * math.pi:
            self._breath_phase %= 2.0 * math.pi
        self._breath = (1.0 - math.cos(self._breath_phase)) / 2.0
        if self._state is AppState.IDLE:
            self.color_changed.emit(self.color)

    def _breath_delta(self) -> int:
        """Idle nefes payı: 0..45 opaklık adımı (yumuşak sinüs eğrisi)."""
        return int(45.0 * self._breath)


# ─────────────────────────────────────────────────────────────────────────────
class StatusBorderWidget(QWidget):
    """İçeriği saran ince, yuvarlatılmış, duruma göre renk değiştiren çerçeve.

    Farklı ekranlarda yeniden kullanılabilir: bir ``StatusColorController``
    verilir, widget yalnızca mevcut rengi çizer.
    """

    BORDER_WIDTH = 4     # sağ kenar ve DPI ölçeklemesinde de görünür kalır (px)
    CORNER_RADIUS = 16   # oval köşe (px)
    CONTENT_INSET = BORDER_WIDTH + 2

    def __init__(self, controller: StatusColorController, parent: QWidget | None = None):
        super().__init__(parent)
        self._controller = controller
        self._controller.color_changed.connect(self._on_color_changed)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(
            self.CONTENT_INSET, self.CONTENT_INSET,
            self.CONTENT_INSET, self.CONTENT_INSET,
        )
        self._layout.setSpacing(0)

    @property
    def controller(self) -> StatusColorController:
        """Bağlı durum controller'ı."""
        return self._controller

    def set_content(self, widget: QWidget) -> None:
        """Çerçevenin içine yerleştirilecek içerik widget'ını ekle."""
        self._layout.addWidget(widget)

    def _on_color_changed(self, _color) -> None:
        self.update()

    def paintEvent(self, event) -> None:
        """Yumuşak renkli, yuvarlatılmış çerçeve çiz (hata olursa logla, çökme)."""
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            pen = QPen(self._controller.color, self.BORDER_WIDTH)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            half = self.BORDER_WIDTH / 2.0 + 1.0
            rect = QRectF(self.rect()).adjusted(half, half, -half, -half)
            painter.drawRoundedRect(rect, self.CORNER_RADIUS, self.CORNER_RADIUS)
        except Exception:
            logger.exception("[StatusBorder] Çerçeve çizilemedi")
        finally:
            painter.end()
        super().paintEvent(event)
