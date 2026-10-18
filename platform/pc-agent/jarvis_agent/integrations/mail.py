"""E-posta kontrolü — IMAP üzerinden salt-okunur okuma.

Güvenlik: yalnızca INBOX'tan okunmamış mesajlar listelenir; silme, yanıt,
taşıma gibi yıkıcı işlemler bilinçli olarak YOKTUR (gereksinim 5.3).
Şifre ortam değişkeninden (JARVIS_IMAP_PASSWORD) okunur.
"""
from __future__ import annotations

import email
import email.policy
import imaplib
import ssl
from .. import config


def available() -> bool:
    host = config.env("JARVIS_IMAP_HOST", "")
    user = config.env("JARVIS_IMAP_USER", "")
    password = config.env("JARVIS_IMAP_PASSWORD", "")
    return bool(host and user and password)


def fetch_unread(limit: int = 5) -> dict:
    """Okunmamış son mesajları listeler (mesajlar okundu işaretlenmez)."""
    if not available():
        return {
            "available": False,
            "error": "E-posta yapılandırılmadı. JARVIS_IMAP_HOST / USER / PASSWORD gerekli.",
        }
    limit = max(1, min(int(limit or 5), 20))
    host = config.env("JARVIS_IMAP_HOST", "")
    user = config.env("JARVIS_IMAP_USER", "")
    password = config.env("JARVIS_IMAP_PASSWORD", "")

    messages: list[dict] = []
    conn: imaplib.IMAP4_SSL | None = None
    try:
        context = ssl.create_default_context()
        conn = imaplib.IMAP4_SSL(host, 993, ssl_context=context)
        conn.login(user, password)
        conn.select("INBOX", readonly=True)  # salt-okunur: hiçbir şey değişmez
        status, data = conn.search(None, "UNSEEN")
        if status != "OK":
            return {"available": True, "messages": []}

        ids = data[0].split()[-limit:]  # en yeni N
        for mid in reversed(ids):  # en yeniden eskiye
            status, msg_data = conn.fetch(mid, "(RFC822)")
            if status != "OK" or not msg_data or msg_data[0] is None:
                continue
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw, policy=email.policy.default)
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        try:
                            body = part.get_content()
                        except Exception:
                            body = ""
                        break
            else:
                try:
                    body = msg.get_content()
                except Exception:
                    body = ""
            messages.append(
                {
                    "from": str(msg.get("From", "")),
                    "subject": str(msg.get("Subject", "(konu yok)")),
                    "date": str(msg.get("Date", "")),
                    "snippet": " ".join(str(body).split())[:200],
                }
            )
        return {"available": True, "messages": messages}
    except imaplib.IMAP4.error as exc:
        return {"available": True, "error": f"Giriş başarısız: {exc}"}
    except (OSError, Exception) as exc:  # ağ/SSL sorunları
        return {"available": True, "error": f"Sunucuya ulaşılamadı: {exc}"}
    finally:
        try:
            if conn is not None:
                conn.logout()
        except Exception:
            pass


# ── Gönderim (SMTP) — yalnızca açık yapılandırmayla ──────────────────────────
def can_send() -> bool:
    host = config.env("JARVIS_SMTP_HOST", "")
    user = config.env("JARVIS_SMTP_USER", "")
    password = config.env("JARVIS_SMTP_PASSWORD", "") or config.env("JARVIS_SMTP_PASS", "")
    return bool(host and user and password)


def send_available() -> bool:
    host = config.env("JARVIS_SMTP_HOST", "")
    user = config.env("JARVIS_SMTP_USER", "")
    password = config.env("JARVIS_SMTP_PASSWORD", "") or config.env("JARVIS_SMTP_PASS", "")
    return bool(host and user and password)


def send_email(to: str, subject: str, body: str) -> dict:
    """Kullanıcının kendi hesabından kısa bir e-posta gönderir (SMTP).

    Güvenlik: yalnızca düz metin; ek yok (gereksinim 5.3 — kullanıcı onayı
    olmadan veri dışarı sızmasın). Şifre ortam değişkeninden okunur.
    """
    import smtplib
    from email.message import EmailMessage

    host = config.env("JARVIS_SMTP_HOST", "")
    port = int(config.env("JARVIS_SMTP_PORT", "587") or 587)
    user = config.env("JARVIS_SMTP_USER", "")
    password = config.env("JARVIS_SMTP_PASSWORD", "") or config.env("JARVIS_SMTP_PASS", "")
    if not (host and user and password):
        return {
            "error": "E-posta gönderimi yapılandırılmadı. "
            "JARVIS_SMTP_HOST / USER / PASSWORD gerekli."
        }
    if not to or "@" not in to:
        return {"error": "Geçersiz alıcı adresi."}

    msg = EmailMessage()
    msg["From"] = user
    msg["To"] = to.strip()
    msg["Subject"] = subject.strip()[:200] or "(konu yok)"
    msg.set_content(body[:20000])

    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=15) as server:
                server.login(user, password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=15) as server:
                server.starttls()
                server.login(user, password)
                server.send_message(msg)
        return {"sent": True, "to": to, "subject": msg["Subject"]}
    except smtplib.SMTPAuthenticationError as exc:
        return {"error": f"SMTP girişi başarısız: {exc}"}
    except Exception as exc:
        return {"error": f"E-posta gönderilemedi: {exc}"}
