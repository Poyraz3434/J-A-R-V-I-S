"""Kimlik doğrulama çekirdeği (Bölüm B — madde 5 ve 16).

- JWT (HS256): access 15 dk, refresh 7 gün, reset 10 dk (config'ten).
- Şifreler ve güvenlik cevapları bcrypt ile hash'lenir (12 round).
- Hatalı giriş kilidi: LOGIN_MAX_FAILURES hatalı denemeden sonra
  LOGIN_BLOCK_SECONDS boyunca o hesap için login 429 döner.
Sırlar koda gömülmez: JARVIS_JWT_SECRET .env'den okunur (config.py).
"""
from __future__ import annotations

import datetime as dt
import re
import secrets
import threading
import time
from typing import Any, Optional

import bcrypt
import jwt

from . import config

_NAME_RE = re.compile(r"^[\wçğıöşüÇĞİÖŞÜ][\wçğıöşüÇĞİÖŞÜ\s.-]{1,39}$", re.UNICODE)
_BIRTH_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Oturumla birlikte üretilen geçici secret (restart'ta token'lar düşer).
_EPHEMERAL_SECRET = secrets.token_urlsafe(48)

# ── Hatalı giriş kilidi (bellek içi, kişisel kullanım) ───────────────────────
_lock_lock = threading.Lock()
_login_state: dict[str, dict[str, float]] = {}


class AuthError(Exception):
    """Kullanıcıya dönülebilir kimlik hatası (HTTP status ile)."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


# ── Şifre hash (bcrypt, madde 16: 12 round) ──────────────────────────────────

def hash_secret(plain: str) -> str:
    rounds = int(config.BCRYPT_ROUNDS)
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=rounds)).decode()


def verify_secret(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ── JWT ──────────────────────────────────────────────────────────────────────

def _secret() -> str:
    return config.AUTH_SECRET or _EPHEMERAL_SECRET


def make_token(user_id: str, token_type: str, ttl_seconds: int) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    payload = {
        "sub": user_id,
        "typ": token_type,
        "iat": now,
        "exp": now + dt.timedelta(seconds=ttl_seconds),
        "jti": secrets.token_urlsafe(8),  # tekil token kimliği
    }
    return jwt.encode(payload, _secret(), algorithm="HS256")


def issue_token_pair(user_id: str) -> dict[str, Any]:
    """Access + refresh token çifti üretir (madde 16: 15 dk / 7 gün)."""
    return {
        "access_token": make_token(user_id, "access", config.ACCESS_TOKEN_TTL_SECONDS),
        "refresh_token": make_token(user_id, "refresh", config.REFRESH_TOKEN_TTL_SECONDS),
        "token_type": "bearer",
        "expires_in": config.ACCESS_TOKEN_TTL_SECONDS,
    }


def decode_token(token: str, expected_type: Optional[str] = None) -> dict[str, Any]:
    """Token'ı doğrular; geçersizse AuthError fırlatır."""
    if not token:
        raise AuthError("Token boş.", 401)
    try:
        payload = jwt.decode(token, _secret(), algorithms=["HS256"])
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("Oturum süresi doldu.", 401) from exc
    except jwt.InvalidTokenError as exc:
        raise AuthError("Geçersiz token.", 401) from exc
    if expected_type and payload.get("typ") != expected_type:
        raise AuthError("Token türü uyuşmuyor.", 401)
    return payload


def bearer_of(request: Any) -> Optional[str]:
    """Authorization: Bearer <token> başlığından token'ı ayıklar."""
    header = ""
    try:
        header = str(request.headers.get("authorization") or "")
    except AttributeError:
        return None
    if header.lower().startswith("bearer "):
        token = header[7:].strip()
        return token or None
    return None


# ── Doğrulamalar ─────────────────────────────────────────────────────────────

def validate_name(value: str, label: str) -> str:
    cleaned = (value or "").strip()
    if not _NAME_RE.fullmatch(cleaned):
        raise AuthError(f"{label} 2-40 karakter olmalı ve geçersiz karakter içermemeli.", 422)
    return cleaned


def validate_birth_date(value: str) -> str:
    cleaned = (value or "").strip()
    if not _BIRTH_RE.fullmatch(cleaned):
        raise AuthError("Doğum tarihi YYYY-MM-DD biçiminde olmalı.", 422)
    try:
        dt.date.fromisoformat(cleaned)
    except ValueError as exc:
        raise AuthError("Doğum tarihi geçersiz.", 422) from exc
    return cleaned


def validate_password(value: str) -> str:
    if len(value or "") < 8:
        raise AuthError("Şifre en az 8 karakter olmalı.", 422)
    if len(value) > 128:
        raise AuthError("Şifre en fazla 128 karakter olabilir.", 422)
    return value


# ── Hatalı giriş kilidi (madde 16: 5 hata → 15 dk blok) ──────────────────────

def _lock_key(first_name: str, last_name: str) -> str:
    return f"{first_name.strip().lower()}|{last_name.strip().lower()}"


def check_not_locked(first_name: str, last_name: str) -> None:
    key = _lock_key(first_name, last_name)
    with _lock_lock:
        state = _login_state.get(key)
        if state and state.get("blocked_until", 0) > time.time():
            remaining = int(state["blocked_until"] - time.time())
            raise AuthError(
                f"Çok fazla hatalı giriş. {remaining} sn sonra tekrar deneyin.", 429
            )


def register_failure(first_name: str, last_name: str) -> None:
    key = _lock_key(first_name, last_name)
    with _lock_lock:
        state = _login_state.setdefault(key, {"fails": 0.0, "blocked_until": 0.0})
        state["fails"] = float(state.get("fails", 0)) + 1
        if state["fails"] >= config.LOGIN_MAX_FAILURES:
            state["blocked_until"] = time.time() + config.LOGIN_BLOCK_SECONDS
            state["fails"] = 0.0


def register_success(first_name: str, last_name: str) -> None:
    with _lock_lock:
        _login_state.pop(_lock_key(first_name, last_name), None)


def reset_login_locks() -> None:
    """Yalnızca testler/kurtarma için: tüm kilitleri temizler."""
    with _lock_lock:
        _login_state.clear()
