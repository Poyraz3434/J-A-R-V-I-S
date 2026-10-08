"""Özellik 8 — Müfredat bilgi katmanı + 3 saniyelik doğrulama adımı.

* ``data/curriculum.json`` — 1-12. sınıf ders/konu referansı (GÜNCELLENEBİLİR
  veri katmanı; resmi kaynakla yenilenir, kod içine hard-code edilmez).
* Eğitim sorusu tespiti + sınıf seviyesi tahmini (belirtilmemişse çıkarım).
* ``verify_answer`` — cevabı sunmadan ÖNCE en az 3 saniyelik doğrulama süresi:
  LLM self-check (JSON verdict + güven skoru); süre dolmadan sonuç dönmez.
* ``curriculum_context`` — seviyeye uygun dil + müfredat kapsamı talimatı.
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_PATH = Path(__file__).resolve().parent / "data" / "curriculum.json"
VERIFY_MIN_SECONDS = 3.0   # spec: 3 SANİYELİK doğrulama süresi

_CACHE: dict | None = None

GRADE_RE = re.compile(r"(\d{1,2})\.\s*sınıf", re.IGNORECASE)
_STAGE_HINTS = {"ilkokul": 3, "ortaokul": 6, "lise": 9,
                "anadolu lisesi": 9, "fen lisesi": 10, "meslek lisesi": 10}

_SUBJECT_HINTS = {
    "matematik": "Matematik", "kesir": "Matematik", "geometri": "Matematik",
    "türkçe": "Türkçe", "edebiyat": "Türkçe", "şiir": "Türkçe",
    "yazım": "Türkçe",
    "fen": "Fen Bilimleri", "hücre": "Fen Bilimleri",
    "fizik": "Fizik", "kuvvet": "Fizik", "elektrik": "Fizik",
    "kimya": "Kimya", "molekül": "Kimya", "asit": "Kimya",
    "biyoloji": "Biyoloji", "kalıtım": "Biyoloji",
    "tarih": "Tarih", "osmanlı": "Tarih",
    "coğrafya": "Coğrafya", "cografya": "Coğrafya", "iklim": "Coğrafya",
    "ingilizce": "İngilizce", "english": "İngilizce",
    "sosyal": "Sosyal Bilgiler", "felsefe": "Felsefe",
    "hayat bilgisi": "Hayat Bilgisi",
}

_EDU_MARKERS = ("ödev", "odev", "sınıf", "sinif", "müfredat", "mufredat",
                "sınav", "sinav", "test çöz", "test coz", "çözümü", "cozumu",
                "ders", "formül", "formul")


def load_curriculum(path=None) -> dict:
    """Müfredat JSON'unu yükle (cache'li; veri katmanı dosyadan güncellenir)."""
    global _CACHE
    if _CACHE is not None and path is None:
        return _CACHE
    p = Path(path) if path else DEFAULT_PATH
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or "grades" not in data:
            raise ValueError("şema geçersiz")
    except Exception as exc:
        logger.error("[Curriculum] Veri katmanı okunamadı (%s): %s", p, exc)
        data = {"grades": {}, "meta": {"error": str(exc)}}
    if path is None:
        _CACHE = data
    return data


def estimate_grade(text: str) -> int | None:
    """Soru metninden sınıf seviyesini tahmin et (yoksa None)."""
    t = (text or "").lower()
    m = GRADE_RE.search(t)
    if m:
        grade = int(m.group(1))
        return grade if 1 <= grade <= 12 else None
    for hint, grade in _STAGE_HINTS.items():
        if hint in t:
            return grade
    return None


def subject_of(text: str) -> str | None:
    """Sorunun hangi derse ait olduğunu tahmin et."""
    t = (text or "").lower()
    for hint, subject in _SUBJECT_HINTS.items():
        if hint in t:
            return subject
    return None


def is_education_query(text: str) -> bool:
    """Bu bir eğitim/ödev sorusu mu? (ders + ödev/sınıf/soru kalıpları)"""
    t = (text or "").lower()
    subject = subject_of(t)
    if subject is None:
        return False
    if estimate_grade(t) is not None:
        return True
    if any(marker in t for marker in _EDU_MARKERS):
        return True
    return any(k in t for k in ("nedir", "nasıl yapılır", "çöz", "açıkla",
                                "örnek ver", "formülü"))


def curriculum_context(grade: int | None, subject: str | None = None,
                       max_chars: int = 1600) -> str:
    """System prompt parçası: seviye + müfredat + seviye dili talimatı."""
    data = load_curriculum()
    grades = data.get("grades", {})
    lines = ["[MÜFREDAT BAĞLAMI — Özellik 8]"]
    if grade and str(grade) in grades:
        subjects = grades[str(grade)]
        lines.append(f"Sınıf seviyesi: {grade}. sınıf")
        use = {subject: subjects[subject]} if subject in subjects else subjects
        for subj, topics in use.items():
            lines.append(f"- {subj}: {', '.join(topics[:8])}")
        lines.append(
            f"YANIT DİLİ: Cevabı {grade}. sınıf öğrencisinin anlayacağı dil ve "
            "karmaşıklıkta ver; kapsamı yukarıdaki müfredat konularıyla sınırlı tut.")
    else:
        lines.append("Sınıf seviyesi belirtilmemiş → genel/orta seviyede yanıtla.")
    return "\n".join(lines)[:max_chars]


VERIFY_INSTRUCTION = (
    "Bir eğitimcusun. Kullanıcının sorusuna verilen cevabı iç kontrolle doğrula. "
    "SADECE şu JSON'u döndür: "
    '{"verdict": "dogru|supheli|yanlis", "confidence": 0.0-1.0, '
    '"reason": "kısa gerekçe (Türkçe)"}'
)


@dataclass
class VerifyResult:
    """Doğrulama sonucu (toplam süre ≥ 3 saniye)."""

    verdict: str        # "doğru" | "şüpheli" | "yanlış"
    confidence: float   # 0..1
    reason: str
    elapsed: float      # toplam saniye


def _parse_verdict(raw: str) -> tuple[str, float, str]:
    """LLM JSON yanıtını (verdict, confidence, reason) üçlüsüne çevir."""
    try:
        start, end = raw.find("{"), raw.rfind("}")
        data = json.loads(raw[start:end + 1])
        verdict = str(data.get("verdict", "şüpheli")).lower()
        verdict = {"dogru": "doğru", "yanlis": "yanlış",
                   "supheli": "şüpheli"}.get(verdict, verdict)
        if verdict not in {"doğru", "yanlış"}:
            verdict = "şüpheli"
        conf = float(data.get("confidence", 0.0))
        return verdict, max(0.0, min(1.0, conf)), str(data.get("reason", ""))[:200]
    except Exception:
        return "şüpheli", 0.0, "Doğrulama yanıtı okunamadı."


def verify_answer(question: str, answer: str, llm_fn=None,
                  min_seconds: float = VERIFY_MIN_SECONDS) -> VerifyResult:
    """Cevabı self-check ile doğrula; toplam süre ``min_seconds`` (3 sn) olana
    kadar bekler. LLM yoksa sonuç "şüpheli" olur ama süre yine tamamlanır."""
    start = time.monotonic()
    verdict, confidence, reason = "şüpheli", 0.0, "Doğrulama LLM'i mevcut değil."
    if llm_fn is not None:
        try:
            raw = llm_fn(question, VERIFY_INSTRUCTION, answer[:6000])
            if raw:
                verdict, confidence, reason = _parse_verdict(raw)
        except Exception as exc:
            logger.warning("[Curriculum] Doğrulama hatası: %s", exc)
            verdict, confidence, reason = "şüpheli", 0.0, f"Hata: {exc}"[:200]
    elapsed = time.monotonic() - start
    if elapsed < min_seconds:          # 3 saniyelik doğrulama süresi tamamlanır
        time.sleep(min_seconds - elapsed)
    elapsed = time.monotonic() - start
    logger.info("[Curriculum] Doğrulama: %s (%.1fs, güven %.0f%%)",
                verdict, elapsed, confidence * 100)
    return VerifyResult(verdict=verdict, confidence=confidence,
                        reason=reason, elapsed=elapsed)
