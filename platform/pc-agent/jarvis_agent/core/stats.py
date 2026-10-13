"""Canlı sistem istatistikleri — psutil tabanlı arka plan monitörü."""
from __future__ import annotations

import datetime
import logging
import threading
import time
from pathlib import Path
from typing import Any, Optional

import psutil

logger = logging.getLogger("jarvis.stats")

_POLL_SECONDS = 2.0


def _disk_path() -> str:
    """Kullanıcı dizininin bulunduğu disk bölümü (Windows: C:\\, POSIX: /)."""
    return str(Path.home().anchor or "/")


def compute_load_level(cpu_percent: float, mem_percent: float) -> str:
    """Sistem yükü seviyesi: 'low' | 'medium' | 'high'."""
    score = max(cpu_percent, mem_percent * 0.8)
    if score < 40.0:
        return "low"
    if score < 75.0:
        return "medium"
    return "high"


class StatsMonitor:
    """CPU/RAM/disk değerlerini arka plan iş parçacığında örnekler.

    ``snapshot()`` her zaman anında döner (kilit altında kopyalanmış önbellek);
    REST ve WebSocket uçları bunu okur. İlk örnek interval'li alınır, sonrakiler
    interval'siz (son 2 saniyenin ortalaması) — böylece çağrıyı bloklamaz.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._snapshot: dict[str, Any] = {}
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._started_at = time.time()

    # ── Yaşam döngüsü ──
    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        # İlk örnek senkron ve interval'siz (anında döner, ilk değer ~0):
        # aksi halde start() sonrası ilk ~1 saniye snapshot boş kalır ve
        # ilk istekler / testler boş veri görürdü. Arka plan iş parçacığı
        # bir sonraki turda interval'li örnekle değerleri düzeltir.
        self._sample(interval=None)
        self._thread = threading.Thread(
            target=self._run, name="jarvis-stats", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def _run(self) -> None:
        self._sample(interval=0.8)  # ilk örnek: interval'li → doğru ilk değer
        while not self._stop_event.wait(_POLL_SECONDS):
            self._sample(interval=None)

    # ── Örnekleme ──
    def _sample(self, interval: Optional[float]) -> None:
        try:
            cpu_percent = psutil.cpu_percent(interval=interval)
            cpu_freq = psutil.cpu_freq()
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage(_disk_path())
            boot = datetime.datetime.fromtimestamp(psutil.boot_time())
            snapshot = {
                "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
                "cpu": {
                    "percent": round(cpu_percent, 1),
                    "physical_cores": psutil.cpu_count(logical=False) or 0,
                    "logical_cores": psutil.cpu_count(logical=True) or 0,
                    "freq_mhz": round(cpu_freq.current, 0) if cpu_freq else None,
                },
                "memory": {
                    "total_gb": round(mem.total / 1024**3, 2),
                    "used_gb": round(mem.used / 1024**3, 2),
                    "percent": round(mem.percent, 1),
                },
                "disk": {
                    "total_gb": round(disk.total / 1024**3, 2),
                    "used_gb": round(disk.used / 1024**3, 2),
                    "percent": round(disk.percent, 1),
                },
                "uptime_seconds": int(time.time() - psutil.boot_time()),
                "boot_time": boot.isoformat(timespec="seconds"),
                "load_level": compute_load_level(cpu_percent, mem.percent),
            }
            with self._lock:
                self._snapshot = snapshot
        except Exception:  # psutil hataları uygulamayı düşürmemeli
            logger.exception("Sistem istatistiği örneklenemedi")

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._snapshot)

    @property
    def uptime_seconds(self) -> float:
        return time.time() - self._started_at
