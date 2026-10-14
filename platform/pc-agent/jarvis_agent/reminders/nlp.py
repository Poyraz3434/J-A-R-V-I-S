"""Türkçe doğal dilden hatırlatıcı zamanı ayrıştırma.

Örnekler: "5 dakika sonra", "2 saat sonra", "yarın 9'da", "yarın sabah 8'de",
"bugün 15:30", "9:30'da", "pazartesi 10'da", "13:00'te".
"""
from __future__ import annotations

import datetime
import re
from typing import Optional

_NUMBER_WORDS = {
    "bir": 1, "iki": 2, "üç": 3, "dört": 4, "beş": 5, "altı": 6,
    "yedi": 7, "sekiz": 8, "dokuz": 9, "on": 10, "on beş": 15, "yirmi": 20,
    "otuz": 30, "kırk": 40, "elli": 50,
}
_WEEKDAYS = {
    "pazartesi": 0, "salı": 1, "çarşamba": 2, "perşembe": 3,
    "cuma": 4, "cumartesi": 5, "pazar": 6,
}
_DAY_PARTS = {"sabah": 6, "öğlen": 12, "öğle": 12, "akşam": 19, "gece": 21}


def _num(token: str) -> Optional[float]:
    token = token.strip()
    try:
        return float(token.replace(",", "."))
    except ValueError:
        pass
    return _NUMBER_WORDS.get(token)


def _hour(text: str) -> Optional[tuple[int, int]]:
    """Metinden saat:dakika çıkarır; yoksa None."""
    m = re.search(r"(\d{1,2})[:.](\d{2})", text)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"saat\s+(\d{1,2})\s*'(?:de|da|te|ta)?", text)
    if m:
        return int(m.group(1)), 0
    for word, val in _NUMBER_WORDS.items():
        m = re.search(rf"(?:saat\s+)?{word}\s*(?:'?(?:de|da|te|ta)|buçuk)?\b", text)
        if m and ("saat" in text or "buçuk" in text):
            minute = 30 if "buçuk" in text else 0
            if "saat" in m.group(0) or "buçuk" in text:
                return val, minute
    return None


def parse_reminder(text: str, now: Optional[datetime.datetime] = None) -> Optional[dict]:
    """Serbest metinden {title, due_at} çıkarır; zaman bulunamazsa None."""
    now = now or datetime.datetime.now()
    t = text.lower().strip()
    due: Optional[datetime.datetime] = None

    # 1) "X dakika/saat/gün sonra"
    m = re.search(r"(\d+|[a-zçğıöşü ]+?)\s*(dakika|dk|saat|gün|günü)\s+sonra", t)
    if m:
        val = _num(m.group(1))
        if val is not None:
            unit = m.group(2)
            delta = (
                datetime.timedelta(minutes=val) if unit in ("dakika", "dk")
                else datetime.timedelta(hours=val) if unit == "saat"
                else datetime.timedelta(days=val)
            )
            due = now + delta

    # 2) "yarım saat sonra"
    if due is None and "yarım saat" in t:
        due = now + datetime.timedelta(minutes=30)

    # 3) Hafta günü + saat
    if due is None:
        for day_name, day_idx in _WEEKDAYS.items():
            if day_name in t:
                hh = _hour(t)
                hour, minute = hh if hh else (9, 0)
                days_ahead = (day_idx - now.weekday()) % 7
                if days_ahead == 0:
                    days_ahead = 7
                due = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                due += datetime.timedelta(days=days_ahead)
                if "saat" not in t and hh is None:
                    due = due  # varsayılan 09:00
                break

    # 4) "yarın/bugün" + saat
    if due is None and ("yarın" in t or "bugün" in t or _hour(t)):
        hh = _hour(t)
        if hh or _daypart(t):
            hour, minute = hh if hh else (_daypart(t), 0)
            due = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if "yarın" in t:
                due += datetime.timedelta(days=1)
            elif due <= now:
                due += datetime.timedelta(days=1)  # geçmiş saat → yarın

    if due is None:
        return None

    # Başlık: metinden zaman ifadelerini soy
    title = text.strip()
    noise = re.compile(
        r"\b(\d+[:.]\d{2}|\d+\s*(dakika|dk|saat|gün)\s*sonra|yarım saat|"
        r"yarın|bugün|hatırlat|hatırlatma|kur|kurar mısın|ayarla|beni|"
        r"pazartesi|salı|çarşamba|perşembe|cuma|cumartesi|pazar|"
        r"saat\s+\S+|sabah|öğlen|akşam|gece)\b", re.IGNORECASE)
    cleaned = noise.sub("", title)
    cleaned = re.sub(r"[\s']*'(?:de|da|te|ta)\s*", " ", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ,.!'\"?")
    title = cleaned if len(cleaned) >= 2 else text.strip()[:80]

    return {"title": title, "due_at": due}


def _daypart(t: str) -> Optional[int]:
    for part, hour in _DAY_PARTS.items():
        if part in t:
            return hour
    return None


# Kısa takma ad — tools.py ve diğer çağıranlar için
parse = parse_reminder
