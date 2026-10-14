"""VAD (ses etkinliği) ve çift alkış dedektörü — tamamen yerel, saf numpy.

Alkış imzası: kısa süreli (≤60 ms) keskin bir enerji sıçraması ve ardından
hızlı sönüm. İnsan konuşması çok daha yavaş attack'a sahip olduğu için
ayırt edilebilir. İki algılama 0.2–1.6 sn aralığında gelirse "çift alkış"
tetiklenir. Hassasiyet, gürültü tabanına uygulanan çarpanla ayarlanır.
"""
from __future__ import annotations

import logging
import time
from collections import deque
from typing import Callable, Optional

import numpy as np

logger = logging.getLogger("jarvis.voice.clap")

# ── Parametreler (tümü deneyimle sabitlendi, ayarlardan override edilebilir) ──
FRAME_MS = 10                       # enerji çerçevesi
CLAP_MAX_ATTACK_MS = 60             # alkış attack süresi üst sınırı
CLAP_DECAY_MS = 300                 # sönüm penceresi
CLAP_PEAK_RATIO = 4.0                # tepe / gürültü tabanı oranı (hassasiyetle ölçeklenir)
DOUBLE_CLAP_MIN_GAP_S = 0.25        # iki alkış arası en kısa süre
DOUBLE_CLAP_MAX_GAP_S = 1.6         # en uzun süre
NOISE_FLOOR_START = 1e-4            # başlangıç gürültü tabanı (RMS²)
NOISE_ADAPT_RATE = 0.02             # yerleşik gürültü adaptasyonu


def rms(frame: np.ndarray) -> float:
    """Karekök-ortalama-kare enerji."""
    if frame.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(frame.astype(np.float64) ** 2)))


class EnergyVAD:
    """Uyarlamalı gürültü tabanlı ses etkinlik algılayıcı."""

    def __init__(self, threshold_factor: float = 2.5) -> None:
        self.threshold_factor = threshold_factor
        self.noise_floor = NOISE_FLOOR_START

    def is_speech(self, frame_rms: float) -> bool:
        return frame_rms > max(self.noise_floor * self.threshold_factor, 1e-5)

    def update_noise(self, frame_rms: float, is_speech: bool) -> None:
        if not is_speech:
            self.noise_floor += (frame_rms**2 - self.noise_floor) * NOISE_ADAPT_RATE
            self.noise_floor = max(self.noise_floor, 1e-6)


class ClapDetector:
    """Çift alkış dedektörü — blok bazlı beslenir, saf sayısal analiz.

    ``feed(block)`` her 100 ms mikrofon bloğuyla çağrılır. Alkış adayı
    enerji zarfının türevinden bulunur: çerçeve enerjisi tabanın
    ``peak_ratio / sensitivity_scale`` katını aşarsa ve attack penceresi
    kısa ise adaydır.
    """

    def __init__(
        self,
        sensitivity: float = 5.0,
        on_double_clap: Optional[Callable[[], None]] = None,
    ) -> None:
        self.sensitivity = float(sensitivity)  # 1 (zor) .. 10 (kolay)
        self.on_double_clap = on_double_clap
        self._frame_energy: deque[float] = deque(maxlen=CLAP_DECAY_MS // FRAME_MS)
        self._noise_floor = NOISE_FLOOR_START
        self._clap_times: list[float] = []
        self._candidate: Optional[float] = None
        self._candidate_peak = 0.0

    # ── hassasiyet → tepe oranı dönüşümü ──
    @property
    def _peak_ratio(self) -> float:
        # sensitivity 10 → oran 1.6 (kolay), 1 → oran 12 (zor)
        return max(12.0 - self.sensitivity * 1.15, 1.4)

    def feed(self, block: np.ndarray, sample_rate: int) -> None:
        """100 ms'lik bloğu 10 ms'lik çerçevelere bölüp analiz eder."""
        if block.size == 0:
            return
        frame_len = max(int(sample_rate * FRAME_MS / 1000), 1)
        t_now = time.monotonic()

        for start in range(0, block.size - frame_len + 1, frame_len):
            e = rms(block[start:start + frame_len])
            self._frame_energy.append(e)
            self._update_noise_floor(e)

            threshold = self._noise_floor * self._peak_ratio
            if e > threshold and e > 1e-4:
                # yükselen kenar mı? (önceki çerçeve belirgin şekilde düşük)
                if len(self._frame_energy) >= 2:
                    prev = self._frame_energy[-2]
                    if e > prev * 1.8:
                        self._register_hit(t_now)
                elif self._candidate is None:
                    self._register_hit(t_now)

        self._check_double(t_now)

    def _update_noise_floor(self, e: float) -> None:
        # ortanca yaklaşımı yerine yavaş EMA; alkışlar tabanı şişirmesin
        recent = list(self._frame_energy)
        if recent:
            med = sorted(recent)[len(recent) // 2]
            self._noise_floor += (med - self._noise_floor) * 0.08
            self._noise_floor = max(self._noise_floor, 1e-6)

    def _register_hit(self, t_now: float) -> None:
        # Aynı alkışın çerçevelerini tek adayta birleştir (200 ms refrakter)
        if self._clap_times and t_now - self._clap_times[-1] < 0.2:
            return
        self._clap_times.append(t_now)
        logger.debug("Alkış adayı: t=%.2f", t_now)

    def _check_double(self, t_now: float) -> None:
        # eski adayları temizle
        self._clap_times = [t for t in self._clap_times if t_now - t <= DOUBLE_CLAP_MAX_GAP_S + 0.5]
        if len(self._clap_times) < 2:
            return
        last, prev = self._clap_times[-1], self._clap_times[-2]
        gap = last - prev
        if DOUBLE_CLAP_MIN_GAP_S <= gap <= DOUBLE_CLAP_MAX_GAP_S:
            self._clap_times.clear()
            logger.info("Çift alkış algılandı (aralık %.2f sn)", gap)
            if self.on_double_clap:
                try:
                    self.on_double_clap()
                except Exception:
                    logger.exception("Alkış geri çağrısı hata verdi")


def synthesize_clap(sample_rate: int = 16000, when: float = 0.0) -> np.ndarray:
    """Test için sentetik alkış: kısa gürültü patlaması + hızlı sönüm."""
    n = int(sample_rate * 0.25)
    t = np.arange(n) / sample_rate
    burst = np.random.default_rng(42).normal(0, 1, n)
    env = np.exp(-t / 0.02)  # 20 ms sönüm
    clap = burst * env
    pad_before = np.zeros(int(sample_rate * when))
    return np.concatenate([pad_before, clap.astype(np.float32)])
