"""Fast local routing for chat, factual questions, and web-grounded requests."""
from __future__ import annotations

import re
from enum import Enum


class AIRequestType(str, Enum):
    CHAT = "chat"
    KNOWLEDGE = "knowledge"
    WEB_SEARCH = "web_search"


_FOLD = str.maketrans({
    "ç": "c", "ğ": "g", "ı": "i", "ö": "o", "ş": "s", "ü": "u",
    "â": "a", "î": "i", "û": "u", "İ": "i",
})

_CONVERSATIONAL_PREFIXES = (
    "selam", "merhaba", "gunaydin", "iyi aksamlar", "iyi geceler",
    "naber", "ne haber", "nasilsin", "tesekkur", "sag ol",
    "espri yap", "saka yap", "komik bir sey", "bir hikaye anlat",
    "hikaye anlat", "masal anlat", "fikra anlat", "bilmece sor",
    "bana kisa bir hikaye", "bana bir hikaye", "bana bir fikra",
    "bugun nasilsin",
)

_WEB_SEARCH_TERMS = (
    "internetten ara", "internette ara", "webden ara", "webde ara",
    "web sitesinde ara", "internetten bak", "webden bak", "webde bak",
    "internetten kontrol et", "internet uzerinden kontrol et",
    "webden kontrol et", "webde kontrol et",
    "kaynaklariyla", "kaynaklariyla birlikte", "kaynak goster",
    "guncel bilgi", "guncel olarak", "en son", "son dakika",
    "su anki", "su an", "bugun", "dun", "bu hafta", "bu ay",
    "2026", "guncel", "haber", "gundem",
)

_QUESTION_STARTS = (
    "ne ", "nedir", "nasil ", "neden ", "niye ", "kim ", "kimdir",
    "hangi ", "kac ", "ne zaman", "nerede ", "nereden ",
)

_INFORMATION_REQUESTS = (
    "bilgi ver", "anlat", "acikla", "ogret", "ozetle", "karsilastir",
    "farklari", "hakkinda bilgi", "ne ise yarar", "nasil calisir",
    "tarihcesi", "anlami", "ornek ver",
)


def _normalize(text: str) -> str:
    value = (text or "").lower().replace("\u0307", "").translate(_FOLD)
    return " ".join(re.sub(r"[^\w\s]", " ", value).split())


def classify_ai_request(text: str) -> AIRequestType:
    """Route small talk to Groq, factual questions to Gemini, and current asks to Search."""
    has_question_mark = "?" in (text or "")
    normalized = _normalize(text)
    if not normalized:
        return AIRequestType.CHAT

    if any(
        normalized == prefix or normalized.startswith(prefix + " ")
        for prefix in _CONVERSATIONAL_PREFIXES
    ):
        return AIRequestType.CHAT

    if any(term in normalized for term in _WEB_SEARCH_TERMS):
        return AIRequestType.WEB_SEARCH

    if has_question_mark or any(
        normalized.startswith(prefix) for prefix in _QUESTION_STARTS
    ):
        return AIRequestType.KNOWLEDGE

    if any(term in normalized for term in _INFORMATION_REQUESTS):
        return AIRequestType.KNOWLEDGE

    return AIRequestType.CHAT
