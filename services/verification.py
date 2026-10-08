"""Lightweight local risk verification for assistant actions."""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class VerificationResult:
    allowed: bool
    requires_confirmation: bool
    message: str = ""


class CommandVerifier:
    """Keeps high-impact actions behind an explicit user confirmation."""

    RISK_MARKERS = (
        "sil", "temizle", "gönder", "yazdır", "kısayol", "kur", "install",
        "whatsapp", "powershell", "cmd", "terminal", "şifre", "parola",
        "tıkla", "tikla", "klavyeye yaz", "aktif pencereye yaz", "alanına yaz", "dosya düzenle",
        "geri al", "rutini sil", "rutin sil", "sistem ayar",
        "ödeme yap", "satın al", "işlemi sonlandır", "process kill",
        "ağ bağlantısını kes", "programı kaldır", "uygulamayı kaldır",
    )

    def __init__(self, window_seconds: int = 120):
        self.window_seconds = window_seconds
        self._pending: tuple[str, float] | None = None
        self.failed_attempts = 0
        self.safe_mode = False

    def inspect(self, text: str) -> VerificationResult:
        normalized = " ".join((text or "").lower().split())
        if self.safe_mode:
            return VerificationResult(False, False, "Güvenli mod aktif. Kritik komutlar geçici olarak engellendi.")
        if self._pending and time.monotonic() - self._pending[1] > self.window_seconds:
            self._pending = None
        if self._pending:
            if normalized in {"onayla", "evet", "devam", "confirm", "yes"}:
                self._pending = None
                return VerificationResult(True, False)
            if normalized in {"iptal", "hayır", "vazgeç", "cancel", "no"}:
                self._pending = None
                return VerificationResult(False, False, "İşlem iptal edildi.")
        if any(marker in normalized for marker in self.RISK_MARKERS):
            digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:8]
            self._pending = (digest, time.monotonic())
            return VerificationResult(False, True, "Bu işlem için onay gerekiyor. Devam etmek için 'onayla' yazın.")
        return VerificationResult(True, False)

    @property
    def has_pending(self) -> bool:
        return self._pending is not None and time.monotonic() - self._pending[1] <= self.window_seconds

    def cancel_pending(self) -> None:
        self._pending = None

    def record_failure(self) -> None:
        self.failed_attempts += 1
        if self.failed_attempts >= 3:
            self.safe_mode = True

    def confirmation_failed(self) -> VerificationResult:
        self.record_failure()
        return VerificationResult(False, False, "Onay doğrulanamadı. Kritik işlemler geçici olarak kısıtlanabilir.")

    def reset(self) -> None:
        self.failed_attempts = 0
        self.safe_mode = False
        self._pending = None
