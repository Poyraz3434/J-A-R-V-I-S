"""Özellik 9 — Prompt Mimarı: başka yapay zekalara verilecek detaylı prompt üretimi.

8 maddelik kalite kontrol listesi (checklist) — her üretilen prompt'ta bulunmalı:
  1) Rol/bağlam  2) Görev (adım adım)  3) Kısıtlar  4) Varsayımlar
  5) Kenar durumlar  6) Çıktı formatı  7) Örnek/şablon  8) Test/doğrulama kriterleri

Tetikleme: "şunun için prompt yaz", "detaylı prompt oluştur" (bilgi sorusu
"prompt nedir?" TETİKLEMEZ — normal cevap verilir).

Üretim: LLM varsa ondan, yoksa tam yapılandırılmış şablon; her iki durumda da
``checklist_quality`` ile kendini denetler, eksik bölümler şablondan tamamlanır.
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# (anahtar, başlık deseni) — checklist denetimi bu başlıklara bakar
CHECKLIST_SECTIONS = (
    ("role", r"^#+\s*.*\bROL\b|^\*\*ROL"),
    ("task", r"^#+\s*.*\bG[ÖO]REV\b|^\*\*G[ÖO]REV"),
    ("constraints", r"^#+\s*.*KISIT|^\*\*KISIT"),
    ("assumptions", r"^#+\s*.*VARSAYIM|^\*\*VARSAYIM"),
    ("edge", r"^#+\s*.*KENAR|^\*\*KENAR"),
    ("output", r"^#+\s*.*ÇIKTI|^\*\*ÇIKTI"),
    ("example", r"^#+\s*.*[ÖO]RNEK|^\*\*[ÖO]RNEK"),
    ("criteria", r"^#+\s*.*TEST|KR[İI]TER|^\*\*TEST"),
)

_NEGATIVE = ("prompt nedir", "prompt ne demek", "prompt tanımı",
             "prompt nasıl çalışır", "prompt'un anlamı")
_TRIGGER = ("prompt yaz", "prompt oluştur", "prompt üret", "prompt modu",
            "detaylı prompt", "prompt hazırla", "için prompt",
            "prompt olarak")

PROMPT_ARCHITECT_SYSTEM = (
    "Sen kıdemli bir prompt mühendisisin. Kullanıcının verdiği iş için başka "
    "yapay zekalara verilmeye hazır, son derece detaylı ve yapılandırılmış bir "
    "prompt ÜRET (kendi cevabını değil, prompt metnini döndür). Her prompt'ta "
    "şu 8 bölüm MUTLAKA bulunmalı: (1) ROL: AI'ya kim olduğu/proje bağlamı, "
    "(2) GÖREV: adım adım net tanım, (3) KISITLAR: format/süre/ton/teknik, "
    "(4) VARSAYIMLAR: belirsiz noktalar için açık varsayımlar, "
    "(5) KENAR DURUMLAR ve ele alınışları, (6) ÇIKTI FORMATI, "
    "(7) ÖRNEK girdi-çıktı/şablon, (8) TEST KRİTERLERİ: başarılı sayılma "
    "koşulları. Yalnızca prompt metnini döndür."
)


def is_prompt_request(text: str) -> bool:
    """Kullanıcı prompt ÜRETİMİ mi istiyor (bilgi sorusu değil mi)?"""
    t = (text or "").lower()
    if not t:
        return False
    if any(neg in t for neg in _NEGATIVE):     # "prompt nedir" → istek değil
        return False
    return any(trig in t for trig in _TRIGGER)


def _sections_for(task: str) -> list[tuple[str, str]]:
    """8 bölümlük şablon (eksik olanları tamamlamak ve fallback için)."""
    return [
        ("role", "## ROL\nSen bu görev için çalışan kıdemli bir asistansın; "
                 f"iş: {task}. Bağlamı ve kısıtları dikkate alarak çalış."),
        ("task", "## GÖREV\n1. İstek madde madde uygula.\n2. Belirsiz noktaları "
                 "varsayımlarla doldur.\n3. Çıktıyı aşağıdaki formatta sun."),
        ("constraints", "## KISITLAR\n- Format: madde madde, net ve kısa.\n"
                        "- Ton: profesyonel, jargonsu mümkünse açıklayıcı.\n"
                        "- Uzunluk: gereksiz tekrar yok."),
        ("assumptions", "## VARSAYIMLAR\n- Yerel tarih/saat biçimi varsayılır.\n"
                        "- Kullanıcı teknik olmayan dil tercih eder."),
        ("edge", "## KENAR DURUMLAR\n- Bilgi eksikse uydurma; 'bilinmiyor' de.\n"
                 "- İstek çelişkiliyse önce çelişkiyi belirt."),
        ("output", "## ÇIKTI FORMATI\n- Başlık + numaralı adımlar + sonuç "
                   "bölümü; istenirse tablo/liste."),
        ("example", "## ÖRNEK\nGirdi: <kısa istek>\nÇıktı: <adım 1... adım n + "
                    "sonuç>"),
        ("criteria", "## TEST KRİTERLERİ\n- 8 bölümın tamamı var mı?\n"
                     "- Görev tek anlamlı mı?\n- Çıktı formata uyuyor mu?"),
    ]


def build_fallback_prompt(task: str) -> str:
    """LLM yoksa tam yapılandırılmış, kullanıma hazır prompt metni."""
    return "\n\n".join(body for _, body in _sections_for(task))


def checklist_quality(prompt_text: str) -> dict:
    """8 maddelik checklist denetimi: {anahtar: True/False}."""
    report = {}
    for key, pattern in CHECKLIST_SECTIONS:
        report[key] = bool(re.search(pattern, prompt_text or "",
                                     re.IGNORECASE | re.MULTILINE))
    return report


def generate_prompt(task: str, llm_fn=None) -> tuple[str, dict]:
    """Prompt üret + kendini denetle; eksik bölümleri şablondan tamamla.

    ``llm_fn(task, instruction, context) -> str`` opsiyoneldir.
    Döner: (prompt_metni, checklist_raporu) — raporda tümü True olana kadar
    en fazla bir tamamlama turu yapılır.
    """
    text = ""
    if llm_fn is not None:
        try:
            text = (llm_fn(task, PROMPT_ARCHITECT_SYSTEM, "") or "").strip()
        except Exception as exc:
            logger.warning("[PromptArchitect] LLM üretimi başarısız: %s", exc)
    if not text:
        text = build_fallback_prompt(task)
    report = checklist_quality(text)
    missing = [key for key, ok in report.items() if not ok]
    if missing:
        sections = dict(_sections_for(task))
        text += "\n\n" + "\n\n".join(
            sections[key] for key in missing)
        report = checklist_quality(text)
        logger.info("[PromptArchitect] Eksik bölümler tamamlandı: %s", missing)
    return text, report
