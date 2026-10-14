"""Türkçe metin normalizasyonu ve bulanık ifade eşleştirme.

Uyandırma ifadeleri ("Hey Jarvis", "Uyan bakalım baba eve geldi") STT
çözülmüş metinle karşılaştırılır; STT hataları (ör. "hey carvis") için
Levenshtein tabanlı tolerans kullanılır.
"""
from __future__ import annotations

import re
import unicodedata

_TR_MAP = str.maketrans({
    "İ": "i", "I": "ı", "Ş": "ş", "Ğ": "ğ", "Ü": "ü", "Ö": "ö", "Ç": "ç",
})

# Yaygın STT karıştırmaları (ses benzerliği)
_PHONETIC = [
    (re.compile(r"j[aâ]?r[vf]i[szş]"), "jarvis"),
    (re.compile(r"he+y"), "hey"),
]


def normalize(text: str) -> str:
    """Türkçe duyarlı küçük harf + noktalama temizliği + boşluk sıkıştırma."""
    text = text or ""
    text = text.translate(_TR_MAP)
    # Türkçe olmayan aksanları katla (ör. 'jârvis' → 'jarvis')
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.replace("ı", "ı")  # korunur
    text = text.lower()
    text = re.sub(r"[^a-zçğıöşü0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# Yazılı moddan sesli moda geçiş ifadeleri (gereklim 5.4: "Jarvis sesli moda geç")
_ENTER_VOICE_PATTERNS = [
    "sesli moda gec",
    "sesli moda gir",
    "sesli moda gece",
    "sesli moda ec",
    "sesli mod ac",
    "sesli konusmaya gec",
    "sesle gec",
    "mikrofonu ac",
]


def is_enter_voice_command(text: str) -> bool:
    """Yazılı/sözlü metnin "sesli moda geç" isteği olup olmadığı.

    "jarvis sesli moda geç" gibi cümlelerde komutun içinde "jarvis" olup
    olmamasına bakılmaz; ifade yeterli (uyarılmış bağlam varsayılır).
    """
    n = normalize(text)
    if not n:
        return False
    for pattern in _ENTER_VOICE_PATTERNS:
        if match_phrase(n, pattern, threshold=0.80):
            return True
        if pattern in n:
            return True
    return False


def levenshtein(a: str, b: str) -> int:
    """Klasik DP Levenshtein — kısa dizgeler için yeterince hızlı."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def similarity(a: str, b: str) -> float:
    """0..1 arası benzerlik (1 = aynı)."""
    if not a and not b:
        return 1.0
    dist = levenshtein(a, b)
    return 1.0 - dist / max(len(a), len(b), 1)


def match_phrase(text: str, phrase: str, threshold: float = 0.82) -> bool:
    """`text` içinde `phrase` geçiyor mu? (bulanık, taşma tolere edilir).

    STT genelde fazladan kelime üretir ("hey jarvis evet" gibi); bu yüzden
    tüm metin karşılaştırmasına ek olarak kayan pencere eşleşmesi yapılır.
    """
    n_text = normalize(text)
    n_phrase = normalize(phrase)
    for pattern, repl in _PHONETIC:
        n_text = pattern.sub(repl, n_text)
        n_phrase = pattern.sub(repl, n_phrase)
    if not n_text or not n_phrase:
        return False

    if n_phrase in n_text:
        return True
    if similarity(n_text, n_phrase) >= threshold:
        return True

    # Kayan pencere: ifade uzunluğu ± 2 kelime dilimlerinde aranır
    words = n_text.split()
    plen = len(n_phrase.split())
    if plen == 0:
        return False
    for size in (plen, plen + 1, plen + 2, max(plen - 1, 1)):
        if size > len(words):
            continue
        for start in range(0, len(words) - size + 1):
            window = " ".join(words[start:start + size])
            if similarity(window, n_phrase) >= threshold:
                return True
    return False
